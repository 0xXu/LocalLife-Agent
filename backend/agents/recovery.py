from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.models.schemas import ItineraryStep, PlanState, RecoveryDiff
from backend.tools import POIRepository


class RecoveryAgent(BaseAgent):
    name = "RecoveryAgent"
    tool = "compare_alternatives"

    def __init__(self, repository: POIRepository) -> None:
        self.repository = repository

    def execute(self, state: PlanState) -> PlanState:
        original = state.itinerary[1]
        fallback = self.repository.get("res_022")
        state.itinerary[1] = ItineraryStep(
            "15:50",
            "16:50",
            "restaurant",
            fallback.name,
            fallback.id,
            fallback.reason,
            "约 340 元",
            "从科学馆步行 7 分钟",
        )
        state.actions[1].target = fallback.name
        state.actions[1].detail = "15:50，3 人桌位，低脂菜单备选已确认。"
        state.diff = RecoveryDiff(
            changed="restaurant",
            reason="绿荫轻食餐厅返回该时段无位。",
            from_value=original.title,
            to=fallback.name,
            cost_delta="+约 40 元",
            travel_delta="+步行 2 分钟",
            preserved=[state.itinerary[0].title, state.itinerary[2].title],
        )
        state.adjustment = {
            "headline": "餐厅临时无位，已为你换好备选",
            "message": "绿荫轻食餐厅当前时段无位，已替换为步行 7 分钟可达的轻碗健康餐厅。原亲子活动和饭后散步保持不变。",
            "primaryAction": "重新确认预订",
            "secondaryAction": "换另一家餐厅",
        }
        state.status = "recovered_pending_confirmation"
        return state

    def message(self, state: PlanState) -> str:
        return "主餐厅无位时只替换餐厅节点，并保留其余行程。"
