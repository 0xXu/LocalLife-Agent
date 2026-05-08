from __future__ import annotations

from uuid import uuid4

from backend.agents.base import BaseAgent
from backend.models.schemas import ItineraryStep, PlanAction, PlanOverview, PlanState
from backend.tools import RoutingTool


class RouteSchedulerAgent(BaseAgent):
    name = "RouteSchedulerAgent"
    tool = "optimize_route"

    def __init__(self, routing: RoutingTool) -> None:
        self.routing = routing

    def execute(self, state: PlanState) -> PlanState:
        activity = state.ranked["activities"][0]
        restaurant = state.ranked["restaurants"][0]
        walk = state.ranked["walks"][0]
        route = self.routing.optimize([activity, restaurant, walk])
        scenario = state.constraints.scenario
        is_family = scenario == "family"
        party_size = state.constraints.people["adults"] + len(state.constraints.people["children"])
        state.plan_id = f"plan_{scenario}_{uuid4().hex[:8]}"
        state.itinerary = [
            ItineraryStep("13:30", "15:30", "activity", activity.name, activity.id, activity.reason, f"约 {activity.avg_price} 元", "打车 12 分钟"),
            ItineraryStep("15:45", "16:45", "restaurant", restaurant.name, restaurant.id, restaurant.reason, f"约 {restaurant.avg_price} 元", "从活动点步行 5 分钟"),
            ItineraryStep("17:00", "17:30", "dessert_walk", walk.name, walk.id, walk.reason, f"约 {walk.avg_price} 元", "轻松步行 1.2 公里"),
        ]
        state.overview = PlanOverview(
            theme="下午 · 家庭 · 健康轻松" if is_family else "下午 · 朋友 · 轻量聚会",
            total_duration="4 小时",
            drive_time=str(route["drive_time"]),
            walking_distance=str(route["walking_distance"]),
            estimated_cost="约 750 - 900 元" if is_family else "约 850 - 1100 元",
        )
        state.actions = [
            PlanAction("activity_reservation", "预约亲子活动" if is_family else "预约朋友活动", activity.name, f"{party_size} 人名额，下午 13:30 到 15:30。"),
            PlanAction("restaurant_reservation", "预订轻食餐厅", restaurant.name, f"15:45，{party_size} 人桌，低脂菜单优先。"),
            PlanAction("message", "发送计划给家人" if is_family else "发送计划给朋友", "家庭群聊" if is_family else "朋友群聊", "发送时间轴、路线和预算摘要。"),
        ]
        state.status = "itinerary_built"
        return state

    def message(self, state: PlanState) -> str:
        return "生成活动 -> 餐厅 -> 饭后散步路线。"
