from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_NEEDS_CLARIFICATION = "needs_clarification"
RUN_STATUS_APPROVAL_REQUIRED = "approval_required"
RUN_STATUS_EXECUTING = "executing"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_VALIDATION_FAILED = "validation_failed"
RUN_STATUS_REJECTED = "rejected"
RUN_STATUS_FAILED = "failed"

RUN_TERMINAL_STATUSES = {
    RUN_STATUS_COMPLETED,
    RUN_STATUS_VALIDATION_FAILED,
    RUN_STATUS_REJECTED,
    RUN_STATUS_FAILED,
}

RUN_EVENT_STREAM_NAME = "run.event"


@dataclass(frozen=True)
class RunEvent:
    event_id: str
    run_id: str
    plan_id: str | None
    seq: int
    type: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.type,
            "run_id": self.run_id,
            "seq": self.seq,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
        if self.plan_id is not None:
            data["plan_id"] = self.plan_id
        return data


def format_sse_event(event: RunEvent) -> str:
    payload = json.dumps(
        event.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"id: {event.event_id}\nevent: {RUN_EVENT_STREAM_NAME}\ndata: {payload}\n\n"
