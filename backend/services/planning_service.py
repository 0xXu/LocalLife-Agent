from __future__ import annotations

from collections.abc import Callable

from backend.data.catalog import LocalDataCatalog
from backend.llm import LLMConfig
from backend.models.schemas import PlanState, action_dict, state_response, to_dict, variant_dict
from backend.orchestrator import PlanningPipeline
from backend.tools import LocalToolRegistry, TraceStore


class PlanningService:
    def __init__(self, catalog: LocalDataCatalog | None = None, llm_config: LLMConfig | None = None) -> None:
        self.catalog = catalog or LocalDataCatalog()
        self.pipeline = PlanningPipeline(self.catalog, llm_config)
        self.tool_registry = LocalToolRegistry(self.catalog)
        self.trace_store = TraceStore()
        self._plans: dict[str, PlanState] = {}
        self._checkpoints: dict[str, dict] = {}

    def build_plan(self, goal: str, on_progress: Callable[[str, str], None] | None = None) -> dict:
        if not goal.strip():
            raise ValueError("validation_error")
        state = self.pipeline.build(goal, on_progress=on_progress)
        self._save(state)
        return state_response(state)

    def get_plan(self, plan_id: str) -> dict:
        state = self._require_plan(plan_id)
        response = state_response(state)
        response["checkpoint"] = self._checkpoints[plan_id]
        return response

    def patch_constraints(self, plan_id: str, updates: dict) -> dict:
        state = self._require_plan(plan_id)
        rebuilt = self.pipeline.build(state.goal, updates)
        rebuilt.plan_id = plan_id
        self._save(rebuilt)
        return state_response(rebuilt)

    def build_alternatives(self, plan_id: str) -> dict:
        state = self._require_plan(plan_id)
        return {"plan_id": plan_id, "alternatives": [variant_dict(variant) for variant in state.variants]}

    def confirm_plan(self, plan_id: str, confirmed: bool) -> dict:
        if not confirmed:
            raise PermissionError("confirmation_required")
        state = self._require_plan(plan_id)
        state.status = "confirmed"
        self._save(state)
        response = state_response(state)
        response["pending_actions"] = [action_dict(action) for action in state.pending_actions]
        return response

    def execute_plan(self, plan_id: str, confirmed: bool) -> dict:
        if not confirmed:
            raise PermissionError("confirmation_required")
        state = self._require_plan(plan_id)
        if state.status not in {"confirmed", "pending_confirmation", "recovered_pending_confirmation"}:
            raise ValueError("validation_error")
        state = self.pipeline.execute(state)
        self._save(state)
        return state_response(state)

    def recover_plan(self, plan_id: str, reason: str) -> dict:
        state = self._require_plan(plan_id)
        state = self.pipeline.recover(state, reason)
        self._save(state)
        return state_response(state)

    def get_trace(self, plan_id: str) -> list[dict]:
        self._require_plan(plan_id)
        return self.trace_store.get(plan_id)

    def tool_schemas(self) -> dict:
        return {"tools": self.tool_registry.schemas()}

    def _save(self, state: PlanState) -> None:
        self._plans[state.plan_id] = state
        self.trace_store.save(state.plan_id, state.trace)
        self._checkpoints[state.plan_id] = to_dict(state.checkpoint())

    def _require_plan(self, plan_id: str) -> PlanState:
        if plan_id not in self._plans:
            raise KeyError("plan_not_found")
        return self._plans[plan_id]
