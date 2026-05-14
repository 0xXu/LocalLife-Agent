from __future__ import annotations

from typing import Any

from backend.data.catalog import LocalDataCatalog
from backend.models.schemas import ParsedConstraints
from backend.tools.registry import LocalToolRegistry


def _is_weather_safe(poi: dict[str, Any], weather: dict[str, Any] | None) -> bool:
    """Return False if weather is rainy AND POI is outdoor-only (no indoor/rain_safe)."""
    if weather is None:
        return True
    condition = weather.get("condition", "clear")
    if condition != "rain":
        return True
    tags = set(poi.get("tags", []))
    if "outdoor" in tags and "indoor" not in tags and "rain_safe" not in tags:
        return False
    return True


def _preference_boost(poi: dict[str, Any], user_preferences: dict[str, Any] | None) -> float:
    """Return a float score reflecting how many POI tags overlap with user preferences."""
    if not user_preferences:
        return 0.0
    poi_tags = set(poi.get("tags", []))
    preferred: set[str] = set()
    for key in ("activity", "diet"):
        for tag in user_preferences.get(key, []):
            if isinstance(tag, str):
                preferred.add(tag)
    return float(len(poi_tags & preferred))


def _apply_context(
    items: list[dict[str, Any]],
    weather: dict[str, Any] | None = None,
    user_preferences: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Filter by weather safety and sort by preference boost + rating."""
    filtered = [item for item in items if _is_weather_safe(item, weather)]
    if user_preferences:
        filtered = sorted(
            filtered,
            key=lambda poi: (_preference_boost(poi, user_preferences), float(poi.get("rating", 4.0))),
            reverse=True,
        )
    return filtered


def search_activities(
    catalog: LocalDataCatalog,
    constraints: ParsedConstraints,
    *,
    weather: dict[str, Any] | None = None,
    user_preferences: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    activity_tags = list(constraints.preferences.get("activity", []))
    tools = LocalToolRegistry(catalog)
    result = tools.search_places(constraints.scenario, radius, activity_tags)
    return _apply_context(result.output["items"], weather, user_preferences)


def search_restaurants(
    catalog: LocalDataCatalog,
    constraints: ParsedConstraints,
    *,
    weather: dict[str, Any] | None = None,
    user_preferences: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    restaurant_tags = list(constraints.preferences.get("diet", [])) or ["booking_supported"]
    tools = LocalToolRegistry(catalog)
    result = tools.search_restaurants(constraints.scenario, radius, restaurant_tags)
    return _apply_context(result.output["items"], weather, user_preferences)


def search_walks(
    catalog: LocalDataCatalog,
    constraints: ParsedConstraints,
    *,
    weather: dict[str, Any] | None = None,
    user_preferences: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    walks = catalog.search_pois("dessert_walk", None, radius, ["walkable"])[:6]
    if not walks:
        tools = LocalToolRegistry(catalog)
        result = tools.search_places("date" if constraints.scenario == "date" else "family", radius, ["walkable"])
        walks = result.output["items"]
    return _apply_context(walks, weather, user_preferences)
