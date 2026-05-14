from __future__ import annotations

from typing import Any

from backend.data.catalog import LocalDataCatalog
from backend.models.schemas import PlanState, TraceStep
from backend.observability.spans import span
from backend.tools.registry import LocalToolRegistry


def build_context_node(state: PlanState, catalog: LocalDataCatalog) -> PlanState:
    constraints = state.constraints
    rainy = constraints.scenario == "rainy_indoor" or "下雨" in state.goal or "雨" in state.goal
    tools = LocalToolRegistry(catalog)
    weather = tools.get_weather(rainy).output
    state.context = {**state.context, "weather": weather, "profile": "local_demo_user", "privacy": "minimal"}
    state.status = "context_ready"
    state.add_trace(span("ContextBuilderAgent", "get_weather", "ok", "补全天气、位置和用户偏好上下文。", "tool", {}, weather, 120, {"provider": "local_weather_seed"}))
    return state


def merge_search_results_node(state: PlanState, activities: list, restaurants: list, walks: list) -> PlanState:
    state.candidates = {
        "activities": activities,
        "restaurants": restaurants,
        "walks": walks,
    }
    state.status = "candidates_ready"
    state.add_trace(span(
        "CandidateSearchAgent", "search_places", "ok",
        "并行检索活动、餐厅、甜品散步点。",
        "tool", {}, {"activities": len(activities), "restaurants": len(restaurants), "walks": len(walks)}, 260,
        {"provider": "local_seed_catalog", "parallel": True},
    ))
    return state
