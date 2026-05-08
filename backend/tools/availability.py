from __future__ import annotations

from backend.models.schemas import POI


class AvailabilityTool:
    def check(self, poi: POI, time: str, party_size: int) -> dict[str, object]:
        if not poi.booking_supported:
            return {"available": True, "slot": time, "party_size": party_size, "source": "walk_in"}
        for slot in poi.availability:
            if slot.get("time") == time:
                return {
                    "available": bool(slot.get("available")),
                    "slot": time,
                    "party_size": party_size,
                    "source": "mock_availability",
                }
        return {
            "available": False,
            "slot": time,
            "party_size": party_size,
            "source": "mock_availability",
        }

