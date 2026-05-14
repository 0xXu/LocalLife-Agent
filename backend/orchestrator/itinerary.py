"""Itinerary building, route helpers, and action construction functions.

Extracted from pipeline.py to keep that module focused on the LangGraph workflow.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from backend.models.schemas import (
    ItineraryStep,
    ParsedConstraints,
    PlanAction,
    PlanState,
    PlanVariant,
)
from backend.orchestrator.constraints import (
    as_list,
    float_or_default,
    normalize_required_actions,
)

if TYPE_CHECKING:
    from backend.orchestrator.pipeline import BuildGraphState


class LLMIntentParsingError(RuntimeError):
    pass


def _apply_replacement(state: PlanState, decision: dict[str, Any]) -> None:
    target_type = decision.get("target_type", "")
    replacement_id = decision.get("replacement_id", "")
    if not target_type or not replacement_id:
        return

    # Find replacement candidate
    replacement = None
    for items in state.ranked.values():
        for item in items:
            if item.get("id") == replacement_id:
                replacement = item
                break
        if replacement:
            break

    if not replacement:
        return

    # Replace in itinerary
    for i, step in enumerate(state.itinerary):
        if step.type == target_type:
            state.itinerary[i] = ItineraryStep(
                step.start, step.end, step.type,
                replacement.get("name", step.title),
                replacement_id,
                replacement.get("reason", step.reason),
                f"约 {replacement.get('avg_price', 0)} 元",
                step.travel,
                step.score,
                step.risk,
            )
            break

    # Remove old pending actions for this type and rebuild
    state.pending_actions = [
        action for action in state.pending_actions
        if action.type != target_type
    ]


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
    if constraints.preferences.get("meal_required") is False:
        return False
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
    if "pace" in overrides:
        constraints.preferences["pace"] = str(overrides["pace"])
    if "meal_required" in overrides:
        constraints.preferences["meal_required"] = bool(overrides["meal_required"])
        if overrides["meal_required"] is False:
            constraints.required_actions = [
                action for action in constraints.required_actions
                if action not in {"restaurant_reservation", "claim_coupon", "create_order"}
            ]
    if "required_actions" in overrides:
        constraints.required_actions = normalize_required_actions(overrides["required_actions"])
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
