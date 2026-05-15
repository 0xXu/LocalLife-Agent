from __future__ import annotations

import json
import warnings
from collections.abc import Callable
from typing import Any, TypedDict
from uuid import uuid4

from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
from langchain_core.messages import HumanMessage, SystemMessage

warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)

from langgraph.graph import END, START, StateGraph

from backend.agents.ranker import RankerAgent
from backend.agents.recovery import RecoveryAgent
from backend.agents.tools import AgentContext
from backend.agents.validator import ValidatorAgent
from backend.data.catalog import LocalDataCatalog
from backend.llm import LLMConfig
from backend.llm.chat_model import build_mimo_chat_model
from backend.models.schemas import (
    ItineraryStep,
    ParsedConstraints,
    PlanOverview,
    PlanState,
    Receipt,
    RecoveryDiff,
)
from backend.observability.spans import span
from backend.orchestrator.constraints import (
    as_list,
    clarifying_questions_for,
    constraints_from_dict,
    deterministic_constraints,
    extract_json_object,
    missing_required_fields,
    normalize_constraints_for_goal,
    unique_list,
)
from backend.orchestrator.itinerary import (
    LLMIntentParsingError,
    _apply_replacement,
    apply_constraint_overrides,
    build_pending_actions,
    build_steps,
    duration_hours_of,
    emit_progress,
    find_step,
    format_duration_hours,
    format_time,
    frontend_route,
    party_size_of,
    require_constraints,
    restaurant_time_from_steps,
    scenario_theme,
    score_step,
    should_include_restaurant,
    should_include_walk,
)
from backend.orchestrator.nodes import build_context_node, merge_search_results_node
from backend.orchestrator.search import search_activities, search_restaurants, search_walks
from backend.planning.candidates import build_itinerary_variants
from backend.profile.resolver import merge_profile_into_goal_context
from backend.providers.local import confidence_for_tags, ground_place
from backend.retrieval.ranker import rank_candidates
from backend.revision.models import RevisionDelta
from backend.tools import LocalToolRegistry
from backend.validation.rules import validate_itinerary


class BuildGraphState(TypedDict, total=False):
    state: PlanState
    overrides: dict | None
    on_progress: Callable[[str, str], None] | None
    on_token: Callable[[str], None] | None
    profile: Any | None
    llm_fallback: bool
    activity: dict | None
    restaurant: dict | None
    walk: dict | None
    route: dict[str, Any]
    build_result: dict[str, Any]
    validation: dict[str, Any]
    # Parallel search results
    activity_candidates: list[dict[str, Any]]
    restaurant_candidates: list[dict[str, Any]]
    walk_candidates: list[dict[str, Any]]


def should_continue_after_parse(graph_state: BuildGraphState) -> str:
    return "clarify" if graph_state["state"].status == "needs_clarification" else "continue"


class PlanningPipeline:
    def __init__(self, catalog: LocalDataCatalog | None = None, llm_config: LLMConfig | None = None) -> None:
        self.catalog = catalog or LocalDataCatalog()
        self.tools = LocalToolRegistry(self.catalog)
        self.llm_config = llm_config or LLMConfig.from_env_file()
        self.chat_model = build_mimo_chat_model(self.llm_config) if self.llm_config.is_configured and self.llm_config.remote_enabled else None
        self.graph = self._compile_graph()

    def build(self, goal: str, overrides: dict | None = None, on_progress: Callable[[str, str], None] | None = None, on_token: Callable[[str], None] | None = None, profile=None) -> PlanState:
        state = PlanState(goal=goal, plan_id=f"plan_{uuid4().hex[:10]}", status="input_received")
        result = self.graph.invoke({"state": state, "overrides": overrides, "on_progress": on_progress, "on_token": on_token, "profile": profile})
        return result["state"]

    def _compile_graph(self):
        graph = StateGraph(BuildGraphState)

        # Existing nodes
        graph.add_node("parse_intent", self._parse_intent_node)
        graph.add_node("build_context", self._build_context_node)

        # Parallel search nodes
        graph.add_node("search_activities", self._search_activities_node)
        graph.add_node("search_restaurants", self._search_restaurants_node)
        graph.add_node("search_walks", self._search_walks_node)
        graph.add_node("merge_search_results", self._merge_search_results_node)

        # Agent nodes
        graph.add_node("ranker_agent", self._ranker_agent_node)
        graph.add_node("build_itinerary", self._build_itinerary_node)
        graph.add_node("validator_agent", self._validator_agent_node)
        graph.add_node("prepare_confirmation", self._prepare_confirmation_node)
        graph.add_node("recovery", self._recovery_node)

        # Edges
        graph.add_edge(START, "parse_intent")
        graph.add_conditional_edges("parse_intent", should_continue_after_parse, {"continue": "build_context", "clarify": END})
        graph.add_edge("build_context", "search_activities")
        graph.add_edge("build_context", "search_restaurants")
        graph.add_edge("build_context", "search_walks")
        graph.add_edge("search_activities", "merge_search_results")
        graph.add_edge("search_restaurants", "merge_search_results")
        graph.add_edge("search_walks", "merge_search_results")
        graph.add_edge("merge_search_results", "ranker_agent")
        graph.add_edge("ranker_agent", "build_itinerary")
        graph.add_edge("build_itinerary", "validator_agent")
        graph.add_conditional_edges("validator_agent", self._after_validate, {
            "confirm": "prepare_confirmation",
            "recover": "recovery",
        })
        graph.add_edge("recovery", "ranker_agent")  # Loop back
        graph.add_edge("prepare_confirmation", END)

        return graph.compile()

    def _parse_intent_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints, llm_fallback = self.parse_constraints(state.goal, on_token=graph_state.get("on_token"))
        overrides = graph_state.get("overrides")
        if overrides:
            constraints = apply_constraint_overrides(constraints, overrides)
        profile = graph_state.get("profile")
        if profile:
            constraints = merge_profile_into_goal_context(constraints, profile)
            state.context["user_profile"] = profile.as_dict()
        state.constraints = constraints
        missing = missing_required_fields(state.goal, constraints)
        if missing:
            state.status = "needs_clarification"
            state.context["missing_fields"] = missing
            state.context["clarifying_questions"] = clarifying_questions_for(missing)
            state.add_trace(span("IntentParserAgent", "clarify_goal", "warning", "目标信息不足，返回澄清问题。", "llm", {}, {"missing_fields": missing}, 80, {"model": self.llm_config.model}))
            return {"state": state}
        state.status = "constraints_parsed"
        state.add_trace(
            span(
                "IntentParserAgent",
                "parse_user_goal",
                "ok",
                "解析自然语言目标为结构化约束。",
                "llm",
                {"goal_length": len(state.goal)},
                {"scenario": constraints.scenario, "llm_fallback": llm_fallback},
                140,
                {"model": self.llm_config.model},
            )
        )
        emit_progress(graph_state, "理解出行需求", "解析自然语言目标为结构化约束。")
        return {"state": state, "llm_fallback": llm_fallback}

    def _build_context_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        rainy = constraints.scenario == "rainy_indoor" or "下雨" in state.goal or "雨" in state.goal
        weather = self.tools.get_weather(rainy).output
        state.context = {**state.context, "weather": weather, "profile": "local_demo_user", "privacy": "minimal"}
        state.status = "context_ready"
        state.add_trace(span("ContextBuilderAgent", "get_weather", "ok", "补全天气、位置和用户偏好上下文。", "tool", {}, weather, 120, {"provider": "local_weather_seed"}))
        emit_progress(graph_state, "补全场景上下文", "补全天气、位置和用户偏好上下文。")
        return {"state": state}

    # --- Parallel search nodes ---

    def _search_activities_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        weather = state.context.get("weather")
        user_preferences = _extract_user_preferences(graph_state)
        items = search_activities(self.catalog, constraints, weather=weather, user_preferences=user_preferences)
        emit_progress(graph_state, "搜索活动场所", f"找到 {len(items)} 个候选")
        return {"activity_candidates": items}

    def _search_restaurants_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        weather = state.context.get("weather")
        user_preferences = _extract_user_preferences(graph_state)
        items = search_restaurants(self.catalog, constraints, weather=weather, user_preferences=user_preferences)
        emit_progress(graph_state, "搜索餐厅", f"找到 {len(items)} 个候选")
        return {"restaurant_candidates": items}

    def _search_walks_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        weather = state.context.get("weather")
        user_preferences = _extract_user_preferences(graph_state)
        items = search_walks(self.catalog, constraints, weather=weather, user_preferences=user_preferences)
        emit_progress(graph_state, "搜索散步点", f"找到 {len(items)} 个候选")
        return {"walk_candidates": items}

    def _merge_search_results_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        activities = graph_state.get("activity_candidates", [])
        restaurants = graph_state.get("restaurant_candidates", [])
        walks = graph_state.get("walk_candidates", [])
        updated = merge_search_results_node(state, activities, restaurants, walks)
        emit_progress(graph_state, "合并搜索结果", f"活动 {len(activities)}、餐厅 {len(restaurants)}、散步 {len(walks)}")
        return {"state": updated}

    # --- Agent nodes ---

    def _ranker_agent_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        context = AgentContext(user_id=state.context.get("user_id", "default"))
        agent = RankerAgent(self.chat_model or self.llm, registry=self.tools, memory_store=getattr(self, 'memory_store', None))
        ranked = agent.rank(state.candidates, constraints, context=context)

        # If agent used deterministic fallback (no LLM "ranked" key), use old multi-factor scorer
        # which considers tag relevance, distance, quality, wait time, budget, etc.
        if "deterministic" in agent.last_reasoning.lower() or "fallback" in agent.last_reasoning.lower():
            preferred_tags = list(constraints.preferences.get("activity", [])) + list(constraints.preferences.get("diet", []))
            candidate_sets: dict[str, list[dict[str, Any]]] = {}
            rejected: dict[str, list[dict[str, Any]]] = {}
            for key, items in state.candidates.items():
                grounded = [ground_place(item, confidence_for_tags(item, preferred_tags)) for item in items]
                result = rank_candidates(grounded, constraints)
                ranked[key] = [candidate.place.as_poi_dict() for candidate in result.items]
                candidate_sets[key] = [
                    {
                        "place": candidate.place.as_poi_dict(),
                        "total_score": candidate.total_score,
                        "score_breakdown": candidate.breakdown,
                        "explanation": candidate.explanation,
                    }
                    for candidate in result.items
                ]
                rejected[key] = result.rejected
            state.candidate_sets = candidate_sets
            state.rejected_candidates = rejected

        state.ranked = ranked
        state.status = "ranked"
        state.agent_decisions["ranker"] = {"reasoning": agent.last_reasoning}
        state.add_trace(agent.build_trace(
            "ok", "LLM 驱动的多目标候选排序。",
            {"candidates": {k: len(v) for k, v in state.candidates.items()}},
            {"ranked": {k: len(v) for k, v in ranked.items()}, "reasoning": agent.last_reasoning},
        ))
        emit_progress(graph_state, "LLM 多目标排序", "LLM 驱动的多目标候选排序。")
        return {"state": state}

    def _validator_agent_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        context = AgentContext(user_id=state.context.get("user_id", "default"))
        agent = ValidatorAgent(self.chat_model or self.llm, registry=self.tools)
        constraints_data = {
            "scenario": constraints.scenario,
            "budget_level": constraints.preferences.get("budget_level", "medium"),
            "duration_hours": constraints.time_window.get("duration_hours", 4.5),
            "time_window": constraints.time_window,
            "people": constraints.people,
            "preferences": constraints.preferences,
            "constraints": constraints.constraints,
        }
        weather = state.context.get("weather", {})
        lookup = {item["id"]: item for group in state.ranked.values() for item in group}
        validation = agent.validate(state.itinerary, constraints_data, weather, lookup, state.route, context=context)
        state.validation_issues = validation.get("issues", [])
        state.status = "pending_confirmation" if validation.get("valid", True) else "recovering"
        state.agent_decisions["validator"] = {"score": validation.get("overall_score", 85), "issues": validation.get("issues", [])}
        state.add_trace(agent.build_trace(
            "ok" if validation.get("valid", True) else "warning",
            "LLM 驱动的方案整体评估。",
            {"itinerary_steps": len(state.itinerary)},
            validation,
        ))
        emit_progress(graph_state, "LLM 方案评估", "LLM 驱动的方案整体评估。")
        return {"state": state, "validation": validation}

    def _after_validate(self, graph_state: BuildGraphState) -> str:
        state = graph_state["state"]
        if state.status == "pending_confirmation" or state.recovery_attempts >= 3:
            return "confirm"
        return "recover"

    def _recovery_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        state.recovery_attempts += 1
        issues = state.validation_issues
        itinerary_summary = [{"type": step.type, "place_id": step.place_id, "title": step.title} for step in state.itinerary]
        alternatives = {k: list(v) for k, v in state.ranked.items()}
        context = AgentContext(user_id=state.context.get("user_id", "default"))
        agent = RecoveryAgent(self.chat_model or self.llm, registry=self.tools)
        decision = agent.recover(issues, itinerary_summary, alternatives, context=context)
        state.agent_decisions["recovery"] = decision

        # Apply recovery decision
        if decision.get("action") == "replace":
            _apply_replacement(state, decision)

        state.status = "recovering"
        state.add_trace(agent.build_trace(
            "ok", f"恢复尝试 #{state.recovery_attempts}。",
            {"issues": issues}, decision,
        ))
        emit_progress(graph_state, f"异常恢复 #{state.recovery_attempts}", decision.get("reason", ""))
        return {"state": state}

    def _build_itinerary_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        if not state.ranked.get("activities"):
            raise RuntimeError("No activity candidates found after ranking. Cannot build itinerary.")
        activity = state.ranked["activities"][0]
        restaurant = state.ranked["restaurants"][0] if should_include_restaurant(constraints) and state.ranked.get("restaurants") else None
        walk = state.ranked["walks"][0] if should_include_walk(constraints, restaurant) and state.ranked.get("walks") else None
        waypoints = [item for item in [activity, restaurant, walk] if item]
        route = self.tools.optimize_route(waypoints).output
        state.route = frontend_route(waypoints, route)
        state.itinerary = build_steps(activity, restaurant, walk, constraints)
        build_result = self.tools.build_itinerary(constraints, activity, restaurant, walk)
        state.add_tool_result(
            build_result,
            {
                "activity": activity["id"],
                "restaurant": restaurant["id"] if restaurant else None,
                "walk": walk["id"] if walk else None,
            },
        )
        state.overview = PlanOverview(
            scenario_theme(constraints.scenario),
            format_duration_hours(constraints.time_window.get("duration_hours", 4.5)),
            route["drive_time"],
            route["walking_distance"],
            f"约 {build_result.output['estimated_budget']} 元",
            build_result.output["score"],
        )
        state.variants = build_itinerary_variants(
            state.itinerary,
            state.ranked.get("activities", []),
            state.ranked.get("restaurants", []),
            state.ranked.get("walks", []),
            constraints,
            build_result.output["score"],
        )
        state.status = "itinerary_built"
        state.add_trace(span("RouteSchedulerAgent", "optimize_route", "ok", "按用户时长生成可执行时间轴和顺路路线。", "tool", {}, route, 220, {"provider": route.get("provider", "local_seed_route_matrix")}))
        emit_progress(graph_state, "生成时间轴和路线", "按用户时长生成可执行时间轴和顺路路线。")
        return {"state": state, "activity": activity, "restaurant": restaurant, "walk": walk, "route": route, "build_result": build_result.output}

    def _prepare_confirmation_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        activity = graph_state["activity"]
        restaurant = graph_state.get("restaurant")
        walk = graph_state.get("walk")
        state.pending_actions = build_pending_actions(activity, restaurant, walk, constraints)
        state.actions = list(state.pending_actions)
        state.add_trace(span("ConfirmationAgent", "human_in_the_loop", "ok", "敏感动作已暂停，等待用户确认。", "planning", {}, {"pending_actions": len(state.pending_actions)}, 80))
        return {"state": state}

    def execute(self, state: PlanState) -> PlanState:
        state.status = "executing"
        receipts: list[Receipt] = []
        for action in state.pending_actions:
            result = self.tools.execute_action(action)
            state.add_tool_result(result, {"tool": action.tool, "target": action.target})
            receipts.append(Receipt(action.type, action.tool, result.output["id"], result.output["status"], result.output["detail"]))
        state.receipts = receipts
        state.status = "completed"
        state.add_trace(span("ExecutionAgent", "confirmed_side_effect_tools", "ok", "用户确认后执行预约、订座、领券、点单、消息和日历动作。", "execution", {}, {"receipts": [item.id for item in receipts]}, 320))
        return state

    def revise(self, state: PlanState, delta: RevisionDelta, profile=None) -> PlanState:
        updates = dict(delta.constraint_updates)
        if updates.get("meal_required") is False:
            updates["required_actions"] = [
                action for action in as_list(require_constraints(state).required_actions)
                if action not in {"restaurant_reservation", "claim_coupon", "create_order"}
            ]
        rebuilt = self.build(state.goal, updates, profile=profile)
        locked = set(delta.locked_nodes)
        if locked:
            locked_steps = {step.place_id: step for step in state.itinerary if step.place_id in locked}
            for index, step in enumerate(rebuilt.itinerary):
                previous = next((old for old in locked_steps.values() if old.type == step.type), None)
                if previous:
                    rebuilt.itinerary[index] = previous
        removed = set(delta.removed_nodes)
        if removed:
            rebuilt.itinerary = [step for step in rebuilt.itinerary if step.place_id not in removed]
            rebuilt.pending_actions = [
                action for action in rebuilt.pending_actions
                if action.payload.get("place_id") not in removed and action.payload.get("shop_id") not in removed
            ]
            rebuilt.actions = list(rebuilt.pending_actions)
        rebuilt.plan_id = state.plan_id
        rebuilt.status = "pending_confirmation"
        rebuilt.context["revision"] = {
            "revision_id": delta.revision_id,
            "feedback_text": delta.feedback_text,
            "constraint_updates": delta.constraint_updates,
        }
        return rebuilt

    def recover(self, state: PlanState, reason: str) -> PlanState:
        state.status = "recovering"
        constraints = require_constraints(state)
        old_restaurant = find_step(state.itinerary, "restaurant")
        if old_restaurant:
            restaurants = [item for item in state.ranked.get("restaurants", []) if item["id"] != old_restaurant.place_id]
            fallback = restaurants[0] if restaurants else self.catalog.search_pois("restaurant", constraints.scenario, 8, ["fallback"])[0]
            restaurant_index = next(index for index, step in enumerate(state.itinerary) if step.type == "restaurant")
            state.itinerary[restaurant_index] = ItineraryStep(
                old_restaurant.start,
                old_restaurant.end,
                "restaurant",
                fallback["name"],
                fallback["id"],
                fallback["reason"],
                f"约 {fallback['avg_price']} 元",
                "从上一站步行 7 分钟",
                88,
                "已替换无位餐厅",
            )
            changed = "restaurant"
            from_value = old_restaurant.title
            to_value = fallback["name"]
            cost_delta = "+约 40 元"
            travel_delta = "+步行 2 分钟"
        else:
            old_activity = find_step(state.itinerary, "activity")
            if old_activity is None:
                raise ValueError("validation_error")
            activities = [item for item in state.ranked.get("activities", []) if item["id"] != old_activity.place_id]
            fallback = activities[0] if activities else self.catalog.search_pois(None, None, 8, constraints.preferences.get("activity", []))[0]
            activity_index = next(index for index, step in enumerate(state.itinerary) if step.type == "activity")
            state.itinerary[activity_index] = ItineraryStep(
                old_activity.start,
                old_activity.end,
                "activity",
                fallback["name"],
                fallback["id"],
                fallback["reason"],
                f"约 {fallback['avg_price']} 元",
                old_activity.travel,
                score_step(fallback, constraints),
                "已替换不可用活动",
            )
            changed = "activity"
            from_value = old_activity.title
            to_value = fallback["name"]
            cost_delta = "按新活动价格调整"
            travel_delta = "路线保持相近"
        activity_step = find_step(state.itinerary, "activity")
        restaurant_step = find_step(state.itinerary, "restaurant")
        walk_step = find_step(state.itinerary, "dessert_walk")
        activity = self.catalog.get_poi(activity_step.place_id) if activity_step else fallback
        restaurant = self.catalog.get_poi(restaurant_step.place_id) if restaurant_step else None
        walk = self.catalog.get_poi(walk_step.place_id) if walk_step else None
        waypoints = [item for item in [activity, restaurant, walk] if item]
        state.route = frontend_route(waypoints, self.tools.optimize_route(waypoints).output)
        state.pending_actions = build_pending_actions(activity, restaurant, walk, constraints)
        state.actions = list(state.pending_actions)
        diff = RecoveryDiff(
            changed,
            reason,
            from_value,
            to_value,
            cost_delta,
            travel_delta,
            [step.title for step in state.itinerary if step.title not in {to_value}],
        )
        state.diff = diff
        state.recovery_history.append(diff)
        state.adjustment = {
            "headline": f"{'餐厅' if changed == 'restaurant' else '活动'}临时不可用，已只替换冲突节点",
            "message": f"{from_value} 当前不可用，已切换到 {to_value}，其他安排保持不变。",
            "primaryAction": "重新确认执行",
            "secondaryAction": "换另一个备选",
        }
        state.status = "recovered_pending_confirmation"
        state.add_trace(span("RecoveryAgent", "compare_alternatives", "ok", "异常恢复只替换冲突节点并展示差异。", "recovery", {"reason": reason}, diff.as_frontend_dict(), 210))
        return state

    def parse_constraints(self, goal: str, on_token: Callable[[str], None] | None = None) -> tuple[ParsedConstraints, bool]:
        if not self.llm_config.is_configured or not self.llm_config.remote_enabled:
            raise LLMIntentParsingError("Remote LLM is required. Configure LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, and LLM_REMOTE_ENABLED=true.")
        if not self.chat_model:
            raise LLMIntentParsingError("Chat model not initialized.")
        messages = [
            SystemMessage(content=(
                "You are a JSON extraction tool. Return ONLY a valid JSON object. No markdown, no prose, no reasoning.\n"
                "Keys: scenario (open-domain snake_case label), origin, time_window, people, preferences (with activity tags, intent_label, budget_level, distance, diet), constraints, required_actions.\n"
                "preferences.activity: 3-8 English tags like hiking, outdoor, pet, quiet, cafe, wifi, work, sports, badminton, basketball, birthday, photo, museum, art, cinema, shopping, wellness, spa, ktv, nightlife, child_friendly, indoor, rain_safe, walkable.\n"
                "preferences.intent_label: short Chinese label.\n"
                "Only include restaurant/coupon/order actions when user asks for eating. Always include send_plan_message and create_calendar_event.\n"
                "Example: {\"scenario\":\"label\",\"origin\":{\"type\":\"current_location\",\"label\":\"home\",\"lat\":38.26,\"lng\":140.88},\"time_window\":{\"date\":\"today\",\"start\":\"14:00\",\"duration_hours\":3,\"flexible\":true},\"people\":{\"adults\":1,\"children\":[],\"relationship\":\"solo\"},\"preferences\":{\"distance\":\"nearby\",\"diet\":[],\"activity\":[\"tag1\"],\"budget_level\":\"medium\",\"intent_label\":\"标签\"},\"constraints\":{\"radius_km\":8,\"max_wait_minutes\":15,\"avoid\":[\"long_queue\"]},\"required_actions\":[\"send_plan_message\",\"create_calendar_event\"]}"
            )),
            HumanMessage(content=goal),
        ]
        try:
            result = self.chat_model.invoke(messages)
            content = result.content
            # MiMo model may put JSON in reasoning_content instead of content
            if not content or "{" not in content:
                rc = result.additional_kwargs.get("reasoning_content", "")
                if rc and "{" in rc:
                    content = rc
            if on_token:
                on_token(content)
            parsed = json.loads(extract_json_object(content), strict=False)
            constraints = constraints_from_dict(parsed)
            return normalize_constraints_for_goal(goal, constraints), False
        except Exception as exc:
            raise LLMIntentParsingError(f"LLM intent parsing failed: {exc}") from exc


def _extract_user_preferences(graph_state: BuildGraphState) -> dict[str, Any] | None:
    """Extract user preference tags from the profile or constraints in graph state."""
    profile = graph_state.get("profile")
    if profile is not None:
        if hasattr(profile, "as_dict"):
            profile_dict = profile.as_dict()
        elif isinstance(profile, dict):
            profile_dict = profile
        else:
            profile_dict = {}
        prefs: dict[str, Any] = {}
        if "activity" in profile_dict:
            prefs["activity"] = list(profile_dict["activity"])
        if "diet" in profile_dict:
            prefs["diet"] = list(profile_dict["diet"])
        if prefs:
            return prefs
    state = graph_state.get("state")
    if state is not None and state.constraints is not None:
        return {
            "activity": list(state.constraints.preferences.get("activity", [])),
            "diet": list(state.constraints.preferences.get("diet", [])),
        }
    return None
