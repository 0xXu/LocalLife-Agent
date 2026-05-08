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
        scenario = state.constraints.scenario
        activity_category = "family_activity" if scenario == "family" else "social_activity"
        activity_tags = ["child_friendly", "indoor"] if scenario == "family" else ["social", "indoor"]
        restaurant_tags = ["low_fat", "child_seat"] if scenario == "family" else ["group_friendly", "booking_supported"]
        state.candidates = {
            "activities": self.repository.search(activity_category, radius, activity_tags),
            "restaurants": self.repository.search("restaurant", radius, restaurant_tags),
            "walks": self.repository.search("dessert_walk", radius, ["low_sugar", "walkable"]),
        }
        state.status = "candidates_found"
        return state

    def summarize_output(self, state: PlanState) -> dict:
        return {key: len(value) for key, value in state.candidates.items()}

    def message(self, state: PlanState) -> str:
        return "找到半径内适合当前人群的活动、餐厅和饭后散步点。"
