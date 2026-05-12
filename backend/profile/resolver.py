from __future__ import annotations

from copy import deepcopy

from backend.models.schemas import ParsedConstraints
from backend.profile.models import UserProfile


def merge_profile_into_goal_context(constraints: ParsedConstraints, profile: UserProfile | None) -> ParsedConstraints:
    if profile is None:
        return constraints
    merged = deepcopy(constraints)
    apply_if_missing(merged.preferences, "pace", profile.preference_value("pace"))
    apply_if_missing(merged.preferences, "transport", profile.preference_value("transport"))
    apply_if_missing(merged.preferences, "diet", list_values(profile, "diet"))
    avoid_values = list_values(profile, "avoid")
    if avoid_values and not merged.constraints.get("avoid"):
        merged.constraints["avoid"] = avoid_values
    if not merged.preferences.get("budget_level"):
        budget = profile.preference_value("budget_level")
        if budget:
            merged.preferences["budget_level"] = budget
    return merged


def apply_if_missing(target: dict, key: str, value) -> None:
    if value in (None, "", []):
        return
    if key not in target or target.get(key) in (None, "", []):
        target[key] = value


def list_values(profile: UserProfile, key: str) -> list:
    return [preference.value for preference in profile.preferences_by_key(key) if preference.confidence >= 0.65]
