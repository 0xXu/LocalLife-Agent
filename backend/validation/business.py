from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any


_PLACE_BOUND_TOOLS = {"reserve_activity", "create_reservation", "claim_coupon", "create_order"}
_REQUIRED_PAYLOAD_FIELDS = {
    "send_plan_message": ("recipient", "message"),
    "create_calendar_event": ("itinerary", "participants"),
}


def validate_revision_for_approval(
    plan: Any,
    candidate_lookup: Mapping[str, Mapping[str, Any]],
    constraints: Any,
    actions: list[Any],
    weather: Mapping[str, Any],
) -> dict[str, Any]:
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    steps = [_as_mapping(step) for step in _value(plan, "itinerary", _value(plan, "steps", [])) if _as_mapping(step)]
    place_steps = [step for step in steps if _step_type(step) != "transport"]
    party_size = _party_size(constraints)
    visit_date = _visit_date(constraints)

    if party_size <= 0:
        blocking.append({"code": "party_size_missing"})

    if place_steps and not _has_origin_route_leg(plan, str(_value(place_steps[0], "place_id", "")), steps):
        blocking.append({"code": "missing_origin_route_leg", "from": "origin_home", "to": _value(place_steps[0], "place_id", "")})

    step_by_action_id: dict[str, Mapping[str, Any]] = {}
    for step in place_steps:
        for alias in _step_aliases(step):
            step_by_action_id[alias] = step

        place_id = str(_value(step, "place_id", ""))
        candidate = _candidate_for_step(step, candidate_lookup)
        if not candidate:
            blocking.append({"code": "ungrounded_step", "place_id": place_id, "title": _value(step, "title", "")})
            continue
        for alias in _candidate_aliases(candidate):
            step_by_action_id[alias] = step

        start = str(_value(step, "start", _value(step, "time", "")))
        if not _is_open_at(_value(candidate, "open_hours", []), visit_date, start):
            blocking.append({"code": "closed_at_visit_time", "place_id": place_id, "time": start, "date": visit_date})

        if _is_rain(weather) and "outdoor" in {str(tag).lower() for tag in _value(candidate, "tags", [])}:
            warnings.append({"code": "weather_mismatch", "place_id": place_id, "condition": _value(weather, "condition", "")})

        if _is_restaurant(step, candidate) and "availability" in candidate and not _has_matching_availability_slot(
            _value(candidate, "availability", []), start, party_size
        ):
            blocking.append({"code": "availability_slot_mismatch", "place_id": place_id, "time": start, "party_size": party_size})

    for action in actions:
        _validate_action(_as_mapping(action), step_by_action_id, party_size, blocking)

    return {"valid": not blocking, "blocking": blocking, "warnings": warnings}


def _validate_action(
    action: Mapping[str, Any],
    step_by_place_id: Mapping[str, Mapping[str, Any]],
    party_size: int,
    blocking: list[dict[str, Any]],
) -> None:
    tool = str(_value(action, "tool", _value(action, "type", "")))
    if not _value(action, "idempotency_key", ""):
        blocking.append({"code": "missing_idempotency_key", "tool": tool})

    payload = _as_mapping(_value(action, "payload", {}))
    action_place_id = _payload_place_id(payload)
    matching_step = step_by_place_id.get(action_place_id) if action_place_id else None

    if tool in _REQUIRED_PAYLOAD_FIELDS:
        missing = [field for field in _REQUIRED_PAYLOAD_FIELDS[tool] if not _value(payload, field, None)]
        if missing:
            blocking.append({"code": "action_payload_missing", "tool": tool, "missing": missing})

    if tool in _PLACE_BOUND_TOOLS and not action_place_id:
        blocking.append({"code": "ungrounded_action", "place_id": "", "tool": tool})
        return

    if action_place_id and matching_step is None:
        blocking.append({"code": "ungrounded_action", "place_id": action_place_id, "tool": tool})
        return

    action_time = _payload_time(payload)
    if action_time and matching_step is not None:
        step_start = str(_value(matching_step, "start", _value(matching_step, "time", "")))
        if not _same_time(step_start, action_time):
            blocking.append({"code": "action_time_mismatch", "place_id": action_place_id, "step_time": step_start, "action_time": action_time})

    if _is_reservation_or_order(action):
        action_party_size = _payload_party_size(payload)
        if action_party_size is None:
            blocking.append({"code": "action_party_size_missing", "place_id": action_place_id, "tool": tool})
            return
        if action_party_size != party_size:
            blocking.append(
                {
                    "code": "action_party_size_mismatch",
                    "place_id": action_place_id,
                    "expected": party_size,
                    "actual": action_party_size,
                }
            )


def _candidate_for_step(step: Mapping[str, Any], candidate_lookup: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    for alias in _step_aliases(step):
        candidate = _as_mapping(candidate_lookup.get(alias))
        if candidate:
            return candidate
    return {}


def _has_origin_route_leg(plan: Any, first_place_id: str, steps: list[Mapping[str, Any]]) -> bool:
    if not first_place_id:
        return False
    route = _as_mapping(_value(plan, "route", {}))
    legs = _value(route, "legs", _value(plan, "legs", []))
    for leg_value in legs:
        leg = _as_mapping(leg_value)
        from_id = str(_value(leg, "from", _value(leg, "from_id", "")))
        to_id = str(_value(leg, "to", _value(leg, "to_id", "")))
        if from_id == "origin_home" and to_id == first_place_id:
            return True
    if not legs and steps:
        leading_step = steps[0]
        from_id = str(_value(leading_step, "from", _value(leading_step, "from_id", "")))
        to_id = str(_value(leading_step, "to", _value(leading_step, "to_id", "")))
        if _step_type(leading_step) == "transport" and from_id == "origin_home" and to_id == first_place_id:
            return True
    return False


def _has_matching_availability_slot(availability: Any, start: str, party_size: int) -> bool:
    if not isinstance(availability, list):
        return False
    for slot_value in availability:
        slot = _as_mapping(slot_value)
        if not _same_time(str(_value(slot, "time", "")), start):
            continue
        if _value(slot, "available", False) is not True:
            continue
        if _int_count(_value(slot, "capacity", 0)) >= party_size:
            return True
    return False


def _is_open_at(open_hours: Any, visit_date: str, time_value: str) -> bool:
    if not open_hours:
        return True
    if not isinstance(open_hours, list):
        return False
    for item_value in open_hours:
        item = _as_mapping(item_value)
        if not _date_matches(item, visit_date):
            continue
        start = str(_value(item, "start", "00:00"))
        end = str(_value(item, "end", "23:59"))
        if _time_in_range(time_value, start, end):
            return True
    return False


def _date_matches(item: Mapping[str, Any], visit_date: str) -> bool:
    item_date = _value(item, "date", "")
    if item_date and str(item_date) != visit_date:
        return False

    item_day = _value(item, "day", "")
    if not item_day:
        return True
    item_day_normalized = str(item_day).strip().lower()
    if item_day_normalized == "today":
        return True

    visit_day = _weekday_name(visit_date)
    if not visit_day:
        return True
    return item_day_normalized[:3] == visit_day[:3]


def _visit_date(constraints: Any) -> str:
    time_window = _value(constraints, "time_window", {})
    value = _value(time_window, "date", "")
    if not value or str(value).lower() == "today":
        return date.today().isoformat()
    return str(value)


def _weekday_name(date_value: str) -> str:
    try:
        return date.fromisoformat(date_value).strftime("%a").lower()
    except ValueError:
        return ""


def _party_size(constraints: Any) -> int:
    people = _value(constraints, "people", {})
    adults = _int_count(_value(people, "adults", 0))
    children = _children_count(_value(people, "children", 0))
    return adults + children


def _children_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return _int_count(value)


def _step_aliases(step: Mapping[str, Any]) -> set[str]:
    return _aliases_from(step, ("id", "place_id", "shop_id"))


def _candidate_aliases(candidate: Mapping[str, Any]) -> set[str]:
    return _aliases_from(candidate, ("id", "place_id", "shop_id"))


def _aliases_from(source: Mapping[str, Any], keys: tuple[str, ...]) -> set[str]:
    aliases: set[str] = set()
    for key in keys:
        value = _value(source, key, "")
        if value:
            aliases.add(str(value))
    return aliases


def _payload_party_size(payload: Mapping[str, Any]) -> int | None:
    if "party_size" in payload:
        return _int_count(_value(payload, "party_size", None), allow_none=True)
    if "people" in payload:
        people = _value(payload, "people", None)
        if isinstance(people, Mapping):
            return _int_count(_value(people, "adults", 0)) + _children_count(_value(people, "children", 0))
        if isinstance(people, list):
            return len(people)
        return _int_count(people, allow_none=True)
    return None


def _same_time(left: str, right: str) -> bool:
    left_minutes = _time_to_minutes(left)
    right_minutes = _time_to_minutes(right)
    if left_minutes is None or right_minutes is None:
        return left == right
    return left_minutes == right_minutes


def _time_in_range(time_value: str, start: str, end: str) -> bool:
    time_minutes = _time_to_minutes(time_value)
    start_minutes = _time_to_minutes(start)
    end_minutes = _time_to_minutes(end)
    if time_minutes is None or start_minutes is None or end_minutes is None:
        return False
    if start_minutes <= end_minutes:
        return start_minutes <= time_minutes <= end_minutes
    return time_minutes >= start_minutes or time_minutes <= end_minutes


def _time_to_minutes(value: str) -> int | None:
    parts = str(value).strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def _int_count(value: Any, allow_none: bool = False) -> int | None:
    if allow_none and value is None:
        return None
    if isinstance(value, bool):
        return 0
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return max(count, 0)


def _payload_place_id(payload: Mapping[str, Any]) -> str:
    value = _value(payload, "place_id", "") or _value(payload, "shop_id", "")
    return str(value) if value else ""


def _payload_time(payload: Mapping[str, Any]) -> str:
    value = _value(payload, "time", "") or _value(payload, "pickup_time", "") or _value(payload, "reservation_time", "")
    return str(value) if value else ""


def _is_reservation_or_order(action: Mapping[str, Any]) -> bool:
    label = f"{_value(action, 'tool', '')} {_value(action, 'type', '')}".lower()
    return "reservation" in label or "reserve" in label or "order" in label


def _is_restaurant(step: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    return _step_type(step) == "restaurant" or str(_value(candidate, "category", "")).lower() == "restaurant"


def _is_rain(weather: Mapping[str, Any]) -> bool:
    return str(_value(weather, "condition", "")).lower() == "rain"


def _step_type(step: Mapping[str, Any]) -> str:
    return str(_value(step, "type", "")).lower()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "__dict__"):
        return value.__dict__
    return {}


def _value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)
