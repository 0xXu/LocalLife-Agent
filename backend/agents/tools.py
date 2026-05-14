from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.tools.registry import LocalToolRegistry


@dataclass
class AgentContext:
    user_id: str
    locale: str = "zh-CN"


# --- Pydantic input schemas ---

class SearchPlacesInput(BaseModel):
    scenario: str = Field(description="Scenario label, e.g. 'family', 'date', 'hiking'")
    radius_km: float = Field(description="Search radius in kilometers", ge=0.5, le=20)
    tags: list[str] = Field(description="Filter tags, e.g. ['child_friendly', 'indoor']")


class GetPoiDetailsInput(BaseModel):
    poi_id: str = Field(description="Unique POI identifier")


class CheckAvailabilityInput(BaseModel):
    poi_id: str = Field(description="POI identifier")
    time: str = Field(description="Desired time, e.g. '14:00'")
    party_size: int = Field(description="Number of people", ge=1, le=20)


class ComparePoisInput(BaseModel):
    poi_ids: list[str] = Field(description="List of POI IDs to compare")
    criteria: list[str] = Field(description="Comparison criteria, e.g. ['price', 'rating', 'distance']")


class CheckWeatherInput(BaseModel):
    date_key: str = Field(description="Date key, e.g. 'today' or 'rainy'", default="today")


class CheckOpeningHoursInput(BaseModel):
    poi_id: str = Field(description="POI identifier")
    time: str = Field(description="Time to check, e.g. '14:00'")


class CheckRouteTimeInput(BaseModel):
    waypoint_ids: list[str] = Field(description="Ordered list of POI IDs as route waypoints")


class SearchAlternativesInput(BaseModel):
    category: str = Field(description="POI category, e.g. 'restaurant', 'social_activity'")
    exclude_ids: list[str] = Field(description="POI IDs to exclude from results")
    radius_km: float = Field(description="Search radius in kilometers", ge=0.5, le=20)
    tags: list[str] = Field(description="Filter tags")


class CompareOptionsInput(BaseModel):
    option_ids: list[str] = Field(description="POI IDs to compare as alternatives")
    original_id: str = Field(description="Original POI ID to compare against")


class EstimateCostInput(BaseModel):
    poi_id: str = Field(description="POI identifier")
    party_size: int = Field(description="Number of people", ge=1, le=20)


# --- Tool factories ---

def build_ranker_tools(registry: LocalToolRegistry, context: AgentContext) -> list:
    """Build read-only tools for RankerAgent."""

    @tool(args_schema=SearchPlacesInput)
    def search_places(scenario: str, radius_km: float, tags: list[str]) -> dict:
        """Search candidate POIs matching the scenario, radius, and tags. Use this to discover options before ranking."""
        result = registry.search_places(scenario, radius_km, tags)
        return result.output

    @tool(args_schema=GetPoiDetailsInput)
    def get_poi_details(poi_id: str) -> dict:
        """Get detailed information for one POI including opening hours, price, rating, risk tags, and availability."""
        try:
            result = registry.get_poi_details(poi_id)
            return result.output
        except KeyError:
            return {"ok": False, "error_code": "POI_NOT_FOUND", "message": f"No POI found: {poi_id}"}

    @tool(args_schema=CheckAvailabilityInput)
    def check_availability(poi_id: str, time: str, party_size: int) -> dict:
        """Check whether a POI has enough availability for rough ranking. Use this only for promising candidates."""
        result = registry.check_availability(poi_id, time, party_size)
        return result.output

    @tool(args_schema=ComparePoisInput)
    def compare_pois(poi_ids: list[str], criteria: list[str]) -> dict:
        """Compare multiple POIs by specified criteria (price, rating, distance, wait_time). Returns side-by-side comparison."""
        details = []
        for pid in poi_ids:
            try:
                poi = registry.get_poi_details(pid).output
                details.append({
                    "id": pid,
                    "name": poi.get("name", ""),
                    "rating": poi.get("rating", 0),
                    "avg_price": poi.get("avg_price", 0),
                    "distance_km": poi.get("distance_km", 0),
                    "wait_minutes": poi.get("wait_minutes", 0),
                    "tags": poi.get("tags", []),
                })
            except KeyError:
                details.append({"id": pid, "error": "not_found"})
        return {"comparison": details, "criteria": criteria}

    return [search_places, get_poi_details, check_availability, compare_pois]


def build_validator_tools(registry: LocalToolRegistry, context: AgentContext) -> list:
    """Build read-only tools for ValidatorAgent."""

    @tool(args_schema=CheckWeatherInput)
    def check_weather(date_key: str = "today") -> dict:
        """Get weather forecast for a date. Use to verify outdoor activities are weather-safe."""
        result = registry.check_weather(date_key)
        return result.output

    @tool(args_schema=CheckOpeningHoursInput)
    def check_opening_hours(poi_id: str, time: str) -> dict:
        """Strictly verify whether a POI is open at the exact planned time. Use for final validation."""
        try:
            result = registry.check_opening_hours(poi_id, time)
            return result.output
        except KeyError:
            return {"ok": False, "error_code": "POI_NOT_FOUND", "message": f"No POI found: {poi_id}"}

    @tool(args_schema=CheckAvailabilityInput)
    def check_availability(poi_id: str, time: str, party_size: int) -> dict:
        """Strictly verify whether the selected POI is available at the exact planned time and party size."""
        result = registry.check_availability(poi_id, time, party_size)
        return result.output

    @tool(args_schema=CheckRouteTimeInput)
    def check_route_time(waypoint_ids: list[str]) -> dict:
        """Check total route time for a list of waypoint POI IDs. Returns travel time breakdown."""
        waypoints = []
        for pid in waypoint_ids:
            try:
                poi = registry.get_poi_details(pid).output
                waypoints.append(poi)
            except KeyError:
                return {"ok": False, "error_code": "POI_NOT_FOUND", "message": f"No POI found: {pid}"}
        result = registry.optimize_route(waypoints)
        return result.output

    return [check_weather, check_opening_hours, check_availability, check_route_time]


def build_recovery_tools(registry: LocalToolRegistry, context: AgentContext) -> list:
    """Build read-only tools for RecoveryAgent."""

    @tool(args_schema=SearchAlternativesInput)
    def search_alternatives(category: str, exclude_ids: list[str], radius_km: float, tags: list[str]) -> dict:
        """Search for replacement POIs, excluding the ones already tried. Use when original plan fails."""
        result = registry.search_alternatives(category, exclude_ids, radius_km, tags)
        return result.output

    @tool(args_schema=CheckAvailabilityInput)
    def check_availability(poi_id: str, time: str, party_size: int) -> dict:
        """Check availability for replacement POIs before proposing them as recovery options."""
        result = registry.check_availability(poi_id, time, party_size)
        return result.output

    @tool(args_schema=CompareOptionsInput)
    def compare_options(option_ids: list[str], original_id: str) -> dict:
        """Compare alternative POIs against the original. Shows what changed."""
        all_ids = [original_id] + option_ids
        details = []
        for pid in all_ids:
            try:
                poi = registry.get_poi_details(pid).output
                details.append({
                    "id": pid,
                    "name": poi.get("name", ""),
                    "rating": poi.get("rating", 0),
                    "avg_price": poi.get("avg_price", 0),
                    "distance_km": poi.get("distance_km", 0),
                    "is_original": pid == original_id,
                })
            except KeyError:
                details.append({"id": pid, "error": "not_found"})
        return {"comparison": details}

    @tool(args_schema=EstimateCostInput)
    def estimate_cost(poi_id: str, party_size: int) -> dict:
        """Estimate total cost for a POI visit with given party size."""
        result = registry.estimate_cost(poi_id, party_size)
        return result.output

    return [search_alternatives, check_availability, compare_options, estimate_cost]
