from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.graph.state import new_action_id


def build_executable_actions(
    revision_id: str,
    plan: dict[str, Any],
    candidate_lookup: dict[str, dict[str, Any]],
    constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    required_actions = set(_value(constraints, "required_actions", []))
    party_size = _party_size(constraints)

    actions: list[dict[str, Any]] = []
    for step in plan.get("itinerary", []):
        step_type = step.get("type")
        place_id = step.get("place_id")
        if not place_id:
            continue

        candidate = candidate_lookup.get(place_id)
        if not candidate:
            continue

        if step_type == "activity":
            if "activity_reservation" in required_actions and bool(candidate.get("booking_supported")):
                time = _step_time(step)
                if time:
                    actions.append(
                        make_action(
                            revision_id,
                            tool="reserve_activity",
                            label="预约活动",
                            target=_target(step, candidate),
                            payload={"place_id": place_id, "time": time, "people": party_size},
                        )
                    )
            continue

        if step_type != "restaurant":
            continue

        time = _step_time(step)
        target = _target(step, candidate)
        if "restaurant_reservation" in required_actions and bool(candidate.get("booking_supported")) and time:
            actions.append(
                make_action(
                    revision_id,
                    tool="create_reservation",
                    label="预订餐厅",
                    target=target,
                    payload={"place_id": place_id, "time": time, "people": party_size},
                )
            )

        deal_id = _deal_id(candidate)
        if "claim_coupon" in required_actions and deal_id:
            actions.append(
                make_action(
                    revision_id,
                    tool="claim_coupon",
                    label="领取团购券",
                    target=target,
                    payload={"deal_id": deal_id},
                )
            )

        menu = _menu(candidate)
        if "create_order" in required_actions and menu and time:
            actions.append(
                make_action(
                    revision_id,
                    tool="create_order",
                    label="创建点单",
                    target=target,
                    payload={
                        "shop_id": step.get("shop_id") or candidate.get("shop_id") or place_id,
                        "menu": menu,
                        "time": time,
                    },
                )
            )

    return actions


def make_action(revision_id: str, tool: str, label: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
    action_id = new_action_id()
    return {
        "action_id": action_id,
        "revision_id": revision_id,
        "tool": tool,
        "label": label,
        "target": target,
        "status": "pending",
        "idempotency_key": f"{revision_id}:{action_id}",
        "requires_confirmation": True,
        "payload": payload,
        "receipt_id": "",
    }


def _party_size(constraints: Mapping[str, Any]) -> int:
    people = _value(constraints, "people", {})
    return int(_value(people, "adults", 0)) + len(_value(people, "children", []))


def _target(step: Mapping[str, Any], candidate: Mapping[str, Any]) -> str:
    return str(step.get("title") or candidate.get("name") or step.get("place_id") or "")


def _step_time(step: Mapping[str, Any]) -> str:
    return str(step.get("time") or step.get("start") or "")


def _deal_id(candidate: Mapping[str, Any]) -> str:
    deal_id = candidate.get("deal_id")
    if deal_id:
        return str(deal_id)

    coupon = candidate.get("coupon")
    if coupon:
        return _id_from_grounding(coupon)

    coupons = candidate.get("coupons")
    if coupons:
        return _id_from_grounding(coupons[0])

    deals = candidate.get("deals")
    if deals:
        return _id_from_grounding(deals[0])

    return ""


def _menu(candidate: Mapping[str, Any]) -> Any:
    for value in (candidate.get("menu"), candidate.get("menus")):
        if isinstance(value, (Mapping, list)) and value:
            return value
    return []


def _id_from_grounding(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("deal_id") or value.get("id") or "")
    if isinstance(value, str):
        return value
    return ""


def _value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)
