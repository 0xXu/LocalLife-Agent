from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.models.schemas import PlanState
from backend.tools import AvailabilityTool, POIRepository


class PlanValidatorAgent(BaseAgent):
    name = "PlanValidatorAgent"
    tool = "check_availability"

    def __init__(self, repository: POIRepository, availability: AvailabilityTool) -> None:
        self.repository = repository
        self.availability = availability

    def execute(self, state: PlanState) -> PlanState:
        restaurant_step = state.itinerary[1]
        restaurant = self.repository.get(restaurant_step.place_id)
        party_size = state.constraints.people["adults"] + len(state.constraints.people["children"])
        check = self.availability.check(restaurant, restaurant_step.start, party_size=party_size)
        if not check["available"]:
            state.errors.append("restaurant_unavailable")
            state.status = "needs_recovery"
        else:
            state.status = "ready_for_confirmation"
        return state

    def summarize_output(self, state: PlanState) -> dict:
        return {"status": state.status, "errors": list(state.errors)}

    def message(self, state: PlanState) -> str:
        return "确认主餐厅在计划时段有模拟可订席位。"
