from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.schemas import ItineraryStep, ParsedConstraints


@dataclass
class ValidationReport:
    valid: bool
    issues: list[dict] = field(default_factory=list)


def validate_itinerary(
    steps: list[ItineraryStep],
    constraints: ParsedConstraints,
    candidate_lookup: dict[str, dict],
    weather: dict,
    route: dict,
) -> ValidationReport:
    issues: list[dict] = []
    for step in steps:
        if step.type == "transport":
            continue
        candidate = candidate_lookup.get(step.place_id, {})
        if not is_open_at(candidate.get("open_hours", []), step.start):
            issues.append({"code": "closed_at_visit_time", "place_id": step.place_id, "time": step.start})
        if weather.get("condition") == "rain" and "outdoor" in candidate.get("tags", []):
            issues.append({"code": "weather_mismatch", "place_id": step.place_id})
    if int(route.get("total_travel_minutes", 0)) > int(float(constraints.time_window.get("duration_hours", 4)) * 60):
        issues.append({"code": "route_timeout", "minutes": route.get("total_travel_minutes")})
    budget = sum(int(candidate_lookup.get(step.place_id, {}).get("avg_price", 0)) for step in steps)
    if str(constraints.preferences.get("budget_level", "medium")) == "low" and budget > 500:
        issues.append({"code": "budget_overrun", "budget": budget})
    return ValidationReport(valid=not issues, issues=issues)


def is_open_at(open_hours: list[dict], time_value: str) -> bool:
    if not open_hours:
        return True
    for item in open_hours:
        if str(item.get("start", "00:00")) <= time_value <= str(item.get("end", "23:59")):
            return True
    return False
