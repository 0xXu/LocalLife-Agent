from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LocalDataCatalog:
    pois: list[dict] = field(default_factory=list)
    coupons: list[dict] = field(default_factory=list)
    menus: list[dict] = field(default_factory=list)
    weather: dict[str, dict] = field(default_factory=dict)
    route_matrix: dict[str, dict] = field(default_factory=dict)
    failure_scenarios: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.pois:
            return
        self.pois = build_pois()
        self.coupons = build_coupons(self.pois)
        self.menus = build_menus(self.pois)
        self.weather = {
            "today": {"condition": "clear", "temperature": 24, "rain_probability": 0.1},
            "rainy": {"condition": "rain", "temperature": 20, "rain_probability": 0.86},
        }
        self.route_matrix = build_route_matrix(self.pois)
        self.failure_scenarios = [
            {"id": "restaurant_unavailable", "type": "availability", "target_category": "restaurant"},
            {"id": "activity_full", "type": "availability", "target_category": "activity"},
            {"id": "rain", "type": "weather", "target_category": "outdoor"},
            {"id": "route_timeout", "type": "route", "target_category": "itinerary"},
            {"id": "budget_overrun", "type": "budget", "target_category": "plan"},
        ]

    def search_pois(self, category: str | None = None, scenario: str | None = None, radius_km: float = 8, tags: list[str] | None = None) -> list[dict]:
        tags = tags or []
        results = [
            poi for poi in self.pois
            if (category is None or poi["category"] == category)
            and poi["distance_km"] <= radius_km
            and (scenario is None or scenario in poi["supported_scenarios"])
        ]
        return sorted(
            results,
            key=lambda poi: (
                sum(tag in poi["tags"] for tag in tags),
                poi["rating"],
                -poi["wait_minutes"],
                -poi["distance_km"],
            ),
            reverse=True,
        )

    def get_poi(self, poi_id: str) -> dict:
        for poi in self.pois:
            if poi["id"] == poi_id:
                return dict(poi)
        raise KeyError(poi_id)

    def coupons_for(self, poi_id: str) -> list[dict]:
        return [dict(item) for item in self.coupons if item["poi_id"] == poi_id]

    def menu_for(self, poi_id: str) -> list[dict]:
        return [dict(item) for item in self.menus if item["poi_id"] == poi_id]


def build_pois() -> list[dict]:
    templates = [
        ("family_activity", "亲子科学馆", ["family"], ["child_friendly", "indoor", "science"], "适合 4 到 8 岁儿童，室内路线轻松。"),
        ("family_activity", "儿童手作乐园", ["family", "rainy_indoor"], ["child_friendly", "indoor", "craft"], "有亲子手作课，雨天也稳定。"),
        ("social_activity", "城市桌游咖啡馆", ["friends", "rainy_indoor"], ["social", "indoor", "group_friendly"], "适合朋友聊天和轻量桌游。"),
        ("social_activity", "复古拍照街区", ["friends", "date"], ["photo", "walkable", "social"], "拍照点密集，适合朋友或情侣。"),
        ("date_activity", "安静艺术展", ["date", "rainy_indoor"], ["quiet", "indoor", "romantic"], "安静、有氛围，排队风险低。"),
        ("indoor_activity", "商场室内体验馆", ["rainy_indoor", "family", "friends"], ["indoor", "rain_safe", "nearby"], "雨天可替代户外节点。"),
        ("restaurant", "绿荫轻食餐厅", ["family", "friends", "date", "rainy_indoor"], ["low_fat", "healthy", "booking_supported", "child_seat"], "低脂菜单和儿童座椅都可用。"),
        ("restaurant", "轻碗健康餐厅", ["family", "friends", "rainy_indoor"], ["low_fat", "healthy", "fallback", "group_friendly"], "主餐厅无位时的健康备选。"),
        ("restaurant", "小巷氛围餐厅", ["date", "friends"], ["romantic", "quiet", "booking_supported"], "灯光安静，适合约会。"),
        ("dessert_walk", "河畔低糖甜品散步", ["family", "friends", "date"], ["low_sugar", "walkable", "photo"], "饭后短距离散步和低糖甜品。"),
    ]
    pois: list[dict] = []
    idx = 1
    for cycle in range(9):
        for category, base_name, scenarios, tags, reason in templates:
            idx_text = f"{idx:03d}"
            pois.append(
                {
                    "id": f"poi_{idx_text}",
                    "name": f"{base_name}{cycle + 1}号店",
                    "category": category,
                    "lat": round(38.25 + (idx % 17) * 0.0017, 6),
                    "lng": round(140.87 + (idx % 19) * 0.0013, 6),
                    "distance_km": round(1.2 + (idx % 50) * 0.11, 2),
                    "rating": round(4.1 + (idx % 9) * 0.08, 2),
                    "review_count": 180 + idx * 17,
                    "avg_price": 80 + (idx % 8) * 35 if category != "restaurant" else 180 + (idx % 7) * 40,
                    "tags": list(dict.fromkeys(tags + ["nearby"])),
                    "duration_minutes": 110 if "activity" in category else 60 if category == "restaurant" else 35,
                    "open_hours": [{"day": "sat", "start": "10:00", "end": "22:00"}],
                    "wait_minutes": idx % 16,
                    "booking_supported": category != "dessert_walk",
                    "availability": [
                        {"time": "13:30", "available": True, "capacity": 6},
                        {"time": "15:45", "available": idx % 11 != 0, "capacity": 6},
                        {"time": "18:00", "available": idx % 7 != 0, "capacity": 4},
                    ],
                    "source": "local_seed_catalog",
                    "reason": reason,
                    "risk_tags": ["weekend_queue"] if idx % 6 == 0 else [],
                    "supported_scenarios": scenarios,
                }
            )
            idx += 1
    return pois[:90]


def build_coupons(pois: list[dict]) -> list[dict]:
    restaurants = [poi for poi in pois if poi["category"] == "restaurant"]
    coupons = []
    for index, poi in enumerate(restaurants[:24], start=1):
        coupons.append(
            {
                "id": f"deal_{index:03d}",
                "poi_id": poi["id"],
                "title": f"{poi['name']} 双人/多人套餐券",
                "price": max(60, poi["avg_price"] - 40),
                "face_value": poi["avg_price"] + 80,
                "rules": "周末可用，需到店核销，不支持真实支付。",
                "valid_until": "2026-12-31",
            }
        )
    return coupons


def build_menus(pois: list[dict]) -> list[dict]:
    menu = []
    for index, poi in enumerate([item for item in pois if item["category"] == "restaurant"], start=1):
        menu.extend(
            [
                {"id": f"menu_{index:03d}_a", "poi_id": poi["id"], "name": "低脂鸡胸沙拉", "price": 48, "tags": ["low_fat"]},
                {"id": f"menu_{index:03d}_b", "poi_id": poi["id"], "name": "儿童友好主食", "price": 38, "tags": ["child_friendly"]},
                {"id": f"menu_{index:03d}_c", "poi_id": poi["id"], "name": "低糖饮品", "price": 22, "tags": ["low_sugar"]},
            ]
        )
    return menu


def build_route_matrix(pois: list[dict]) -> dict[str, dict]:
    route = {}
    for left in pois[:35]:
        route[left["id"]] = {}
        for right in pois[:35]:
            distance = abs(float(left["distance_km"]) - float(right["distance_km"])) + 0.6
            route[left["id"]][right["id"]] = {
                "mode": "walk" if distance < 1.5 else "taxi",
                "minutes": int(distance * (9 if distance < 1.5 else 7)) + 3,
                "distance_km": round(distance, 2),
            }
    return route
