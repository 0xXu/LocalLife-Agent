from __future__ import annotations

import json
from typing import Any

from agents import Agent, Runner

from backend.agents.intent_extraction_tool import REQUIRED_FIELD_PRIORITY
from backend.agents.runtime import EventSink, PlanRunRequest

FINAL_VALIDATION_DONE_KEY = "__final_validation_done"


class FinalValidationTool:
    def __init__(self, *, dry_run: bool, model: str | Any | None = None) -> None:
        self.dry_run = dry_run
        self.agent = self._build_agent(model)

    async def validate(
        self,
        request: PlanRunRequest,
        *,
        constraints: dict[str, Any],
        sink: EventSink,
    ) -> dict[str, Any]:
        merged = dict(constraints)
        if self.dry_run:
            return {
                "constraints": merged,
                "missing_fields": self._missing_required_fields(merged),
            }

        await sink("agent.started", {"agent": "final_validation"})
        run_result = await Runner.run(self.agent, self._prompt(request, merged))
        final_output = getattr(run_result, "final_output", run_result)
        result = self.parse_output(final_output, merged)
        await sink("agent.completed", {"agent": "final_validation", **result})
        return result

    def parse_output(self, value: Any, constraints: dict[str, Any]) -> dict[str, Any]:
        parsed: Any
        if isinstance(value, dict):
            parsed = value
        else:
            if not isinstance(value, str):
                parsed = {}
            else:
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError:
                    parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}

        raw_constraints = parsed.get("constraints") if isinstance(parsed.get("constraints"), dict) else {}
        merged = dict(constraints)
        merged.update({str(key): item for key, item in raw_constraints.items() if item not in (None, "", [], {})})
        missing_fields = parsed.get("missing_fields")
        if not isinstance(missing_fields, list):
            missing_fields = self._missing_required_fields(merged)
        return {
            "constraints": merged,
            "missing_fields": [
                str(field)
                for field in missing_fields
                if str(field) in REQUIRED_FIELD_PRIORITY and not merged.get(str(field))
            ],
        }

    def _missing_required_fields(self, constraints: dict[str, Any]) -> list[str]:
        return [field for field in REQUIRED_FIELD_PRIORITY if not constraints.get(field)]

    def _build_agent(self, model: str | Any | None) -> Agent:
        kwargs: dict[str, Any] = {
            "name": "FinalValidationAgent",
            "instructions": (
                "Validate whether confirmed local-life planning constraints are sufficient. "
                "Return only compact JSON with keys: constraints and missing_fields. "
                "Do not invent values. missing_fields may include only: time_window, "
                "start_location, party_size, activity_preference."
            ),
        }
        if model is not None:
            kwargs["model"] = model
        return Agent(**kwargs)

    def _prompt(self, request: PlanRunRequest, constraints: dict[str, Any]) -> str:
        visible_constraints = {
            key: value
            for key, value in constraints.items()
            if not key.startswith("__")
        }
        return (
            "Validate the final local-life planning constraints after user clarification.\n"
            "Return missing_fields only if a required field is still absent or contradictory.\n\n"
            f"Original goal:\n{request.goal}\n\n"
            "Confirmed constraints JSON:\n"
            f"{json.dumps(visible_constraints, ensure_ascii=False)}\n\n"
            "User clarification answers JSON:\n"
            f"{json.dumps(request.answers, ensure_ascii=False)}"
        )
