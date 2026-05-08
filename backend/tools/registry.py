from __future__ import annotations

from backend.data.catalog import LocalDataCatalog
from backend.models.schemas import ParsedConstraints, PlanAction, ToolResult, to_dict


class LocalToolRegistry:
    def __init__(self, catalog: LocalDataCatalog | None = None) -> None:
        self.catalog = catalog or LocalDataCatalog()

    def schemas(self) -> list[dict]:
        return [
            self._schema("parse_user_goal", False, ["text", "current_time"], "ParsedConstraints"),
            self._schema("get_weather", False, ["location", "time"], "weather"),
            self._schema("search_places", False, ["category", "constraints"], "POI[]"),
            self._schema("search_restaurants", False, ["cuisine", "diet", "party_size"], "POI[]"),
            self._schema("check_availability", False, ["place_id", "time", "party_size"], "availability"),
            self._schema("optimize_route", False, ["origin", "waypoints"], "route"),
            self._schema("build_itinerary", False, ["candidates", "constraints"], "itinerary"),
            self._schema("validate_plan", False, ["itinerary", "constraints"], "validation_report"),
            self._schema("compare_alternatives", False, ["itinerary_a", "itinerary_b"], "diff_report"),
            self._schema("reserve_activity", True, ["place_id", "time", "people"], "ticket_id"),
            self._schema("create_reservation", True, ["place_id", "time", "people"], "reservation_id"),
            self._schema("claim_coupon", True, ["deal_id", "user_id"], "coupon_id"),
            self._schema("create_order", True, ["shop_id", "items", "pickup_time"], "order_id"),
            self._schema("send_plan_message", True, ["recipient", "message"], "message_id"),
            self._schema("create_calendar_event", True, ["itinerary", "participants"], "event_id"),
        ]

    def _schema(self, name: str, side_effect: bool, inputs: list[str], output: str) -> dict:
        return {"name": name, "input": inputs, "output": output, "side_effect": side_effect, "requires_confirmation": side_effect}

    def get_weather(self, rainy: bool = False) -> ToolResult:
        key = "rainy" if rainy else "today"
        return ToolResult("get_weather", dict(self.catalog.weather[key]))

    def search_places(self, scenario: str, radius_km: float, tags: list[str]) -> ToolResult:
        category = {
            "family": "family_activity",
            "friends": "social_activity",
            "date": "date_activity",
            "rainy_indoor": "indoor_activity",
        }.get(scenario, "family_activity")
        return ToolResult("search_places", {"items": self.catalog.search_pois(category, scenario, radius_km, tags)[:8]})

    def search_restaurants(self, scenario: str, radius_km: float, tags: list[str]) -> ToolResult:
        return ToolResult("search_restaurants", {"items": self.catalog.search_pois("restaurant", scenario, radius_km, tags)[:8]})

    def check_availability(self, place_id: str, time: str, party_size: int) -> ToolResult:
        poi = self.catalog.get_poi(place_id)
        if not poi["booking_supported"]:
            return ToolResult("check_availability", {"available": True, "slot": time, "party_size": party_size, "source": "walk_in"})
        for slot in poi.get("availability", []):
            if slot.get("time") == time and int(slot.get("capacity", 0)) >= party_size:
                return ToolResult("check_availability", {"available": bool(slot.get("available")), "slot": time, "party_size": party_size, "source": "mock_availability"})
        return ToolResult("check_availability", {"available": False, "slot": time, "party_size": party_size, "source": "mock_availability"})

    def optimize_route(self, waypoints: list[dict]) -> ToolResult:
        total_minutes = 0
        walking_km = 0.0
        legs = []
        for left, right in zip(waypoints, waypoints[1:]):
            leg = self.catalog.route_matrix.get(left["id"], {}).get(right["id"])
            if not leg:
                leg = {"mode": "taxi", "minutes": 12, "distance_km": 2.0}
            total_minutes += int(leg["minutes"])
            if leg["mode"] == "walk":
                walking_km += float(leg["distance_km"])
            legs.append({"from_id": left["id"], "to_id": right["id"], **leg})
        return ToolResult("optimize_route", {"legs": legs, "total_travel_minutes": total_minutes, "walking_distance": f"{walking_km:.1f} 公里", "drive_time": f"约 {max(total_minutes, 12)} 分钟"})

    def build_itinerary(self, constraints: ParsedConstraints, activity: dict, restaurant: dict, walk: dict) -> ToolResult:
        budget = activity["avg_price"] + restaurant["avg_price"] + walk["avg_price"]
        return ToolResult(
            "build_itinerary",
            {
                "summary": f"{activity['name']} + {restaurant['name']} + {walk['name']}",
                "estimated_budget": budget,
                "score": 91,
            },
        )

    def validate_plan(self, available: bool, total_minutes: int, budget: int) -> ToolResult:
        issues = []
        if not available:
            issues.append("restaurant_unavailable")
        if total_minutes > 360:
            issues.append("route_timeout")
        if budget > 1200:
            issues.append("budget_overrun")
        return ToolResult("validate_plan", {"valid": not issues, "issues": issues})

    def compare_alternatives(self, before: str, after: str, reason: str) -> ToolResult:
        return ToolResult("compare_alternatives", {"changed": reason.split("_")[0], "from": before, "to": after, "reason": reason})

    def execute_action(self, action: PlanAction) -> ToolResult:
        prefix = {
            "reserve_activity": "TKT",
            "create_reservation": "RES",
            "claim_coupon": "CPN",
            "create_order": "ORD",
            "send_plan_message": "MSG",
            "create_calendar_event": "CAL",
        }[action.tool]
        stable = abs(hash((action.tool, action.target, action.detail))) % 9000 + 1000
        return ToolResult(
            action.tool,
            {
                "id": f"{prefix}-{stable}",
                "status": "confirmed",
                "detail": f"{action.label}已完成：{action.target}",
                "payload": to_dict(action.payload),
            },
            side_effect=True,
        )
