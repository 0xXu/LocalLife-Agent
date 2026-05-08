from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.models.schemas import PlanState


class ContextBuilderAgent(BaseAgent):
    name = "ContextBuilderAgent"
    tool = "get_weather"

    def execute(self, state: PlanState) -> PlanState:
        state.context = {
            "weather": {"condition": "clear", "risk": "low"},
            "profile": {"dietary": "low_fat", "home_radius_km": state.constraints.constraints["radius_km"]},
            "current_time": "12:40",
        }
        state.status = "context_ready"
        return state

    def message(self, state: PlanState) -> str:
        return "补全当前位置、天气和减脂饮食偏好。"

