from __future__ import annotations

from backend.agents import (
    CandidateSearchAgent,
    ContextBuilderAgent,
    ExecutionAgent,
    IntentParserAgent,
    PlanValidatorAgent,
    RankerAgent,
    RecoveryAgent,
    RouteSchedulerAgent,
)
from backend.models.schemas import PlanState
from backend.orchestrator.recovery_loop import RecoveryLoop
from backend.tools import AvailabilityTool, ExecutionTool, POIRepository, RoutingTool


class PlanningPipeline:
    def __init__(self) -> None:
        self.repository = POIRepository()
        self.availability = AvailabilityTool()
        self.routing = RoutingTool()
        self.execution = ExecutionTool()
        self.agents = [
            IntentParserAgent(),
            ContextBuilderAgent(),
            CandidateSearchAgent(self.repository),
            RankerAgent(),
            RouteSchedulerAgent(self.routing),
            PlanValidatorAgent(self.repository, self.availability),
        ]
        self.execution_agent = ExecutionAgent(self.execution)
        self.recovery_loop = RecoveryLoop(RecoveryAgent(self.repository))

    def build(self, goal: str) -> PlanState:
        state = PlanState(goal=goal)
        for agent in self.agents:
            state = agent.run(state)
            if state.status == "needs_recovery":
                break
        return state

    def execute(self, state: PlanState) -> PlanState:
        return self.execution_agent.run(state)

    def recover(self, state: PlanState, reason: str) -> PlanState:
        return self.recovery_loop.run(state, reason)

