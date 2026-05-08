from __future__ import annotations

import json
from pathlib import Path

from backend.models.schemas import POI


class POIRepository:
    def __init__(self, seed_path: Path | None = None) -> None:
        self.seed_path = seed_path or Path(__file__).resolve().parents[1] / "data" / "poi_seed.json"
        self._pois = self._load()

    def _load(self) -> list[POI]:
        data = json.loads(self.seed_path.read_text(encoding="utf-8"))
        return [POI(**item) for item in data]

    def search(self, category: str, radius_km: float, tags: list[str] | None = None) -> list[POI]:
        tags = tags or []
        results = [
            poi for poi in self._pois
            if poi.category == category and poi.distance_km <= radius_km
        ]
        if tags:
            results.sort(key=lambda poi: sum(tag in poi.tags for tag in tags), reverse=True)
        return [copy_poi(poi) for poi in results]

    def get(self, poi_id: str) -> POI:
        for poi in self._pois:
            if poi.id == poi_id:
                return copy_poi(poi)
        raise KeyError(f"Unknown POI: {poi_id}")


def copy_poi(poi: POI) -> POI:
    return POI(
        id=poi.id,
        name=poi.name,
        category=poi.category,
        lat=poi.lat,
        lng=poi.lng,
        distance_km=poi.distance_km,
        rating=poi.rating,
        avg_price=poi.avg_price,
        tags=list(poi.tags),
        duration_minutes=poi.duration_minutes,
        open_hours=[dict(item) for item in poi.open_hours],
        wait_minutes=poi.wait_minutes,
        booking_supported=poi.booking_supported,
        availability=[dict(item) for item in poi.availability],
        source=poi.source,
        reason=poi.reason,
    )

