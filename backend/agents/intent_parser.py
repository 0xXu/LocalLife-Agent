from __future__ import annotations

import re

from backend.agents.base import BaseAgent
from backend.models.schemas import ParsedConstraints, PlanState


class IntentParserAgent(BaseAgent):
    name = "IntentParserAgent"
    tool = "parse_user_goal"

    def execute(self, state: PlanState) -> PlanState:
        child_age = parse_child_age(state.goal)
        scenario = "family" if child_age else "friends"
        adult_count = parse_adult_count(state.goal, child_age)
        radius = 5 if re.search(r"别.*远|附近|nearby|not too far|5km", state.goal, re.I) else 8
        diet = ["low_fat", "low_sugar"] if re.search(r"减脂|减肥|diet|low[-\s]?fat", state.goal, re.I) else []
        state.constraints = ParsedConstraints(
            scenario=scenario,
            origin={"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
            time_window={"date": "today", "start": "13:30", "duration_hours": 4.0, "flexible": True},
            people={
                "adults": adult_count,
                "children": [{"age": child_age}] if child_age else [],
                "relationship": scenario,
            },
            preferences={
                "distance": "nearby",
                "diet": diet,
                "activity": ["child_friendly", "not_too_tiring"] if scenario == "family" else ["social", "indoor"],
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
        return "解析出人群、饮食、距离和半日时长约束。"

    def duration_ms(self) -> int:
        return 120


def parse_child_age(goal: str) -> int | None:
    match = re.search(r"孩子\s*(\d{1,2})\s*岁|(\d{1,2})\s*(?:岁|yo).*(?:孩子|child|kid)", goal, re.I)
    if match:
        return int(next(group for group in match.groups() if group))
    if re.search(r"孩子|child|kid", goal, re.I):
        return 5
    return None


def parse_adult_count(goal: str, child_age: int | None) -> int:
    if child_age:
        return 2
    gender_match = re.search(r"(\d{1,2})\s*男\s*(\d{1,2})\s*女", goal)
    if gender_match:
        return int(gender_match.group(1)) + int(gender_match.group(2))
    match = re.search(r"朋友\s*(\d{1,2})\s*个人|(\d{1,2})\s*个?人", goal)
    if match:
        return int(next(group for group in match.groups() if group))
    return 4 if "朋友" in goal else 2
