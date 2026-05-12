from __future__ import annotations

import json
import re
import warnings
from collections.abc import Callable
from typing import Any, TypedDict
from uuid import uuid4

from langchain_core._api.deprecation import LangChainPendingDeprecationWarning

warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)

from langgraph.graph import END, START, StateGraph

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
from backend.planning.candidates import build_itinerary_variants
from backend.providers.local import confidence_for_tags, ground_place
from backend.retrieval.ranker import rank_candidates
from backend.tools import LocalToolRegistry


class LLMIntentParsingError(RuntimeError):
    pass


class BuildGraphState(TypedDict, total=False):
    state: PlanState
    overrides: dict | None
    on_progress: Callable[[str, str], None] | None
    on_token: Callable[[str], None] | None
    llm_fallback: bool
    activity: dict | None
    restaurant: dict | None
    walk: dict | None
    route: dict[str, Any]
    build_result: dict[str, Any]
    validation: dict[str, Any]


class PlanningPipeline:
    def __init__(self, catalog: LocalDataCatalog | None = None, llm_config: LLMConfig | None = None) -> None:
        self.catalog = catalog or LocalDataCatalog()
        self.tools = LocalToolRegistry(self.catalog)
        self.llm_config = llm_config or LLMConfig.from_env_file()
        self.llm = LLMClient(self.llm_config)
        self.graph = self._compile_graph()

    def build(self, goal: str, overrides: dict | None = None, on_progress: Callable[[str, str], None] | None = None, on_token: Callable[[str], None] | None = None) -> PlanState:
        state = PlanState(goal=goal, plan_id=f"plan_{uuid4().hex[:10]}", status="input_received")
        result = self.graph.invoke({"state": state, "overrides": overrides, "on_progress": on_progress, "on_token": on_token})
        return result["state"]

    def _compile_graph(self):
        graph = StateGraph(BuildGraphState)
        graph.add_node("parse_intent", self._parse_intent_node)
        graph.add_node("build_context", self._build_context_node)
        graph.add_node("search_candidates", self._search_candidates_node)
        graph.add_node("rank_candidates", self._rank_candidates_node)
        graph.add_node("build_itinerary", self._build_itinerary_node)
        graph.add_node("validate_plan", self._validate_plan_node)
        graph.add_node("prepare_confirmation", self._prepare_confirmation_node)
        graph.add_edge(START, "parse_intent")
        graph.add_edge("parse_intent", "build_context")
        graph.add_edge("build_context", "search_candidates")
        graph.add_edge("search_candidates", "rank_candidates")
        graph.add_edge("rank_candidates", "build_itinerary")
        graph.add_edge("build_itinerary", "validate_plan")
        graph.add_edge("validate_plan", "prepare_confirmation")
        graph.add_edge("prepare_confirmation", END)
        return graph.compile()

    def _parse_intent_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints, llm_fallback = self.parse_constraints(state.goal, on_token=graph_state.get("on_token"))
        overrides = graph_state.get("overrides")
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
                {"goal_length": len(state.goal)},
                {"scenario": constraints.scenario, "llm_fallback": llm_fallback},
                140,
            )
        )
        emit_progress(graph_state, "理解出行需求", "解析自然语言目标为结构化约束。")
        return {"state": state, "llm_fallback": llm_fallback}

    def _build_context_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        rainy = constraints.scenario == "rainy_indoor" or "下雨" in state.goal or "雨" in state.goal
        weather = self.tools.get_weather(rainy).output
        state.context = {"weather": weather, "profile": "local_demo_user", "privacy": "minimal"}
        state.status = "context_ready"
        state.add_trace(TraceStep("ContextBuilderAgent", "get_weather", "ok", "补全天气、位置和用户偏好上下文。", {}, weather, 120))
        emit_progress(graph_state, "补全场景上下文", "补全天气、位置和用户偏好上下文。")
        return {"state": state}

    def _search_candidates_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
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
        emit_progress(graph_state, "筛选本地供给", "检索活动、餐厅、甜品散步点和本地供给。")
        return {"state": state}

    def _rank_candidates_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        ranked: dict[str, list[dict]] = {}
        candidate_sets: dict[str, list[dict[str, Any]]] = {}
        rejected: dict[str, list[dict[str, Any]]] = {}
        preferred_tags = list(constraints.preferences.get("activity", [])) + list(constraints.preferences.get("diet", []))
        for key, items in state.candidates.items():
            grounded = [ground_place(item, confidence_for_tags(item, preferred_tags)) for item in items]
            result = rank_candidates(grounded, constraints)
            ranked[key] = [candidate.place.as_poi_dict() for candidate in result.items]
            candidate_sets[key] = [
                {
                    "place": candidate.place.as_poi_dict(),
                    "total_score": candidate.total_score,
                    "score_breakdown": candidate.breakdown,
                    "explanation": candidate.explanation,
                }
                for candidate in result.items
            ]
            rejected[key] = result.rejected
        state.ranked = ranked
        state.candidate_sets = candidate_sets
        state.rejected_candidates = rejected
        state.status = "ranked"
        state.add_trace(TraceStep("RankerAgent", "rank_candidates", "ok", "按语义、距离、质量、等待、预算、来源和风险排序。", {}, {key: [item["place"]["id"] for item in value[:3]] for key, value in candidate_sets.items()}, 180))
        emit_progress(graph_state, "多目标排序", "按语义、距离、质量、等待、预算、来源和风险排序。")
        return {"state": state}

    def _build_itinerary_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        activity = state.ranked["activities"][0]
        restaurant = state.ranked["restaurants"][0] if should_include_restaurant(constraints) and state.ranked.get("restaurants") else None
        walk = state.ranked["walks"][0] if should_include_walk(constraints, restaurant) and state.ranked.get("walks") else None
        waypoints = [item for item in [activity, restaurant, walk] if item]
        route = self.tools.optimize_route(waypoints).output
        state.route = frontend_route(waypoints, route)
        state.itinerary = build_steps(activity, restaurant, walk, constraints)
        build_result = self.tools.build_itinerary(constraints, activity, restaurant, walk)
        state.add_tool_result(
            build_result,
            {
                "activity": activity["id"],
                "restaurant": restaurant["id"] if restaurant else None,
                "walk": walk["id"] if walk else None,
            },
        )
        state.overview = PlanOverview(
            scenario_theme(constraints.scenario),
            format_duration_hours(constraints.time_window.get("duration_hours", 4.5)),
            route["drive_time"],
            route["walking_distance"],
            f"约 {build_result.output['estimated_budget']} 元",
            build_result.output["score"],
        )
        state.variants = build_itinerary_variants(
            state.itinerary,
            state.ranked.get("activities", []),
            state.ranked.get("restaurants", []),
            state.ranked.get("walks", []),
            constraints,
            build_result.output["score"],
        )
        state.status = "itinerary_built"
        state.add_trace(TraceStep("RouteSchedulerAgent", "optimize_route", "ok", "按用户时长生成可执行时间轴和顺路路线。", {}, route, 220))
        emit_progress(graph_state, "生成时间轴和路线", "按用户时长生成可执行时间轴和顺路路线。")
        return {"state": state, "activity": activity, "restaurant": restaurant, "walk": walk, "route": route, "build_result": build_result.output}

    def _validate_plan_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        restaurant = graph_state.get("restaurant")
        route = graph_state["route"]
        build_result = graph_state["build_result"]
        party_size = party_size_of(constraints)
        available = True
        if restaurant:
            availability_result = self.tools.check_availability(restaurant["id"], restaurant_time_from_steps(state.itinerary), party_size)
            state.add_tool_result(availability_result, {"place_id": restaurant["id"], "party_size": party_size})
            available = bool(availability_result.output["available"])
        validation = self.tools.validate_plan(available, route["total_travel_minutes"], build_result["estimated_budget"]).output
        state.status = "pending_confirmation" if validation["valid"] else "recovering"
        state.add_trace(TraceStep("PlanValidatorAgent", "validate_plan", "ok" if validation["valid"] else "warning", "校验营业时间、路线、预算和可订性。", {}, validation, 170))
        emit_progress(graph_state, "校验可订性和约束", "校验营业时间、路线、预算和可订性。")
        return {"state": state, "validation": validation}

    def _prepare_confirmation_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        activity = graph_state["activity"]
        restaurant = graph_state.get("restaurant")
        walk = graph_state.get("walk")
        state.pending_actions = build_pending_actions(activity, restaurant, walk, constraints)
        state.actions = list(state.pending_actions)
        state.add_trace(TraceStep("ConfirmationAgent", "human_in_the_loop", "ok", "敏感动作已暂停，等待用户确认。", {}, {"pending_actions": len(state.pending_actions)}, 80))
        return {"state": state}

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
        constraints = require_constraints(state)
        old_restaurant = find_step(state.itinerary, "restaurant")
        if old_restaurant:
            restaurants = [item for item in state.ranked.get("restaurants", []) if item["id"] != old_restaurant.place_id]
            fallback = restaurants[0] if restaurants else self.catalog.search_pois("restaurant", constraints.scenario, 8, ["fallback"])[0]
            restaurant_index = next(index for index, step in enumerate(state.itinerary) if step.type == "restaurant")
            state.itinerary[restaurant_index] = ItineraryStep(
                old_restaurant.start,
                old_restaurant.end,
                "restaurant",
                fallback["name"],
                fallback["id"],
                fallback["reason"],
                f"约 {fallback['avg_price']} 元",
                "从上一站步行 7 分钟",
                88,
                "已替换无位餐厅",
            )
            changed = "restaurant"
            from_value = old_restaurant.title
            to_value = fallback["name"]
            cost_delta = "+约 40 元"
            travel_delta = "+步行 2 分钟"
        else:
            old_activity = find_step(state.itinerary, "activity")
            if old_activity is None:
                raise ValueError("validation_error")
            activities = [item for item in state.ranked.get("activities", []) if item["id"] != old_activity.place_id]
            fallback = activities[0] if activities else self.catalog.search_pois(None, None, 8, constraints.preferences.get("activity", []))[0]
            activity_index = next(index for index, step in enumerate(state.itinerary) if step.type == "activity")
            state.itinerary[activity_index] = ItineraryStep(
                old_activity.start,
                old_activity.end,
                "activity",
                fallback["name"],
                fallback["id"],
                fallback["reason"],
                f"约 {fallback['avg_price']} 元",
                old_activity.travel,
                score_step(fallback, constraints),
                "已替换不可用活动",
            )
            changed = "activity"
            from_value = old_activity.title
            to_value = fallback["name"]
            cost_delta = "按新活动价格调整"
            travel_delta = "路线保持相近"
        activity_step = find_step(state.itinerary, "activity")
        restaurant_step = find_step(state.itinerary, "restaurant")
        walk_step = find_step(state.itinerary, "dessert_walk")
        activity = self.catalog.get_poi(activity_step.place_id) if activity_step else fallback
        restaurant = self.catalog.get_poi(restaurant_step.place_id) if restaurant_step else None
        walk = self.catalog.get_poi(walk_step.place_id) if walk_step else None
        waypoints = [item for item in [activity, restaurant, walk] if item]
        state.route = frontend_route(waypoints, self.tools.optimize_route(waypoints).output)
        state.pending_actions = build_pending_actions(activity, restaurant, walk, constraints)
        state.actions = list(state.pending_actions)
        diff = RecoveryDiff(
            changed,
            reason,
            from_value,
            to_value,
            cost_delta,
            travel_delta,
            [step.title for step in state.itinerary if step.title not in {to_value}],
        )
        state.diff = diff
        state.recovery_history.append(diff)
        state.adjustment = {
            "headline": f"{'餐厅' if changed == 'restaurant' else '活动'}临时不可用，已只替换冲突节点",
            "message": f"{from_value} 当前不可用，已切换到 {to_value}，其他安排保持不变。",
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
                    "Extract planning info as one JSON object only. Do not use markdown, prose, or reasoning.\n"
                    "Do not force the user's goal into a fixed enum. The scenario value should be a short open-domain snake_case label such as hiking, pet_friendly_walk, deep_work_cafe, birthday_surprise, badminton, museum_day, ktv_night, parent_child_science, rainy_indoor, or family_picnic.\n"
                    "preferences.activity must be 3-8 concrete retrieval tags for tools, using natural English tags like hiking, outdoor, pet, quiet, cafe, wifi, work, sports, badminton, basketball, birthday, photo, museum, art, cinema, shopping, wellness, spa, ktv, nightlife, child_friendly, indoor, rain_safe, walkable.\n"
                    "preferences.intent_label should be a short Chinese display label, for example 宠物散步, 写代码自习, 羽毛球运动, 生日惊喜, 雨天室内.\n"
                    "Only include restaurant/coupon/order actions when the user asks for eating, dining, booking a meal, coupons, or ordering. Always include send_plan_message and create_calendar_event.\n"
                    '{"scenario":"open_domain_label","origin":{"type":"current_location","label":"home","lat":38.26,"lng":140.88},"time_window":{"date":"today","start":"HH:MM","duration_hours":3,"flexible":true},"people":{"adults":1,"children":[],"relationship":"solo"},"preferences":{"distance":"nearby","diet":[],"activity":["tag1","tag2"],"budget_level":"medium","intent_label":"中文短标签"},"constraints":{"radius_km":8,"max_wait_minutes":15,"avoid":["long_queue"]},"required_actions":["send_plan_message","create_calendar_event"]}'
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
            constraints = constraints_from_dict(parsed)
            return normalize_constraints_for_goal(goal, constraints), False
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
    if re.search(r"孩子|小孩|亲子|老婆孩子|family|child|kid", goal, re.I):
        return "family"
    return "local_life"


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
    scenario = normalize_scenario_label(data.get("scenario", fallback.scenario))
    people = normalize_people(data.get("people", fallback.people), fallback.people)
    time_window = normalize_time_window(data.get("time_window", fallback.time_window), fallback.time_window)
    preferences = normalize_preferences(data.get("preferences", fallback.preferences), fallback.preferences)
    constraints = normalize_constraints(data.get("constraints", fallback.constraints), fallback.constraints)
    return ParsedConstraints(
        scenario=scenario,
        origin=data.get("origin", fallback.origin),
        time_window=time_window,
        people=people,
        preferences=preferences,
        constraints=constraints,
        required_actions=as_list(data.get("required_actions", fallback.required_actions)),
    )


def normalize_constraints_for_goal(goal: str, constraints: ParsedConstraints) -> ParsedConstraints:
    if not is_hiking_goal(goal):
        return enrich_constraints_for_goal(goal, constraints)

    if not has_family_signal(goal) and not has_date_signal(goal) and constraints.scenario != "rainy_indoor":
        constraints.scenario = "friends"
        constraints.people["relationship"] = "friends"
        constraints.people["children"] = []

    party_size = parse_party_size(goal)
    if party_size:
        constraints.people["adults"] = party_size

    activity_tags = as_list(constraints.preferences.get("activity", []))
    constraints.preferences["activity"] = unique_list(["hiking", "outdoor", "nature", "walkable", "group_friendly", *activity_tags])
    constraints.constraints["radius_km"] = max(float_or_default(constraints.constraints.get("radius_km"), 5), 10)

    if not has_explicit_duration(goal) and float_or_default(constraints.time_window.get("duration_hours"), 4.5) >= 4.5:
        constraints.time_window["duration_hours"] = 3

    if not has_food_signal(goal):
        constraints.required_actions = [
            action for action in as_list(constraints.required_actions)
            if action not in {"restaurant_reservation", "claim_coupon", "create_order"}
        ]
    return enrich_constraints_for_goal(goal, constraints)


def enrich_constraints_for_goal(goal: str, constraints: ParsedConstraints) -> ParsedConstraints:
    tags = unique_list([*infer_activity_tags(goal), *as_list(constraints.preferences.get("activity", []))])
    if tags:
        constraints.preferences["activity"] = tags
    if "intent_label" not in constraints.preferences or not str(constraints.preferences.get("intent_label", "")).strip():
        constraints.preferences["intent_label"] = infer_intent_label(goal, constraints)
    party_size = parse_party_size(goal)
    if party_size:
        constraints.people["adults"] = party_size
        if not has_family_signal(goal):
            constraints.people["children"] = []
    if has_food_signal(goal):
        constraints.required_actions = unique_list([*as_list(constraints.required_actions), "restaurant_reservation", "claim_coupon", "create_order"])
    else:
        constraints.required_actions = [
            action for action in as_list(constraints.required_actions)
            if action not in {"restaurant_reservation", "claim_coupon", "create_order"}
        ]
    return constraints


def normalize_scenario_label(value) -> str:
    label = str(value or "local_life").strip()
    if not label or "|" in label or "," in label:
        return "local_life"
    normalized = re.sub(r"\s+", "_", label.lower())
    normalized = re.sub(r"[^0-9a-zA-Z_\-\u4e00-\u9fff]", "", normalized)
    return normalized or "local_life"


def infer_activity_tags(goal: str) -> list[str]:
    patterns = [
        (r"爬山|登山|徒步|山野|步道|hiking?|mountain|trail|trek", ["hiking", "outdoor", "nature", "walkable"]),
        (r"狗|宠物|猫|pet|dog|cat", ["pet", "outdoor", "walkable"]),
        (r"写代码|自习|学习|办公|工作|电脑|咖啡|coffee|cafe|work|study", ["work", "quiet", "cafe", "wifi"]),
        (r"羽毛球|篮球|足球|网球|运动|健身|badminton|basketball|sports|fitness", ["sports", "group_friendly"]),
        (r"生日|惊喜|纪念日|庆祝|birthday|celebration", ["birthday", "celebration", "photo"]),
        (r"展|博物馆|美术馆|艺术|museum|gallery|art", ["museum", "art", "quiet", "indoor"]),
        (r"电影|影院|cinema|movie", ["cinema", "indoor", "low_noise"]),
        (r"逛街|商场|买东西|shopping|mall", ["shopping", "indoor", "walkable"]),
        (r"KTV|酒吧|夜生活|唱歌|bar|nightlife", ["ktv", "nightlife", "group_friendly"]),
        (r"按摩|spa|放松|疗愈|wellness|relax", ["wellness", "spa", "quiet"]),
        (r"密室|剧本杀|escape|mystery", ["immersive", "mystery", "group_friendly"]),
        (r"孩子|小孩|亲子|family|child|kid", ["child_friendly", "not_too_tiring"]),
        (r"雨|下雨|室内|rain|indoor", ["indoor", "rain_safe"]),
    ]
    tags: list[str] = []
    for pattern, values in patterns:
        if re.search(pattern, goal, re.I):
            tags.extend(values)
    return unique_list(tags)


def infer_intent_label(goal: str, constraints: ParsedConstraints) -> str:
    tag_labels = [
        ({"pet"}, "宠物散步"),
        ({"work", "cafe"}, "写代码自习"),
        ({"hiking"}, "户外徒步"),
        ({"sports"}, "运动计划"),
        ({"birthday"}, "生日惊喜"),
        ({"museum", "art"}, "看展计划"),
        ({"cinema"}, "电影计划"),
        ({"shopping"}, "逛街计划"),
        ({"ktv", "nightlife"}, "夜生活聚会"),
        ({"wellness", "spa"}, "放松疗愈"),
        ({"child_friendly"}, "亲子活动"),
        ({"rain_safe"}, "雨天室内"),
    ]
    tags = set(constraints.preferences.get("activity", [])) | set(infer_activity_tags(goal))
    for required, label in tag_labels:
        if required <= tags:
            return label
    scenario = constraints.scenario.replace("_", " ").strip()
    return scenario if re.search(r"[\u4e00-\u9fff]", scenario) else "本地生活"


def is_hiking_goal(goal: str) -> bool:
    return bool(re.search(r"爬山|登山|徒步|山野|步道|hiking?|mountain|trail|trek", goal, re.I))


def has_family_signal(goal: str) -> bool:
    return bool(re.search(r"孩子|小孩|亲子|老婆孩子|family|child|kid", goal, re.I))


def has_date_signal(goal: str) -> bool:
    return bool(re.search(r"对象|约会|情侣|老婆(?!孩子)|date|couple", goal, re.I))


def has_food_signal(goal: str) -> bool:
    return bool(re.search(r"吃饭|吃点|吃个|吃些|用餐|聚餐|餐厅|晚饭|午饭|早饭|饭|dinner|lunch|restaurant|meal|dining", goal, re.I))


def has_explicit_duration(goal: str) -> bool:
    return bool(re.search(r"\d+(?:\.\d+)?\s*(小时|钟头|h|hour)|半天|全天|一小时|两小时|三小时|四小时|五小时", goal, re.I))


def parse_party_size(goal: str) -> int | None:
    digit = re.search(r"(\d{1,2})\s*(?:个)?人", goal)
    if digit:
        return int(digit.group(1))
    chinese_numbers = {
        "一": 1,
        "两": 2,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    chinese = re.search(r"([一两二三四五六七八九十])\s*(?:个)?人", goal)
    if chinese:
        return chinese_numbers[chinese.group(1)]
    return None


def unique_list(values: list) -> list:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


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


def require_constraints(state: PlanState) -> ParsedConstraints:
    if state.constraints is None:
        raise ValueError("constraints_not_ready")
    return state.constraints


def find_step(steps: list[ItineraryStep], step_type: str) -> ItineraryStep | None:
    return next((step for step in steps if step.type == step_type), None)


def emit_progress(graph_state: BuildGraphState, label: str, detail: str) -> None:
    on_progress = graph_state.get("on_progress")
    if on_progress:
        on_progress(label, detail)


def format_duration_hours(value) -> str:
    hours = float_or_default(value, 4.5)
    if hours.is_integer():
        return f"{int(hours)} 小时"
    return f"{hours:g} 小时"


def frontend_route(waypoints: list[dict], route: dict[str, Any]) -> dict[str, Any]:
    coordinates = [[float(item["lng"]), float(item["lat"])] for item in waypoints]
    if len(coordinates) == 1:
        lng, lat = coordinates[0]
        coordinates.append([lng + 0.002, lat + 0.002])
    if not coordinates:
        coordinates = [[140.8824, 38.2601], [140.8844, 38.2621]]
    legs = [
        {
            "from": leg.get("from_id", "origin"),
            "to": leg.get("to_id", "destination"),
            "mode": leg.get("mode", "taxi"),
            "duration_minutes": int(leg.get("minutes", 0)),
            "distance_km": float(leg.get("distance_km", 0)),
            "route_summary": "本地 seed 路线矩阵估算",
        }
        for leg in route.get("legs", [])
    ]
    walking_km = sum(float(leg.get("distance_km", 0)) for leg in route.get("legs", []) if leg.get("mode") == "walk")
    return {
        "legs": legs,
        "total_travel_minutes": int(route.get("total_travel_minutes", 0)),
        "walking_distance_km": round(walking_km, 2),
        "drive_time_minutes": int(route.get("total_travel_minutes", 0)) or 12,
        "polyline": {"type": "LineString", "coordinates": coordinates},
        "provider": "local_seed_route_matrix",
    }


def duration_hours_of(constraints: ParsedConstraints) -> float:
    return float_or_default(constraints.time_window.get("duration_hours"), 4.5)


def required_actions_of(constraints: ParsedConstraints) -> set[str]:
    return set(as_list(constraints.required_actions))


def should_include_restaurant(constraints: ParsedConstraints) -> bool:
    required = required_actions_of(constraints)
    if required & {"restaurant_reservation", "claim_coupon", "create_order"}:
        return True
    if set(constraints.preferences.get("activity", [])) & {"hiking", "outdoor", "nature", "pet", "work", "sports"}:
        return False
    return duration_hours_of(constraints) >= 2.25


def should_include_walk(constraints: ParsedConstraints, restaurant: dict | None) -> bool:
    return bool(restaurant) and duration_hours_of(constraints) >= 3.5


def restaurant_time_from_steps(steps: list[ItineraryStep]) -> str:
    for step in steps:
        if step.type == "restaurant":
            return step.start
    return "15:45"


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
    if "duration_hours" in overrides:
        duration = float(overrides["duration_hours"])
        if duration <= 0:
            raise ValueError("validation_error")
        constraints.time_window["duration_hours"] = duration
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


def build_steps(activity: dict, restaurant: dict | None, walk: dict | None, constraints: ParsedConstraints) -> list[ItineraryStep]:
    start = parse_time_minutes(str(constraints.time_window.get("start", "14:00")))
    duration_minutes = max(60, int(duration_hours_of(constraints) * 60))
    cursor = start
    steps = [
        ItineraryStep(
            format_time(cursor - 15),
            format_time(cursor),
            "transport",
            "从当前位置出发",
            "origin_home",
            "按当前位置估算出发时间。",
            "约 35 元",
            "打车 12 分钟",
            90,
        )
    ]

    reserved = 0
    if restaurant:
        reserved += 15 + 60
    if walk:
        reserved += 15 + 35
    activity_minutes = min(int(activity.get("duration_minutes", 90)), max(45, duration_minutes - 15 - reserved))
    activity_end = cursor + activity_minutes
    steps.append(
        ItineraryStep(
            format_time(cursor),
            format_time(activity_end),
            "activity",
            activity["name"],
            activity["id"],
            activity["reason"],
            f"约 {activity['avg_price']} 元",
            "到达活动点",
            score_step(activity, constraints),
            risk_text(activity),
        )
    )
    cursor = activity_end

    if restaurant:
        cursor += 15
        restaurant_end = cursor + 60
        steps.append(
            ItineraryStep(
                format_time(cursor),
                format_time(restaurant_end),
                "restaurant",
                restaurant["name"],
                restaurant["id"],
                restaurant["reason"],
                f"约 {restaurant['avg_price']} 元",
                "从活动点顺路前往",
                score_step(restaurant, constraints),
                risk_text(restaurant),
            )
        )
        cursor = restaurant_end

    if walk:
        cursor += 15
        walk_end = cursor + 35
        steps.append(
            ItineraryStep(
                format_time(cursor),
                format_time(walk_end),
                "dessert_walk",
                walk["name"],
                walk["id"],
                walk["reason"],
                f"约 {walk['avg_price']} 元",
                "饭后轻松步行",
                score_step(walk, constraints),
                risk_text(walk),
            )
        )
    return steps


def parse_time_minutes(value: str) -> int:
    match = re.match(r"^(\d{1,2}):(\d{2})$", value)
    if not match:
        return 14 * 60
    hours = max(0, min(23, int(match.group(1))))
    minutes = max(0, min(59, int(match.group(2))))
    return hours * 60 + minutes


def format_time(total_minutes: int) -> str:
    total_minutes = total_minutes % (24 * 60)
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def score_step(item: dict, constraints: ParsedConstraints) -> int:
    tags = set(item.get("tags", []))
    preferred = set(constraints.preferences.get("activity", [])) | set(constraints.preferences.get("diet", []))
    score = 76 + int(float(item.get("rating", 4.0)) * 3)
    score += min(6, 2 * len(tags & preferred))
    score -= min(6, int(item.get("wait_minutes", 0)) // 8)
    return max(70, min(98, score))


def risk_text(poi: dict) -> str:
    return "周末可能排队，建议提前确认。" if poi.get("risk_tags") else "风险低。"


def build_variants(steps: list[ItineraryStep], budget: int, constraints: ParsedConstraints, base_score: int) -> list[PlanVariant]:
    experience_title = "孩子优先版" if constraints.scenario == "family" else "体验优先版"
    experience_kind = "child_first" if constraints.scenario == "family" else "experience_first"
    return [
        PlanVariant("main", "主方案", "综合距离、可订性和偏好匹配。", base_score, budget, [copy_step(step) for step in steps]),
        PlanVariant("budget", "省钱版", "优先使用团购券和低客单价餐厅。", max(60, base_score - 5), max(300, budget - 120), [copy_step(step) for step in steps]),
        PlanVariant("comfort", "舒适版", "减少步行和等待，优先高评分点位。", min(98, base_score + 2), budget + 160, [copy_step(step) for step in steps]),
        PlanVariant(experience_kind, experience_title, "优先照顾活动体验和节奏。", max(60, min(98, base_score - 1)), budget + 60, [copy_step(step) for step in steps]),
    ]


def copy_step(step: ItineraryStep) -> ItineraryStep:
    return ItineraryStep(step.start, step.end, step.type, step.title, step.place_id, step.reason, step.cost, step.travel, step.score, step.risk)


def build_pending_actions(activity: dict, restaurant: dict | None, walk: dict | None, constraints: ParsedConstraints) -> list[PlanAction]:
    people = party_size_of(constraints)
    relationship = str(constraints.people.get("relationship", constraints.scenario))
    recipient = "家庭群聊" if constraints.scenario == "family" or relationship == "family" else "朋友群聊" if constraints.scenario == "friends" or relationship == "friends" else "同行人"
    actions = [
        PlanAction("activity_reservation", "预约活动", activity["name"], f"{people} 人名额，14:00 到 15:30。", True, "reserve_activity", {"place_id": activity["id"], "people": people}),
    ]
    if restaurant:
        actions.extend(
            [
                PlanAction("restaurant_reservation", "预订餐厅", restaurant["name"], f"{people} 人桌。", True, "create_reservation", {"place_id": restaurant["id"], "people": people}),
                PlanAction("coupon", "领取团购券", restaurant["name"], "领取可核销套餐券，展示价格和规则。", True, "claim_coupon", {"place_id": restaurant["id"]}),
                PlanAction("order", "创建点单", restaurant["name"], "预创建低脂/低糖友好点单。", True, "create_order", {"shop_id": restaurant["id"]}),
            ]
        )
    actions.extend(
        [
            PlanAction("message", "发送计划", recipient, "发送时间轴、路线和预算摘要。", True, "send_plan_message", {"recipient": recipient}),
            PlanAction("calendar", "创建日历", "本地日历", "创建行程提醒。", True, "create_calendar_event", {"participants": people}),
        ]
    )
    return actions


def party_size_of(constraints: ParsedConstraints) -> int:
    return int(constraints.people.get("adults", 0)) + len(constraints.people.get("children", []))


def scenario_theme(scenario: str) -> str:
    label = scenario.replace("_", " ").strip()
    return {
        "family": "下午 · 家庭 · 健康轻松",
        "friends": "下午 · 朋友 · 轻量聚会",
        "date": "下午 · 约会 · 安静有氛围",
        "rainy_indoor": "下午 · 雨天 · 室内稳定",
    }.get(scenario, f"下午 · {label or '本地生活'} · 可执行")
