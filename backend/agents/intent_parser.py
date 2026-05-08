from __future__ import annotations

import re

from backend.agents.base import BaseAgent
from backend.models.schemas import ParsedConstraints, PlanState


class IntentParserAgent(BaseAgent):
    name = "IntentParserAgent"
    tool = "parse_user_goal"

    def execute(self, state: PlanState) -> PlanState:
        child_age = 5 if re.search(r"5\s*(岁|yo)|孩子|child|kid", state.goal, re.I) else None
        radius = 5 if re.search(r"别.*远|nearby|not too far|附近|5km", state.goal, re.I) else 8
        diet = ["low_fat", "low_sugar"] if re.search(r"减脂|减肥|diet|low[-\s]?fat", state.goal, re.I) else []
        state.constraints = ParsedConstraints(
            scenario="family" if child_age else "friends",
            origin={"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
            time_window={"date": "today", "start": "13:30", "duration_hours": 4.0, "flexible": True},
            people={
                "adults": 2,
                "children": [{"age": child_age}] if child_age else [],
                "relationship": "family" if child_age else "friends",
            },
            preferences={
                "distance": "nearby",
                "diet": diet,
                "activity": ["child_friendly", "not_too_tiring"],
                "budget_level": "medium",
            },
            constraints={"radius_km": radius, "max_wait_minutes": 15, "avoid": ["heavy_oil", "long_queue"]},
            required_actions=["activity_reservation", "restaurant_reservation", "send_plan_message"],
        )
        state.status = "constraints_parsed"
        return state

    def summarize_output(self, state: PlanState) -> dict:
        return {"scenario": state.constraints.scenario, "radius_km": state.constraints.constraints["radius_km"]}

    def message(self, state: PlanState) -> str:
        return "解析出家庭、饮食、距离和半日时长约束。"

    def duration_ms(self) -> int:
        return 120

