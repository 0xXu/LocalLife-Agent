from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def build_executable_actions(
    revision_id: str,
    plan: dict[str, Any],
    candidate_lookup: dict[str, dict[str, Any]],
    constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    required_actions = set(_value(constraints, "required_actions", []))
    party_size = _party_size(constraints)
    user_id = _user_id(constraints)

    actions: list[dict[str, Any]] = []
    for step in plan.get("itinerary", []):
        step_type = step.get("type")
        place_id = step.get("place_id")
        if not place_id:
            continue

        candidate = candidate_lookup.get(place_id)
        if not candidate or not _identity_matches(step, candidate):
            continue

        if step_type == "activity":
            if (
                "activity_reservation" in required_actions
                and _activity_grounded(candidate)
                and candidate.get("booking_supported") is True
            ):
                time = _step_time(step)
                if time:
                    actions.append(
                        make_action(
                            revision_id,
                            tool="reserve_activity",
                            label="预约活动",
                            target=_target(step, candidate),
                            payload={"place_id": place_id, "time": time, "party_size": party_size},
                        )
                    )
            continue

        if step_type != "restaurant":
            continue
        if not _restaurant_grounded(candidate):
            continue

        time = _step_time(step)
        target = _target(step, candidate)
        if "restaurant_reservation" in required_actions and candidate.get("booking_supported") is True and time:
            actions.append(
                make_action(
                    revision_id,
                    tool="create_reservation",
                    label="预订餐厅",
                    target=target,
                    payload={"place_id": place_id, "time": time, "party_size": party_size},
                )
            )

        deal_id = _deal_id(candidate)
        if "claim_coupon" in required_actions and deal_id and user_id:
            actions.append(
                make_action(
                    revision_id,
                    tool="claim_coupon",
                    label="领取团购券",
                    target=target,
                    payload={"place_id": place_id, "deal_id": deal_id, "user_id": user_id},
                )
            )

        items = _items(candidate)
        if "create_order" in required_actions and items and time:
            actions.append(
                make_action(
                    revision_id,
                    tool="create_order",
                    label="创建点单",
                    target=target,
                    payload={
                        "shop_id": step.get("shop_id") or candidate.get("shop_id") or place_id,
                        "items": items,
                        "pickup_time": time,
                        "party_size": party_size,
                    },
                )
            )

    return actions


def make_action(
    revision_id: str,
    tool: str,
    label: str,
    target: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    idempotency_key = _stable_idempotency_key(revision_id, tool, payload)
    action_id = _stable_action_id(idempotency_key)
    return {
        "action_id": action_id,
        "revision_id": revision_id,
        "tool": tool,
        "label": label,
        "target": target,
        "status": "pending",
        "idempotency_key": idempotency_key,
        "requires_confirmation": True,
        "payload": payload,
        "receipt_id": "",
    }


def _party_size(constraints: Mapping[str, Any]) -> int:
    people = _value(constraints, "people", {})
    adults = _int_count(_value(people, "adults", 0))
    children = _children_count(_value(people, "children", 0))
    return adults + children


def _int_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return max(count, 0)


def _children_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return _int_count(value)


def _target(step: Mapping[str, Any], candidate: Mapping[str, Any]) -> str:
    return str(step.get("title") or candidate.get("name") or step.get("place_id") or "")


def _step_time(step: Mapping[str, Any]) -> str:
    return str(step.get("time") or step.get("start") or "")


def _deal_id(candidate: Mapping[str, Any]) -> str:
    deal_id = candidate.get("deal_id")
    if isinstance(deal_id, str) and deal_id:
        return deal_id

    coupon = candidate.get("coupon")
    if isinstance(coupon, (Mapping, str)):
        return _id_from_grounding(coupon)

    coupons = candidate.get("coupons")
    if isinstance(coupons, list) and coupons:
        return _id_from_grounding(coupons[0])

    deals = candidate.get("deals")
    if isinstance(deals, list) and deals:
        return _id_from_grounding(deals[0])

    return ""


def _items(candidate: Mapping[str, Any]) -> list[Any]:
    for value in (candidate.get("items"), candidate.get("menu"), candidate.get("menus")):
        if _valid_items(value):
            return value
    return []


def _id_from_grounding(value: Any) -> str:
    if isinstance(value, Mapping):
        grounded_id = value.get("deal_id") or value.get("id")
        if isinstance(grounded_id, str) and grounded_id:
            return grounded_id
        return ""
    if isinstance(value, str):
        return value
    return ""


def _value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _user_id(constraints: Mapping[str, Any]) -> str:
    value = _value(constraints, "user_id", "")
    if isinstance(value, str) and value:
        return value
    user = _value(constraints, "user", {})
    value = _value(user, "id", "")
    if isinstance(value, str) and value:
        return value
    return ""


def _identity_matches(step: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    expected_ids = {str(value) for value in (step.get("place_id"), step.get("shop_id")) if value}
    candidate_ids = {str(candidate[key]) for key in ("id", "place_id", "shop_id") if candidate.get(key)}
    return bool(expected_ids & candidate_ids)


def _restaurant_grounded(candidate: Mapping[str, Any]) -> bool:
    return candidate.get("category") == "restaurant"


def _activity_grounded(candidate: Mapping[str, Any]) -> bool:
    category = candidate.get("category")
    if not isinstance(category, str) or not category:
        return False
    normalized = category.lower()
    allowed_categories = {"social_activity", "family_activity", "date_activity", "indoor_activity"}
    return normalized in allowed_categories or "activity" in normalized


def _valid_items(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    for item in value:
        if isinstance(item, str):
            if not item:
                return False
            continue
        if isinstance(item, Mapping):
            item_id = item.get("id") or item.get("item_id")
            if not isinstance(item_id, str) or not item_id:
                return False
            continue
        return False
    return True


def _stable_idempotency_key(
    revision_id: str,
    tool: str,
    payload: dict[str, Any],
) -> str:
    source = {
        "revision_id": revision_id,
        "tool": tool,
        "payload": payload,
    }
    source_json = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(source_json.encode("utf-8")).hexdigest()
    return f"{revision_id}:{tool}:{digest[:24]}"


def _stable_action_id(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return f"act_{digest[:24]}"
