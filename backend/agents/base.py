from __future__ import annotations

from abc import ABC, abstractmethod

from backend.models.schemas import PlanState, TraceStep


class BaseAgent(ABC):
    name = "BaseAgent"
    tool = "none"

    def run(self, state: PlanState) -> PlanState:
        before = self.summarize_input(state)
        state = self.execute(state)
        after = self.summarize_output(state)
        state.add_trace(
            TraceStep(
                agent=self.name,
                tool=self.tool,
                status="ok" if not state.errors else "warning",
                message=self.message(state),
                input_summary=before,
                output_summary=after,
                duration_ms=self.duration_ms(),
            )
        )
        return state

    @abstractmethod
    def execute(self, state: PlanState) -> PlanState:
        ...

    def summarize_input(self, state: PlanState) -> dict:
        return {"status": state.status}

    def summarize_output(self, state: PlanState) -> dict:
        return {"status": state.status}

    def message(self, state: PlanState) -> str:
        return f"{self.name} completed."

    def duration_ms(self) -> int:
        return 180

