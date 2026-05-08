from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.models.schemas import PlanState
from backend.tools import POIRepository


class CandidateSearchAgent(BaseAgent):
    name = "CandidateSearchAgent"
    tool = "search_places"

    def __init__(self, repository: POIRepository) -> None:
        self.repository = repository

    def execute(self, state: PlanState) -> PlanState:
        radius = state.constraints.constraints["radius_km"]
        state.candidates = {
            "activities": self.repository.search("family_activity", radius, ["child_friendly", "indoor"]),
            "restaurants": self.repository.search("restaurant", radius, ["low_fat", "child_seat"]),
            "walks": self.repository.search("dessert_walk", radius, ["low_sugar", "walkable"]),
        }
        state.status = "candidates_found"
        return state

    def summarize_output(self, state: PlanState) -> dict:
        return {key: len(value) for key, value in state.candidates.items()}

    def message(self, state: PlanState) -> str:
        return "找到 5 公里内适合亲子的活动、健康餐厅和饭后散步点。"

