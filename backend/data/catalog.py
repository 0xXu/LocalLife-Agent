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
        ("social_activity", "山野徒步步道", ["friends", "date"], ["hiking", "outdoor", "nature", "walkable", "group_friendly"], "适合三五好友轻徒步，沿途有观景点和补给点。"),
        ("social_activity", "近郊登山路线", ["friends", "family"], ["hiking", "mountain", "outdoor", "nature", "not_too_tiring"], "坡度适中，适合半天内完成的近郊登山。"),
        ("social_activity", "宠物友好河岸公园", ["pet_friendly_walk", "friends", "family"], ["pet", "outdoor", "walkable", "quiet", "nature"], "允许牵绳宠物进入，路面平缓，适合低噪音散步。"),
        ("social_activity", "自习咖啡馆", ["deep_work_cafe", "date", "friends"], ["work", "quiet", "cafe", "wifi", "indoor"], "有插座、Wi-Fi 和安静座位，适合写代码或自习。"),
        ("restaurant", "运动补给轻食吧", ["sports", "badminton", "friends", "family"], ["healthy", "protein", "low_fat", "booking_supported", "group_friendly"], "运动后适合补充蛋白质，座位周转快。"),
        ("social_activity", "社区羽毛球馆", ["badminton", "sports", "friends"], ["sports", "badminton", "indoor", "group_friendly"], "可预约场地，适合朋友运动和轻量出汗。"),
        ("social_activity", "生日布置拍照馆", ["birthday_surprise", "celebration", "date", "friends"], ["birthday", "celebration", "photo", "indoor"], "提供小型生日布置和拍照区域，适合惊喜安排。"),
        ("social_activity", "沉浸式剧本空间", ["mystery_game", "friends"], ["immersive", "mystery", "group_friendly", "indoor"], "适合朋友组局，节奏完整且不受天气影响。"),
        ("social_activity", "夜间KTV包厢", ["ktv_night", "nightlife", "friends"], ["ktv", "nightlife", "group_friendly", "indoor"], "夜间可订包厢，适合唱歌聚会。"),
        ("date_activity", "安静艺术展", ["date", "rainy_indoor"], ["quiet", "indoor", "romantic"], "安静、有氛围，排队风险低。"),
        ("date_activity", "小型独立影院", ["cinema", "date", "rainy_indoor"], ["cinema", "indoor", "low_noise", "quiet"], "排片灵活，适合低噪音观影。"),
        ("date_activity", "疗愈香氛SPA", ["wellness_spa", "date"], ["wellness", "spa", "quiet", "relax"], "节奏慢、私密度高，适合放松恢复。"),
        ("indoor_activity", "商场室内体验馆", ["rainy_indoor", "family", "friends"], ["indoor", "rain_safe", "nearby"], "雨天可替代户外节点。"),
        ("indoor_activity", "综合购物中心", ["shopping", "rainy_indoor", "friends", "family"], ["shopping", "indoor", "walkable", "rain_safe"], "购物、餐饮和休息点集中，适合不确定天气。"),
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
    return pois[:110]


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
