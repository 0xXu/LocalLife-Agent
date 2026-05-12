from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Provenance:
    source: str
    freshness: str
    confidence: float
    retrieved_at: str = "seed"
    raw_ref: str = ""


@dataclass
class GroundedPlace:
    id: str
    name: str
    category: str
    lat: float
    lng: float
    distance_km: float
    rating: float
    avg_price: int
    tags: list[str]
    reason: str
    risk_tags: list[str]
    open_hours: list[dict[str, str]]
    wait_minutes: int
    booking_supported: bool
    availability: list[dict]
    supported_scenarios: list[str]
    provenance: Provenance

    def as_poi_dict(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "lat": self.lat,
            "lng": self.lng,
            "distance_km": self.distance_km,
            "rating": self.rating,
            "avg_price": self.avg_price,
            "tags": list(self.tags),
            "reason": self.reason,
            "risk_tags": list(self.risk_tags),
            "open_hours": [dict(item) for item in self.open_hours],
            "wait_minutes": self.wait_minutes,
            "booking_supported": self.booking_supported,
            "availability": [dict(item) for item in self.availability],
            "supported_scenarios": list(self.supported_scenarios),
            "source": self.provenance.source,
            "provenance": {
                "source": self.provenance.source,
                "freshness": self.provenance.freshness,
                "confidence": self.provenance.confidence,
                "retrieved_at": self.provenance.retrieved_at,
                "raw_ref": self.provenance.raw_ref,
            },
        }
        data["duration_minutes"] = 110 if "activity" in self.category else 60 if self.category == "restaurant" else 35
        data["review_count"] = 100
        return data


@dataclass
class PlaceSearchResult:
    query: str
    tags: list[str]
    radius_km: float
    items: list[GroundedPlace]
    rejected: list[dict] = field(default_factory=list)


@dataclass
class GroundedRoute:
    legs: list[dict]
    total_travel_minutes: int
    walking_distance_km: float
    drive_time_minutes: int
    polyline: dict
    provider: str
    provenance: Provenance


@dataclass
class GroundedAvailability:
    place_id: str
    slot: str
    available: bool
    party_size: int
    provenance: Provenance


@dataclass
class GroundedWeather:
    condition: str
    temperature: int
    rain_probability: float
    provenance: Provenance


class PlaceProvider(Protocol):
    def search(self, query: str, tags: list[str], radius_km: float, limit: int) -> PlaceSearchResult:
        ...


class RouteProvider(Protocol):
    def optimize(self, waypoints: list[GroundedPlace]) -> GroundedRoute:
        ...


class AvailabilityProvider(Protocol):
    def check(self, place_id: str, time: str, party_size: int) -> GroundedAvailability:
        ...


class WeatherProvider(Protocol):
    def current(self, rainy: bool = False) -> GroundedWeather:
        ...
