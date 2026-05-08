from __future__ import annotations

from backend.models.schemas import PlanState, state_response, to_dict
from backend.orchestrator import PlanningPipeline
from backend.tools import TraceStore


class PlanningService:
    def __init__(self) -> None:
        self.pipeline = PlanningPipeline()
        self.trace_store = TraceStore()
        self._plans: dict[str, PlanState] = {}

    def build_plan(self, goal: str) -> dict:
        state = self.pipeline.build(goal)
        self._plans[state.plan_id] = state
        self.trace_store.save(state.plan_id, state.trace)
        return state_response(state)

    def execute_plan(self, plan_id: str, confirmed: bool) -> dict:
        if not confirmed:
            raise PermissionError("Side-effect actions require user confirmation.")
        state = self._require_plan(plan_id)
        state = self.pipeline.execute(state)
        self._plans[plan_id] = state
        self.trace_store.save(plan_id, state.trace)
        response = state_response(state)
        response["receipts"] = [to_dict(receipt) for receipt in state.receipts]
        return response

    def recover_plan(self, plan_id: str, reason: str) -> dict:
        state = self._require_plan(plan_id)
        state = self.pipeline.recover(state, reason)
        self._plans[state.plan_id] = state
        self._plans[plan_id] = state
        self.trace_store.save(plan_id, state.trace)
        return state_response(state)

    def get_trace(self, plan_id: str) -> list[dict]:
        return self.trace_store.get(plan_id)

    def _require_plan(self, plan_id: str) -> PlanState:
        if plan_id not in self._plans:
            raise KeyError(f"Unknown plan: {plan_id}")
        return self._plans[plan_id]

