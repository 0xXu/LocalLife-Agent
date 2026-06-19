from __future__ import annotations

from typing import Any

from backend.agents.runtime import ExecuteActionsRequest, RuntimeContext
from backend.application.run_service import RunService
from backend.domain.events import RUN_STATUS_COMPLETED, RUN_STATUS_EXECUTING, RUN_STATUS_REJECTED
from backend.domain.run import RunRecord


class ApprovalService:
    def __init__(self, run_service: RunService) -> None:
        self.run_service = run_service

    async def approve_actions(self, run_id: str, action_ids: list[str]) -> RunRecord:
        if not action_ids:
            raise ValueError("validation_error")

        record = self.run_service.get_run(run_id)
        plan = self.run_service.get_plan(record.plan_id)
        known_action_ids = {str(action["action_id"]) for action in plan["actions"] if "action_id" in action}
        missing_action_ids = [action_id for action_id in action_ids if action_id not in known_action_ids]
        if missing_action_ids:
            raise ValueError("invalid_action_id")

        self.run_service.update_run_status(run_id, status=RUN_STATUS_EXECUTING, current_agent="executor")
        self.run_service.events.append(
            run_id,
            record.plan_id,
            "run.executing",
            {"status": RUN_STATUS_EXECUTING, "action_ids": action_ids},
        )

        async def sink(event_type: str, payload: dict[str, Any]) -> None:
            self.run_service.events.append(run_id, record.plan_id, event_type, payload)

        result = await self.run_service.runtime.execute_actions(
            ExecuteActionsRequest(action_ids=action_ids),
            RuntimeContext(run_id=run_id, plan_id=record.plan_id, user_id=record.user_id),
            sink,
        )
        self.run_service.add_receipts(record.plan_id, result.receipts, status=RUN_STATUS_COMPLETED)
        self.run_service.update_run_status(run_id, status=RUN_STATUS_COMPLETED, current_agent=None)
        self.run_service.events.append(run_id, record.plan_id, "run.completed", {"status": RUN_STATUS_COMPLETED})
        self.run_service.events.close_queue(run_id)
        return self.run_service.get_run(run_id)

    def reject_run(self, run_id: str, reason: str) -> RunRecord:
        record = self.run_service.get_run(run_id)
        self.run_service.update_run_status(run_id, status=RUN_STATUS_REJECTED, current_agent=None)
        self.run_service.update_plan_status(record.plan_id, RUN_STATUS_REJECTED)
        self.run_service.events.append(
            run_id,
            record.plan_id,
            "run.rejected",
            {"status": RUN_STATUS_REJECTED, "reason": reason},
        )
        self.run_service.events.close_queue(run_id)
        return self.run_service.get_run(run_id)
