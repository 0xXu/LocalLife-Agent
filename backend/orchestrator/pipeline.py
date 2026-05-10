from __future__ import annotations

import json
import re
from collections.abc import Callable
from uuid import uuid4

from backend.data.catalog import LocalDataCatalog
from backend.llm import LLMClient, LLMConfig
from backend.models.schemas import (
    ItineraryStep,
    ParsedConstraints,
    PlanAction,
    PlanOverview,
    PlanState,
    PlanVariant,
    Receipt,
    RecoveryDiff,
    TraceStep,
)
from backend.tools import LocalToolRegistry


class LLMIntentParsingError(RuntimeError):
    pass


class PlanningPipeline:
    def __init__(self, catalog: LocalDataCatalog | None = None, llm_config: LLMConfig | None = None) -> None:
        self.catalog = catalog or LocalDataCatalog()
        self.tools = LocalToolRegistry(self.catalog)
        self.llm_config = llm_config or LLMConfig.from_env_file()
        self.llm = LLMClient(self.llm_config)

    def build(self, goal: str, overrides: dict | None = None, on_progress: Callable[[str, str], None] | None = None, on_token: Callable[[str], None] | None = None) -> PlanState:
        state = PlanState(goal=goal, plan_id=f"plan_{uuid4().hex[:10]}", status="input_received")
        constraints, llm_fallback = self.parse_constraints(goal, on_token=on_token)
        if overrides:
            constraints = apply_constraint_overrides(constraints, overrides)
        state.constraints = constraints
        state.status = "constraints_parsed"
        state.add_trace(
            TraceStep(
                "IntentParserAgent",
                "parse_user_goal",
                "ok",
                "解析自然语言目标为结构化约束。",
                {"goal_length": len(goal)},
                {"scenario": constraints.scenario, "llm_fallback": llm_fallback},
                140,
            )
        )
        if on_progress:
            on_progress("理解出行需求", "解析自然语言目标为结构化约束。")

        rainy = constraints.scenario == "rainy_indoor" or "下雨" in goal or "雨" in goal
        weather = self.tools.get_weather(rainy).output
        state.context = {"weather": weather, "profile": "local_demo_user", "privacy": "minimal"}
        state.status = "context_ready"
        state.add_trace(TraceStep("ContextBuilderAgent", "get_weather", "ok", "补全天气、位置和用户偏好上下文。", {}, weather, 120))
        if on_progress:
            on_progress("补全场景上下文", "补全天气、位置和用户偏好上下文。")

        radius = float(constraints.constraints["radius_km"])
        activity_tags = list(constraints.preferences.get("activity", []))
        restaurant_tags = list(constraints.preferences.get("diet", [])) or ["booking_supported"]
        activity_result = self.tools.search_places(constraints.scenario, radius, activity_tags)
        restaurant_result = self.tools.search_restaurants(constraints.scenario, radius, restaurant_tags)
        walk_result = self.tools.search_places("date" if constraints.scenario == "date" else "family", radius, ["walkable"])
        state.add_tool_result(activity_result, {"scenario": constraints.scenario, "radius_km": radius})
        state.add_tool_result(restaurant_result, {"scenario": constraints.scenario, "radius_km": radius})
        state.candidates = {
            "activities": activity_result.output["items"],
            "restaurants": restaurant_result.output["items"],
            "walks": self.catalog.search_pois("dessert_walk", None, radius, ["walkable"])[:6] or walk_result.output["items"],
        }
        state.status = "candidates_ready"
        state.add_trace(TraceStep("CandidateSearchAgent", "search_places", "ok", "检索活动、餐厅、甜品散步点和本地供给。", {}, {key: len(value) for key, value in state.candidates.items()}, 260))
        if on_progress:
            on_progress("筛选本地供给", "检索活动、餐厅、甜品散步点和本地供给。")

        state.ranked = {key: rank_items(items, constraints) for key, items in state.candidates.items()}
        state.status = "ranked"
        state.add_trace(TraceStep("RankerAgent", "rank_candidates", "ok", "按距离、评分、可订性、预算和场景匹配排序。", {}, {key: [item["id"] for item in value[:3]] for key, value in state.ranked.items()}, 180))
        if on_progress:
            on_progress("多目标排序", "按距离、评分、可订性、预算和场景匹配排序。")

        activity = state.ranked["activities"][0]
        restaurant = state.ranked["restaurants"][0]
        walk = state.ranked["walks"][0]
        route = self.tools.optimize_route([activity, restaurant, walk]).output
        state.itinerary = build_steps(activity, restaurant, walk, constraints)
        build_result = self.tools.build_itinerary(constraints, activity, restaurant, walk)
        state.add_tool_result(build_result, {"activity": activity["id"], "restaurant": restaurant["id"], "walk": walk["id"]})
        state.overview = PlanOverview(
            scenario_theme(constraints.scenario),
            "4.5 小时",
            route["drive_time"],
            route["walking_distance"],
            f"约 {build_result.output['estimated_budget']} 元",
            build_result.output["score"],
        )
        state.variants = build_variants(state.itinerary, build_result.output["estimated_budget"], constraints)
        state.status = "itinerary_built"
        state.add_trace(TraceStep("RouteSchedulerAgent", "optimize_route", "ok", "生成 4 到 6 小时可执行时间轴和顺路路线。", {}, route, 220))
        if on_progress:
            on_progress("生成时间轴和路线", "生成 4 到 6 小时可执行时间轴和顺路路线。")

        party_size = party_size_of(constraints)
        availability = self.tools.check_availability(restaurant["id"], "15:45", party_size).output
        validation = self.tools.validate_plan(bool(availability["available"]), route["total_travel_minutes"], build_result.output["estimated_budget"]).output
        state.add_tool_result(self.tools.check_availability(restaurant["id"], "15:45", party_size), {"place_id": restaurant["id"], "party_size": party_size})
        state.status = "pending_confirmation" if validation["valid"] else "recovering"
        state.add_trace(TraceStep("PlanValidatorAgent", "validate_plan", "ok" if validation["valid"] else "warning", "校验营业时间、路线、预算和可订性。", {}, validation, 170))
        if on_progress:
            on_progress("校验可订性和约束", "校验营业时间、路线、预算和可订性。")

        state.pending_actions = build_pending_actions(activity, restaurant, walk, constraints)
        state.actions = list(state.pending_actions)
        state.add_trace(TraceStep("ConfirmationAgent", "human_in_the_loop", "ok", "敏感动作已暂停，等待用户确认。", {}, {"pending_actions": len(state.pending_actions)}, 80))
        return state

    def execute(self, state: PlanState) -> PlanState:
        state.status = "executing"
        receipts: list[Receipt] = []
        for action in state.pending_actions:
            result = self.tools.execute_action(action)
            state.add_tool_result(result, {"tool": action.tool, "target": action.target})
            receipts.append(Receipt(action.type, action.tool, result.output["id"], result.output["status"], result.output["detail"]))
        state.receipts = receipts
        state.status = "completed"
        state.add_trace(TraceStep("ExecutionAgent", "confirmed_side_effect_tools", "ok", "用户确认后执行预约、订座、领券、点单、消息和日历动作。", {}, {"receipts": [item.id for item in receipts]}, 320))
        return state

    def recover(self, state: PlanState, reason: str) -> PlanState:
        state.status = "recovering"
        old_restaurant = next(step for step in state.itinerary if step.type == "restaurant")
        restaurants = [item for item in state.ranked.get("restaurants", []) if item["id"] != old_restaurant.place_id]
        fallback = restaurants[0] if restaurants else self.catalog.search_pois("restaurant", state.constraints.scenario, 8, ["fallback"])[0]
        restaurant_index = next(index for index, step in enumerate(state.itinerary) if step.type == "restaurant")
        state.itinerary[restaurant_index] = ItineraryStep("15:50", "16:50", "restaurant", fallback["name"], fallback["id"], fallback["reason"], f"约 {fallback['avg_price']} 元", "从上一站步行 7 分钟", 88, "已替换无位餐厅")
        activity_step = next(step for step in state.itinerary if step.type == "activity")
        walk_step = next(step for step in state.itinerary if step.type == "dessert_walk")
        state.pending_actions = build_pending_actions(self.catalog.get_poi(activity_step.place_id), fallback, self.catalog.get_poi(walk_step.place_id), state.constraints)
        state.actions = list(state.pending_actions)
        diff = RecoveryDiff(
            "restaurant",
            reason,
            old_restaurant.title,
            fallback["name"],
            "+约 40 元",
            "+步行 2 分钟",
            [state.itinerary[0].title, state.itinerary[2].title],
        )
        state.diff = diff
        state.recovery_history.append(diff)
        state.adjustment = {
            "headline": "餐厅临时不可用，已保留其他节点并替换餐厅",
            "message": f"{old_restaurant.title} 当前不可用，已切换到 {fallback['name']}，活动和饭后安排保持不变。",
            "primaryAction": "重新确认执行",
            "secondaryAction": "换另一个备选",
        }
        state.status = "recovered_pending_confirmation"
        state.add_trace(TraceStep("RecoveryAgent", "compare_alternatives", "ok", "异常恢复只替换冲突节点并展示差异。", {"reason": reason}, diff.as_frontend_dict(), 210))
        return state

    def parse_constraints(self, goal: str, on_token: Callable[[str], None] | None = None) -> tuple[ParsedConstraints, bool]:
        if not self.llm_config.is_configured or not self.llm_config.remote_enabled:
            raise LLMIntentParsingError("Remote LLM is required. Configure LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, and LLM_REMOTE_ENABLED=true.")
        messages = [
            {
                "role": "system",
                "content": (
                    "Extract planning info as JSON. Only return JSON, no explanation.\n"
                    '{"scenario":"family|friends|date|rainy_indoor","origin":{"type":"current_location","label":"home","lat":38.26,"lng":140.88},"time_window":{"date":"today","start":"HH:MM","duration_hours":N,"flexible":true},"people":{"adults":N,"children":[{"age":N}],"relationship":"family"},"preferences":{"distance":"nearby","diet":[],"activity":[],"budget_level":"medium"},"constraints":{"radius_km":N,"max_wait_minutes":15,"avoid":[]},"required_actions":["activity_reservation","restaurant_reservation","claim_coupon","create_order","send_plan_message","create_calendar_event"]}'
                ),
            },
            {"role": "user", "content": goal},
        ]
        try:
            content = ""
            for token in self.llm.chat_stream(messages):
                content += token
                if on_token:
                    on_token(token)
            parsed = json.loads(extract_json_object(content))
            return constraints_from_dict(parsed), False
        except Exception as exc:
            raise LLMIntentParsingError(f"LLM intent parsing failed: {exc}") from exc


def extract_json_object(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("llm_json_not_found")
    return stripped[start:end + 1]


def deterministic_constraints(goal: str) -> ParsedConstraints:
    scenario = detect_scenario(goal)
    child_age = parse_child_age(goal)
    adults = parse_adult_count(goal, child_age, scenario)
    radius = 5 if re.search(r"别.*远|附近|nearby|not too far|5km", goal, re.I) else 8
    diet = ["low_fat", "low_sugar"] if re.search(r"减脂|减肥|健康|低脂|diet|low[-\s]?fat", goal, re.I) else []
    if scenario == "date":
        activity = ["quiet", "romantic"]
    elif scenario == "friends":
        activity = ["social", "photo", "indoor"]
    elif scenario == "rainy_indoor":
        activity = ["indoor", "rain_safe"]
    else:
        activity = ["child_friendly", "not_too_tiring"]
    return ParsedConstraints(
        scenario=scenario,
        origin={"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
        time_window={"date": "today", "start": "13:30", "duration_hours": 4.5, "flexible": True},
        people={"adults": adults, "children": [{"age": child_age}] if child_age else [], "relationship": scenario},
        preferences={"distance": "nearby", "diet": diet, "activity": activity, "budget_level": "medium"},
        constraints={"radius_km": radius, "max_wait_minutes": 15, "avoid": ["heavy_oil", "long_queue", "smoking"]},
        required_actions=["activity_reservation", "restaurant_reservation", "claim_coupon", "create_order", "send_plan_message", "create_calendar_event"],
    )


def detect_scenario(goal: str) -> str:
    if "雨" in goal or "下雨" in goal or "室内" in goal:
        return "rainy_indoor"
    if "对象" in goal or "约会" in goal or "情侣" in goal:
        return "date"
    if "朋友" in goal or re.search(r"\d+\s*男\s*\d+\s*女", goal):
        return "friends"
    return "family"


def parse_child_age(goal: str) -> int | None:
    match = re.search(r"孩子\s*(\d{1,2})\s*岁|(\d{1,2})\s*(?:岁|yo).*(?:孩子|child|kid)", goal, re.I)
    if match:
        return int(next(group for group in match.groups() if group))
    return 5 if re.search(r"孩子|child|kid", goal, re.I) else None


def parse_adult_count(goal: str, child_age: int | None, scenario: str) -> int:
    if child_age:
        return 2
    gender = re.search(r"(\d{1,2})\s*男\s*(\d{1,2})\s*女", goal)
    if gender:
        return int(gender.group(1)) + int(gender.group(2))
    count = re.search(r"朋友\s*(\d{1,2})\s*个人|(\d{1,2})\s*个?人", goal)
    if count:
        return int(next(group for group in count.groups() if group))
    return 2 if scenario == "date" else 4 if scenario == "friends" else 2


def constraints_from_dict(data: dict) -> ParsedConstraints:
    fallback = deterministic_constraints("")
    people = normalize_people(data.get("people", fallback.people), fallback.people)
    time_window = normalize_time_window(data.get("time_window", fallback.time_window), fallback.time_window)
    preferences = normalize_preferences(data.get("preferences", fallback.preferences), fallback.preferences)
    constraints = normalize_constraints(data.get("constraints", fallback.constraints), fallback.constraints)
    return ParsedConstraints(
        scenario=data.get("scenario", fallback.scenario),
        origin=data.get("origin", fallback.origin),
        time_window=time_window,
        people=people,
        preferences=preferences,
        constraints=constraints,
        required_actions=as_list(data.get("required_actions", fallback.required_actions)),
    )


def normalize_people(value: dict, fallback: dict) -> dict:
    people = {**fallback, **value} if isinstance(value, dict) else dict(fallback)
    people["adults"] = int_or_default(people.get("adults"), int(fallback.get("adults", 2)))
    children = people.get("children", [])
    if children is None or children == 0:
        people["children"] = []
    elif isinstance(children, int):
        people["children"] = [{"age": None} for _ in range(children)]
    elif isinstance(children, dict):
        people["children"] = [children]
    elif isinstance(children, list):
        people["children"] = children
    else:
        people["children"] = []
    return people


def normalize_time_window(value: dict, fallback: dict) -> dict:
    time_window = {**fallback, **value} if isinstance(value, dict) else dict(fallback)
    time_window["duration_hours"] = float_or_default(time_window.get("duration_hours"), float(fallback.get("duration_hours", 4.5)))
    time_window["flexible"] = bool(time_window.get("flexible", fallback.get("flexible", True)))
    return time_window


def normalize_preferences(value: dict, fallback: dict) -> dict:
    preferences = {**fallback, **value} if isinstance(value, dict) else dict(fallback)
    preferences["diet"] = as_list(preferences.get("diet", fallback.get("diet", [])))
    preferences["activity"] = as_list(preferences.get("activity", fallback.get("activity", [])))
    return preferences


def normalize_constraints(value: dict, fallback: dict) -> dict:
    constraints = {**fallback, **value} if isinstance(value, dict) else dict(fallback)
    constraints["radius_km"] = float_or_default(constraints.get("radius_km"), float(fallback.get("radius_km", 5)))
    constraints["max_wait_minutes"] = int_or_default(constraints.get("max_wait_minutes"), int(fallback.get("max_wait_minutes", 15)))
    constraints["avoid"] = as_list(constraints.get("avoid", fallback.get("avoid", [])))
    return constraints


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def int_or_default(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def float_or_default(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def apply_constraint_overrides(constraints: ParsedConstraints, overrides: dict) -> ParsedConstraints:
    if "radius_km" in overrides:
        radius = float(overrides["radius_km"])
        if radius <= 0:
            raise ValueError("validation_error")
        constraints.constraints["radius_km"] = radius
    if "budget_level" in overrides:
        constraints.preferences["budget_level"] = str(overrides["budget_level"])
    if "start" in overrides:
        constraints.time_window["start"] = str(overrides["start"])
    return constraints


def rank_items(items: list[dict], constraints: ParsedConstraints) -> list[dict]:
    tags = constraints.preferences.get("diet", []) + constraints.preferences.get("activity", [])
    return sorted(
        items,
        key=lambda item: (
            sum(tag in item["tags"] for tag in tags),
            item["rating"],
            -item["distance_km"],
            -item["wait_minutes"],
        ),
        reverse=True,
    )


def build_steps(activity: dict, restaurant: dict, walk: dict, constraints: ParsedConstraints) -> list[ItineraryStep]:
    return [
        ItineraryStep("13:30", "13:45", "transport", "从当前位置出发", "origin_home", "按当前位置估算出发时间。", "约 35 元", "打车 12 分钟", 90),
        ItineraryStep("14:00", "15:30", "activity", activity["name"], activity["id"], activity["reason"], f"约 {activity['avg_price']} 元", "到达活动点", 92, risk_text(activity)),
        ItineraryStep("15:45", "16:45", "restaurant", restaurant["name"], restaurant["id"], restaurant["reason"], f"约 {restaurant['avg_price']} 元", "从活动点步行 5 分钟", 91, risk_text(restaurant)),
        ItineraryStep("17:00", "17:35", "dessert_walk", walk["name"], walk["id"], walk["reason"], f"约 {walk['avg_price']} 元", "轻松步行 1.2 公里", 88, risk_text(walk)),
    ]


def risk_text(poi: dict) -> str:
    return "周末可能排队，建议提前确认。" if poi.get("risk_tags") else "风险低。"


def build_variants(steps: list[ItineraryStep], budget: int, constraints: ParsedConstraints) -> list[PlanVariant]:
    return [
        PlanVariant("main", "主方案", "综合距离、可订性和偏好匹配。", 91, budget, [copy_step(step) for step in steps]),
        PlanVariant("budget", "省钱版", "优先使用团购券和低客单价餐厅。", 86, max(300, budget - 120), [copy_step(step) for step in steps]),
        PlanVariant("comfort", "舒适版", "减少步行和等待，优先高评分点位。", 89, budget + 160, [copy_step(step) for step in steps]),
        PlanVariant("child_first", "孩子优先版" if constraints.scenario == "family" else "体验优先版", "优先照顾活动体验和节奏。", 88, budget + 60, [copy_step(step) for step in steps]),
    ]


def copy_step(step: ItineraryStep) -> ItineraryStep:
    return ItineraryStep(step.start, step.end, step.type, step.title, step.place_id, step.reason, step.cost, step.travel, step.score, step.risk)


def build_pending_actions(activity: dict, restaurant: dict, walk: dict, constraints: ParsedConstraints) -> list[PlanAction]:
    people = party_size_of(constraints)
    recipient = "家庭群聊" if constraints.scenario == "family" else "朋友群聊" if constraints.scenario == "friends" else "同行人"
    return [
        PlanAction("activity_reservation", "预约活动", activity["name"], f"{people} 人名额，14:00 到 15:30。", True, "reserve_activity", {"place_id": activity["id"], "people": people}),
        PlanAction("restaurant_reservation", "预订餐厅", restaurant["name"], f"15:45，{people} 人桌。", True, "create_reservation", {"place_id": restaurant["id"], "people": people}),
        PlanAction("coupon", "领取团购券", restaurant["name"], "领取可核销套餐券，展示价格和规则。", True, "claim_coupon", {"place_id": restaurant["id"]}),
        PlanAction("order", "创建点单", restaurant["name"], "预创建低脂/低糖友好点单。", True, "create_order", {"shop_id": restaurant["id"]}),
        PlanAction("message", "发送计划", recipient, "发送时间轴、路线和预算摘要。", True, "send_plan_message", {"recipient": recipient}),
        PlanAction("calendar", "创建日历", "本地日历", "创建半日行程提醒。", True, "create_calendar_event", {"participants": people}),
    ]


def party_size_of(constraints: ParsedConstraints) -> int:
    return int(constraints.people.get("adults", 0)) + len(constraints.people.get("children", []))


def scenario_theme(scenario: str) -> str:
    return {
        "family": "下午 · 家庭 · 健康轻松",
        "friends": "下午 · 朋友 · 轻量聚会",
        "date": "下午 · 约会 · 安静有氛围",
        "rainy_indoor": "下午 · 雨天 · 室内稳定",
    }.get(scenario, "下午 · 本地生活 · 可执行")
