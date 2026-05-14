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
            self._schema("get_poi_details", False, ["poi_id"], "POI"),
            self._schema("check_weather", False, ["date_key"], "weather"),
            self._schema("check_opening_hours", False, ["poi_id", "time"], "opening_status"),
            self._schema("search_alternatives", False, ["category", "exclude_ids", "radius_km", "tags"], "POI[]"),
            self._schema("estimate_cost", False, ["poi_id", "party_size"], "cost_estimate"),
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
        legacy_category = {
            "family": "family_activity",
            "friends": "social_activity",
            "date": "date_activity",
            "rainy_indoor": "indoor_activity",
        }.get(scenario)
        broad_search = bool(set(tags) - {"child_friendly", "not_too_tiring", "social", "photo", "quiet", "romantic", "indoor", "rain_safe"})
        scenario_filter = scenario if legacy_category and not broad_search else None
        category_filter = legacy_category if legacy_category and not broad_search else None
        items = self.catalog.search_pois(category_filter, scenario_filter, radius_km, tags)
        activities = [item for item in items if item["category"] not in {"restaurant", "dessert_walk"}]
        if not activities:
            activities = [
                item for item in self.catalog.search_pois(None, None, radius_km, tags)
                if item["category"] not in {"restaurant", "dessert_walk"}
            ]
        if not activities:
            activities = [
                item for item in self.catalog.search_pois(None, None, radius_km, [])
                if item["category"] not in {"restaurant", "dessert_walk"}
            ]
        return ToolResult("search_places", {"items": activities[:8]})

    def search_restaurants(self, scenario: str, radius_km: float, tags: list[str]) -> ToolResult:
        scenario_filter = scenario if scenario in {"family", "friends", "date", "rainy_indoor"} else None
        items = self.catalog.search_pois("restaurant", scenario_filter, radius_km, tags)
        if not items and scenario_filter:
            items = self.catalog.search_pois("restaurant", None, radius_km, tags)
        return ToolResult("search_restaurants", {"items": items[:8]})

    def check_availability(self, place_id: str, time: str, party_size: int) -> ToolResult:
        poi = self.catalog.get_poi(place_id)
        if not poi["booking_supported"]:
            return ToolResult("check_availability", {"available": True, "slot": time, "party_size": party_size, "source": "walk_in"})
        for slot in poi.get("availability", []):
            if slot.get("time") == time and int(slot.get("capacity", 0)) >= party_size:
                return ToolResult("check_availability", {"available": bool(slot.get("available")), "slot": time, "party_size": party_size, "source": "mock_availability"})
        for slot in poi.get("availability", []):
            if bool(slot.get("available")) and int(slot.get("capacity", 0)) >= party_size:
                return ToolResult("check_availability", {"available": True, "slot": slot.get("time"), "requested_slot": time, "party_size": party_size, "source": "mock_availability_nearest"})
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

    def build_itinerary(self, constraints: ParsedConstraints, activity: dict, restaurant: dict | None = None, walk: dict | None = None) -> ToolResult:
        items = [item for item in [activity, restaurant, walk] if item]
        budget = sum(int(item["avg_price"]) for item in items)
        score = calculate_itinerary_score(items, constraints, budget)
        return ToolResult(
            "build_itinerary",
            {
                "summary": " + ".join(item["name"] for item in items),
                "estimated_budget": budget,
                "score": score,
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

    def get_poi_details(self, poi_id: str) -> ToolResult:
        """Get full details of a single POI."""
        poi = self.catalog.get_poi(poi_id)
        return ToolResult("get_poi_details", dict(poi))

    def check_weather(self, date_key: str = "today") -> ToolResult:
        """Get weather for a date."""
        weather = dict(self.catalog.weather.get(date_key, self.catalog.weather["today"]))
        return ToolResult("check_weather", weather)

    def check_opening_hours(self, poi_id: str, time: str) -> ToolResult:
        """Check if a POI is open at a given time."""
        poi = self.catalog.get_poi(poi_id)
        is_open = False
        for hours in poi.get("open_hours", []):
            start = hours.get("start", "00:00")
            end = hours.get("end", "23:59")
            if start <= time <= end:
                is_open = True
                break
        return ToolResult("check_opening_hours", {
            "poi_id": poi_id,
            "time": time,
            "is_open": is_open,
            "open_hours": poi.get("open_hours", []),
        })

    def search_alternatives(self, category: str, exclude_ids: list[str], radius_km: float, tags: list[str]) -> ToolResult:
        """Search for alternative POIs, excluding specified IDs."""
        items = self.catalog.search_pois(category, None, radius_km, tags)
        filtered = [item for item in items if item["id"] not in set(exclude_ids)]
        return ToolResult("search_alternatives", {"items": filtered[:8]})

    def estimate_cost(self, poi_id: str, party_size: int) -> ToolResult:
        """Estimate total cost for a POI visit."""
        poi = self.catalog.get_poi(poi_id)
        per_person = int(poi.get("avg_price", 100))
        total = per_person * party_size
        return ToolResult("estimate_cost", {
            "poi_id": poi_id,
            "party_size": party_size,
            "per_person": per_person,
            "total_cost": total,
        })

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


def calculate_itinerary_score(items: list[dict], constraints: ParsedConstraints, budget: int) -> int:
    if not items:
        return 60
    avg_rating = sum(float(item.get("rating", 4.0)) for item in items) / len(items)
    avg_distance = sum(float(item.get("distance_km", 5.0)) for item in items) / len(items)
    avg_wait = sum(int(item.get("wait_minutes", 15)) for item in items) / len(items)
    radius = max(float(constraints.constraints.get("radius_km", 5)), 1.0)
    max_wait = max(int(constraints.constraints.get("max_wait_minutes", 15)), 1)
    preferred_tags = set(constraints.preferences.get("activity", [])) | set(constraints.preferences.get("diet", []))
    matched_tags = sum(len(preferred_tags & set(item.get("tags", []))) for item in items)

    rating_score = (avg_rating / 5) * 40
    distance_score = max(0.0, 1 - avg_distance / radius) * 18
    wait_score = max(0.0, 1 - avg_wait / max_wait) * 14
    preference_score = min(14, matched_tags * 3)
    budget_score = budget_fit_score(str(constraints.preferences.get("budget_level", "medium")), budget)
    score = round(30 + rating_score + distance_score + wait_score + preference_score + budget_score)
    return max(60, min(98, score))


def budget_fit_score(level: str, budget: int) -> int:
    if level == "low":
        return 8 if budget <= 500 else 3 if budget <= 800 else 0
    if level == "high":
        return 8 if budget <= 1600 else 4
    return 8 if budget <= 1000 else 3 if budget <= 1400 else 0
