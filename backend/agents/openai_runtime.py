from __future__ import annotations

from typing import Any

from agents import Agent, Runner

from backend.agents.guardrails import require_grounded_action
from backend.agents.runtime import (
    EventSink,
    ExecuteActionsRequest,
    ExecutionResult,
    PlanRunRequest,
    PlanRunResult,
    RuntimeContext,
)


class OpenAIAgentsRuntime:
    def __init__(self, dry_run: bool = False, model: str | None = None) -> None:
        self.dry_run = dry_run
        self.model = model
        self.planner = self._build_planner(model)

    def _build_planner(self, model: str | None) -> Agent:
        kwargs: dict[str, Any] = {
            "name": "PlannerAgent",
            "instructions": "Create grounded local-life plans. Return only validated product-safe output.",
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

        if self.dry_run:
            if "time_window" not in request.answers:
                clarification = {
                    "question": {
                        "id": "time_window",
                        "label": "今天下午大概几点开始？",
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
                    "partial_constraints": request.constraints,
                    "missing_fields": ["time_window"],
                }
                await sink("clarification.required", clarification)
                return PlanRunResult(
                    status="needs_clarification",
                    clarification=clarification,
                    validation={"valid": False, "missing_fields": ["time_window"]},
                )

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
