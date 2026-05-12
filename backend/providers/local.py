from __future__ import annotations

from backend.data.catalog import LocalDataCatalog
from backend.providers.contracts import GroundedAvailability, GroundedPlace, GroundedRoute, GroundedWeather, PlaceSearchResult, Provenance


class LocalPlaceProvider:
    def __init__(self, catalog: LocalDataCatalog) -> None:
        self.catalog = catalog

    def search(self, query: str, tags: list[str], radius_km: float, limit: int) -> PlaceSearchResult:
        raw_items = self.catalog.search_pois(None, None, radius_km, tags)
        items = [ground_place(item, confidence_for_tags(item, tags)) for item in raw_items[:limit]]
        rejected = [
            {"id": item["id"], "reason": "outside_limit"}
            for item in raw_items[limit:limit + 8]
        ]
        return PlaceSearchResult(query=query, tags=list(tags), radius_km=radius_km, items=items, rejected=rejected)


class LocalRouteProvider:
    def __init__(self, catalog: LocalDataCatalog) -> None:
        self.catalog = catalog

    def optimize(self, waypoints: list[GroundedPlace]) -> GroundedRoute:
        legs: list[dict] = []
        total = 0
        walking_km = 0.0
        for left, right in zip(waypoints, waypoints[1:]):
            leg = self.catalog.route_matrix.get(left.id, {}).get(right.id, {"mode": "taxi", "minutes": 12, "distance_km": 2.0})
            total += int(leg["minutes"])
            if leg["mode"] == "walk":
                walking_km += float(leg["distance_km"])
            legs.append({"from_id": left.id, "to_id": right.id, **leg})
        coords = [[item.lng, item.lat] for item in waypoints]
        if len(coords) == 1:
            lng, lat = coords[0]
            coords.append([lng + 0.002, lat + 0.002])
        if not coords:
            coords = [[140.8824, 38.2601], [140.8844, 38.2621]]
        return GroundedRoute(
            legs=legs,
            total_travel_minutes=total,
            walking_distance_km=round(walking_km, 2),
            drive_time_minutes=total or 12,
            polyline={"type": "LineString", "coordinates": coords},
            provider="local_seed_route_matrix",
            provenance=Provenance("local_seed_route_matrix", "seed_static", 0.72),
        )


class LocalAvailabilityProvider:
    def __init__(self, catalog: LocalDataCatalog) -> None:
        self.catalog = catalog

    def check(self, place_id: str, time: str, party_size: int) -> GroundedAvailability:
        poi = self.catalog.get_poi(place_id)
        for slot in poi.get("availability", []):
            if slot.get("time") == time and int(slot.get("capacity", 0)) >= party_size:
                return GroundedAvailability(place_id, time, bool(slot.get("available")), party_size, Provenance("mock_availability", "seed_static", 0.68))
        return GroundedAvailability(place_id, time, True, party_size, Provenance("mock_availability_nearest", "seed_static", 0.55))


class LocalWeatherProvider:
    def __init__(self, catalog: LocalDataCatalog) -> None:
        self.catalog = catalog

    def current(self, rainy: bool = False) -> GroundedWeather:
        data = self.catalog.weather["rainy" if rainy else "today"]
        return GroundedWeather(
            condition=str(data["condition"]),
            temperature=int(data["temperature"]),
            rain_probability=float(data["rain_probability"]),
            provenance=Provenance("local_weather_seed", "seed_static", 0.7),
        )


def ground_place(item: dict, confidence: float) -> GroundedPlace:
    return GroundedPlace(
        id=item["id"],
        name=item["name"],
        category=item["category"],
        lat=float(item["lat"]),
        lng=float(item["lng"]),
        distance_km=float(item["distance_km"]),
        rating=float(item["rating"]),
        avg_price=int(item["avg_price"]),
        tags=list(item["tags"]),
        reason=item["reason"],
        risk_tags=list(item.get("risk_tags", [])),
        open_hours=[dict(value) for value in item["open_hours"]],
        wait_minutes=int(item.get("wait_minutes", 0)),
        booking_supported=bool(item.get("booking_supported", False)),
        availability=[dict(value) for value in item.get("availability", [])],
        supported_scenarios=list(item.get("supported_scenarios", [])),
        provenance=Provenance(item.get("source", "local_seed_catalog"), "seed_static", confidence, raw_ref=item["id"]),
    )


def confidence_for_tags(item: dict, tags: list[str]) -> float:
    if not tags:
        return 0.55
    matched = sum(tag in item.get("tags", []) for tag in tags)
    return round(min(0.95, 0.5 + matched / max(len(tags), 1) * 0.45), 2)
