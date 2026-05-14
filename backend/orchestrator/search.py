from __future__ import annotations

from typing import Any

from backend.data.catalog import LocalDataCatalog
from backend.models.schemas import ParsedConstraints
from backend.tools.registry import LocalToolRegistry


def search_activities(catalog: LocalDataCatalog, constraints: ParsedConstraints) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    activity_tags = list(constraints.preferences.get("activity", []))
    tools = LocalToolRegistry(catalog)
    result = tools.search_places(constraints.scenario, radius, activity_tags)
    return result.output["items"]


def search_restaurants(catalog: LocalDataCatalog, constraints: ParsedConstraints) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    restaurant_tags = list(constraints.preferences.get("diet", [])) or ["booking_supported"]
    tools = LocalToolRegistry(catalog)
    result = tools.search_restaurants(constraints.scenario, radius, restaurant_tags)
    return result.output["items"]


def search_walks(catalog: LocalDataCatalog, constraints: ParsedConstraints) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    walks = catalog.search_pois("dessert_walk", None, radius, ["walkable"])[:6]
    if not walks:
        tools = LocalToolRegistry(catalog)
        result = tools.search_places("date" if constraints.scenario == "date" else "family", radius, ["walkable"])
        walks = result.output["items"]
    return walks
