from __future__ import annotations

from backend.agents import RecoveryAgent
from backend.models.schemas import PlanState


class RecoveryLoop:
    def __init__(self, recovery_agent: RecoveryAgent) -> None:
        self.recovery_agent = recovery_agent

    def run(self, state: PlanState, reason: str) -> PlanState:
        if reason != "restaurant_unavailable":
            state.errors.append(f"unsupported_recovery_reason:{reason}")
            return state
        return self.recovery_agent.run(state)

