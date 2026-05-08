from __future__ import annotations

from backend.models.schemas import POI


class RoutingTool:
    def optimize(self, waypoints: list[POI]) -> dict[str, object]:
        names = [poi.name for poi in waypoints]
        return {
            "route": names,
            "drive_time": "约 25 分钟",
            "walking_distance": "1.2 公里",
            "segments": [
                {"from": "家", "to": names[0], "mode": "taxi", "minutes": 12},
                {"from": names[0], "to": names[1], "mode": "walk", "minutes": 5},
                {"from": names[1], "to": names[2], "mode": "walk", "minutes": 7},
            ],
        }

