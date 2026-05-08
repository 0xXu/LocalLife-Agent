from __future__ import annotations

from backend.models.schemas import TraceStep, to_dict


class TraceStore:
    def __init__(self) -> None:
        self._traces: dict[str, list[TraceStep]] = {}

    def save(self, plan_id: str, trace: list[TraceStep]) -> None:
        self._traces[plan_id] = list(trace)

    def get(self, plan_id: str) -> list[dict]:
        return [to_dict(step) for step in self._traces.get(plan_id, [])]
