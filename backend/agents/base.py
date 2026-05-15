from __future__ import annotations

import json
import re
from typing import Any, Callable

from backend.models.schemas import TraceStep
from backend.observability.spans import span


class BaseAgent:
    def __init__(self, name: str, llm: Any) -> None:
        self.name = name
        self.llm = llm

    def build_trace(self, status: str, message: str, input_summary: dict, output_summary: dict, duration_ms: int = 150) -> TraceStep:
        return span(self.name, self.name.lower().replace("agent", ""), status, message, "llm", input_summary, output_summary, duration_ms, {"model": "mimo"})


def extract_json_object(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("llm_json_not_found")
    return stripped[start:end + 1]


def build_react_agent(llm, tools: list, prompt: str | Callable, checkpointer=None):
    """Build a ReAct agent subgraph. Wraps create_react_agent for future migration."""
    from langgraph.prebuilt import create_react_agent

    return create_react_agent(
        llm,
        tools=tools,
        prompt=prompt,
        checkpointer=checkpointer,
    )
