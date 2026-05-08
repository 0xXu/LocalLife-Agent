from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.models.schemas import POI, PlanState


class RankerAgent(BaseAgent):
    name = "RankerAgent"
    tool = "rank_candidates"

    def execute(self, state: PlanState) -> PlanState:
        state.ranked = {
            key: sorted(items, key=self.score, reverse=True)
            for key, items in state.candidates.items()
        }
        state.status = "ranked"
        return state

    def score(self, poi: POI) -> float:
        tag_score = 0.2 * ("low_fat" in poi.tags) + 0.2 * ("child_friendly" in poi.tags)
        distance_score = max(0, 1 - poi.distance_km / 10)
        wait_score = max(0, 1 - poi.wait_minutes / 60)
        return 0.4 * poi.rating / 5 + 0.25 * distance_score + 0.2 * wait_score + tag_score

    def message(self, state: PlanState) -> str:
        return "按距离、儿童友好、饮食匹配、等待时间和评分排序。"

