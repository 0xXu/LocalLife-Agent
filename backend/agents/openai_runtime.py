from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from agents import Agent, Runner, set_tracing_disabled
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from backend.agents.guardrails import require_grounded_action
from backend.agents.runtime import (
    EventSink,
    ExecuteActionsRequest,
    ExecutionResult,
    PlanRunRequest,
    PlanRunResult,
    RuntimeContext,
)
from backend.llm.config import LLMConfig

ConstraintExtractor = Callable[[PlanRunRequest], dict[str, Any] | Awaitable[dict[str, Any]]]


class OpenAIAgentsRuntime:
    def __init__(
        self,
        dry_run: bool = False,
        model: str | None = None,
        planner_model: Any | None = None,
        constraint_extractor: ConstraintExtractor | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.model = model
        self.constraint_extractor = constraint_extractor
        self.planner = self._build_planner(planner_model or model)
        self.intent_extractor = self._build_intent_extractor(planner_model or model)

    @classmethod
    def from_llm_config(cls, config: LLMConfig) -> "OpenAIAgentsRuntime":
        if not config.remote_enabled or not config.is_configured:
            return cls(dry_run=True, model=config.model)

        client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )
        set_tracing_disabled(True)
        planner_model = OpenAIChatCompletionsModel(model=config.model, openai_client=client)
        return cls(dry_run=False, model=config.model, planner_model=planner_model)

    def _build_planner(self, model: str | Any | None) -> Agent:
        kwargs: dict[str, Any] = {
            "name": "PlannerAgent",
            "instructions": "Create grounded local-life plans. Return only validated product-safe output.",
        }
        if model is not None:
            kwargs["model"] = model
        return Agent(**kwargs)

    def _build_intent_extractor(self, model: str | Any | None) -> Agent:
        kwargs: dict[str, Any] = {
            "name": "IntentExtractorAgent",
            "instructions": (
                "Extract structured local-life planning constraints from the user goal. "
                "Return only compact JSON with keys: time_window, start_location, party_size, "
                "scenario, budget, diet_preferences, accessibility, transport_preference, "
                "activity_preference. Omit unknown values."
            ),
        }
        if model is not None:
            kwargs["model"] = model
        return Agent(**kwargs)

    async def start_plan(
        self,
        request: PlanRunRequest,
        context: RuntimeContext,
        sink: EventSink,
    ) -> PlanRunResult:
        await sink("agent.started", {"agent": "planner"})
        constraints = await self._extract_constraints(request, sink)
        missing_fields = self._missing_required_fields(constraints)
        if missing_fields:
            clarification = self._clarification_for(missing_fields[0], constraints)
            await sink("clarification.required", clarification)
            return PlanRunResult(
                status="needs_clarification",
                clarification=clarification,
                validation={"valid": False, "missing_fields": missing_fields},
            )

        if self.dry_run:
            pending_action = {
                "action_id": "act_demo_reservation",
                "tool": "create_reservation",
                "target": "demo_restaurant",
                "label": "预约餐厅",
                "payload": {"place_id": "demo_restaurant", "people": 3},
            }
            require_grounded_action(pending_action)
            await sink("approval.required", {"plan_id": context.plan_id, "actions": [pending_action]})
            return PlanRunResult(
                status="approval_required",
                plan={
                    "id": context.plan_id,
                    "status": "approval_required",
                    "title": "本地生活计划",
                    "summary": request.goal,
                    "itinerary": [],
                    "actions": [pending_action],
                    "receipts": [],
                },
                validation={"valid": True},
                pending_actions=[pending_action],
            )

        run_result = await Runner.run(self.planner, request.goal)
        final_output = getattr(run_result, "final_output", run_result)
        plan = {
            "id": context.plan_id,
            "goal": request.goal,
            "user_id": request.user_id,
            "output": final_output,
        }
        return PlanRunResult(status="completed", plan=plan, raw_output=run_result)

    async def _extract_constraints(self, request: PlanRunRequest, sink: EventSink) -> dict[str, Any]:
        constraints = dict(request.constraints)
        constraints.update({key: value for key, value in request.answers.items() if value not in (None, "")})
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
        prompt = (
            "User goal:\n"
            f"{request.goal}\n\n"
            "Existing answers JSON:\n"
            f"{json.dumps(request.answers, ensure_ascii=False)}\n\n"
            "Return only JSON object of extracted constraints."
        )
        run_result = await Runner.run(self.intent_extractor, prompt)
        final_output = getattr(run_result, "final_output", run_result)
        extracted = self._parse_extracted_constraints(final_output)
        constraints.update(extracted)
        await sink("agent.completed", {"agent": "intent_extractor", "constraints": constraints})
        return constraints

    def _parse_extracted_constraints(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return {str(key): item for key, item in value.items() if item not in (None, "", [], {})}
        if not isinstance(value, str):
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {str(key): item for key, item in parsed.items() if item not in (None, "", [], {})}

    def _missing_required_fields(self, constraints: dict[str, Any]) -> list[str]:
        priority = ["time_window"]
        return [field for field in priority if not constraints.get(field)]

    def _clarification_for(self, field: str, constraints: dict[str, Any]) -> dict[str, Any]:
        if field == "time_window":
            return {
                "question": {
                    "id": "time_window",
                    "label": "今天大概几点开始？",
                    "description": "时间范围会影响营业状态、路线顺序和预约动作。",
                    "kind": "time",
                    "required": True,
                    "options": [
                        {"label": "今天下午 2 点", "value": "今天下午 2 点"},
                        {"label": "今天下午 4 点", "value": "今天下午 4 点"},
                        {"label": "今晚 7 点", "value": "今晚 7 点"},
                    ],
                    "allow_custom": True,
                },
                "partial_constraints": constraints,
                "missing_fields": [field],
            }
        raise RuntimeError(f"unsupported_clarification_field:{field}")

    async def execute_actions(
        self,
        request: ExecuteActionsRequest,
        context: RuntimeContext,
        sink: EventSink,
    ) -> ExecutionResult:
        await sink("actions.execution.started", {"plan_id": context.plan_id, "action_ids": request.action_ids})
        receipts = [
            {
                "id": f"receipt_{index + 1}",
                "action_id": action_id,
                "plan_id": context.plan_id,
                "status": "confirmed",
                "run_id": context.run_id,
            }
            for index, action_id in enumerate(request.action_ids)
        ]
        await sink("actions.execution.completed", {"plan_id": context.plan_id, "receipts": receipts})
        return ExecutionResult(status="completed", receipts=receipts)
