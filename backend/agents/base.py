from __future__ import annotations

import json
import re
from typing import Any

from backend.models.schemas import TraceStep
from backend.observability.spans import span


class BaseAgent:
    def __init__(self, name: str, llm: Any) -> None:
        self.name = name
        self.llm = llm
        self._last_messages: list[dict[str, str]] = []

    def run_llm(self, system_prompt: str, context: dict[str, Any], max_tokens: int = 1024) -> dict[str, Any] | None:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ]
        self._last_messages = messages
        try:
            content = ""
            for token in self.llm.chat_stream(messages):
                content += token
            return json.loads(extract_json_object(content))
        except Exception:
            return None

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
