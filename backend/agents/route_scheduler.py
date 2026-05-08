from __future__ import annotations

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
        state.plan_id = "plan_family_001"
        state.itinerary = [
            ItineraryStep("13:30", "15:30", "activity", activity.name, activity.id, activity.reason, "约 320 元", "打车 12 分钟"),
            ItineraryStep("15:45", "16:45", "restaurant", restaurant.name, restaurant.id, restaurant.reason, "约 300 元", "从科学馆步行 5 分钟"),
            ItineraryStep("17:00", "17:30", "dessert_walk", walk.name, walk.id, walk.reason, "约 130 元", "轻松步行 1.2 公里"),
        ]
        state.overview = PlanOverview(
            theme="下午 · 家庭 · 健康轻松",
            total_duration="4 小时",
            drive_time=str(route["drive_time"]),
            walking_distance=str(route["walking_distance"]),
            estimated_cost="约 750 - 900 元",
        )
        state.actions = [
            PlanAction("activity_reservation", "预约亲子活动", activity.name, "3 人入场名额，下午 13:30 到 15:30。"),
            PlanAction("restaurant_reservation", "预订轻食餐厅", restaurant.name, "15:45，3 人桌位，低脂菜单优先。"),
            PlanAction("message", "发送计划给家人", "家庭群聊", "发送时间轴、路线和预算摘要。"),
        ]
        state.status = "itinerary_built"
        return state

    def message(self, state: PlanState) -> str:
        return "生成科学馆 -> 轻食餐厅 -> 河畔散步路线。"

