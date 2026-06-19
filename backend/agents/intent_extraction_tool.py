from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from agents import Agent, Runner

from backend.agents.runtime import EventSink, PlanRunRequest

ConstraintExtractor = Callable[[PlanRunRequest], dict[str, Any] | Awaitable[dict[str, Any]]]
CLARIFICATION_QUEUE_KEY = "__clarification_queue"
LLM_MISSING_FIELDS_KEY = "__llm_missing_fields"
REQUIRED_FIELD_PRIORITY = ["time_window", "start_location", "party_size", "activity_preference"]


class IntentExtractionTool:
    def __init__(
        self,
        *,
        dry_run: bool,
        model: str | Any | None = None,
        constraint_extractor: ConstraintExtractor | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.constraint_extractor = constraint_extractor
        self.agent = self._build_agent(model)

    async def extract(
        self,
        request: PlanRunRequest,
        *,
        base_constraints: dict[str, Any],
        sink: EventSink,
    ) -> dict[str, Any]:
        constraints = dict(base_constraints)
        if self.constraint_extractor is not None:
            extracted_or_awaitable = self.constraint_extractor(request)
            extracted = (
                await extracted_or_awaitable
                if hasattr(extracted_or_awaitable, "__await__")
                else extracted_or_awaitable
            )
            constraints.update({key: value for key, value in extracted.items() if value not in (None, "", [], {})})
            return constraints
        if self.dry_run:
            return constraints

        await sink("agent.started", {"agent": "intent_extractor"})
        run_result = await Runner.run(self.agent, self._prompt(request))
        final_output = getattr(run_result, "final_output", run_result)
        constraints.update(self.parse_output(final_output))
        await sink("agent.completed", {"agent": "intent_extractor", "constraints": constraints})
        return constraints

    def parse_output(self, value: Any) -> dict[str, Any]:
        parsed: Any
        if isinstance(value, dict):
            parsed = value
        else:
            if not isinstance(value, str):
                return {}
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
        if not isinstance(parsed, dict):
            return {}

        raw_constraints = parsed.get("constraints") if isinstance(parsed.get("constraints"), dict) else parsed
        constraints = {
            str(key): item
            for key, item in raw_constraints.items()
            if key not in {"constraints", "missing_fields", "question_plan"} and item not in (None, "", [], {})
        }
        missing_fields = parsed.get("missing_fields")
        if isinstance(missing_fields, list):
            constraints[LLM_MISSING_FIELDS_KEY] = [
                str(field)
                for field in missing_fields
                if str(field) in REQUIRED_FIELD_PRIORITY
            ]
        return constraints

    def _build_agent(self, model: str | Any | None) -> Agent:
        kwargs: dict[str, Any] = {
            "name": "IntentExtractorAgent",
            "instructions": (
                "Extract structured local-life planning constraints from the user goal. "
                "Return only compact JSON with keys: constraints and missing_fields. "
                "constraints may contain: time_window, start_location, party_size, scenario, "
                "budget, diet_preferences, accessibility, transport_preference, activity_preference. "
                "missing_fields is ordered and may include: time_window, start_location, "
                "party_size, activity_preference."
            ),
        }
        if model is not None:
            kwargs["model"] = model
        return Agent(**kwargs)

    def _prompt(self, request: PlanRunRequest) -> str:
        return (
            "User goal:\n"
            f"{request.goal}\n\n"
            "Existing answers JSON:\n"
            f"{json.dumps(request.answers, ensure_ascii=False)}\n\n"
            "Return only JSON object with keys: constraints and missing_fields. "
            "constraints is an object containing known values only. missing_fields is an ordered array "
            "from these possible fields when missing: time_window, start_location, party_size, activity_preference."
        )
