from __future__ import annotations

from uuid import uuid4

from backend.models.schemas import TraceStep


def span(
    agent: str,
    tool: str,
    status: str,
    message: str,
    kind: str,
    input_summary: dict | None = None,
    output_summary: dict | None = None,
    duration_ms: int = 0,
    metadata: dict | None = None,
) -> TraceStep:
    trace = TraceStep(agent, tool, status, message, input_summary or {}, output_summary or {}, duration_ms)
    trace.output_summary = {
        **trace.output_summary,
        "_span": {
            "span_id": f"span_{uuid4().hex[:10]}",
            "kind": kind,
            "metadata": metadata or {},
        },
    }
    return trace
