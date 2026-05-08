from __future__ import annotations

from backend.models.schemas import PlanState, Receipt


class ExecutionTool:
    def execute(self, state: PlanState) -> list[Receipt]:
        restaurant = state.itinerary[1]
        restaurant_id = "RES-7420" if restaurant.place_id == "res_022" else "RES-3812"
        return [
            Receipt(
                type="activity_reservation",
                tool="reserve_activity",
                id="TKT-2041",
                status="已确认",
                detail=f"已为 3 人预约{state.itinerary[0].title}。",
            ),
            Receipt(
                type="restaurant_reservation",
                tool="create_reservation",
                id=restaurant_id,
                status="已确认",
                detail=f"已预订{restaurant.title} {restaurant.start} 的 3 人桌。",
            ),
            Receipt(
                type="message",
                tool="send_plan_message",
                id="MSG-9128",
                status="已发送",
                detail="计划摘要已发送到家庭群聊。",
            ),
        ]

