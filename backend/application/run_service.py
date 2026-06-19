from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.agents.runtime import AgentRuntime, PlanRunRequest as RuntimePlanRunRequest, RuntimeContext
from backend.domain.events import (
    RUN_STATUS_FAILED,
    RUN_STATUS_NEEDS_CLARIFICATION,
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
)
from backend.domain.run import PlanRunRequest as DomainPlanRunRequest, RunRecord
from backend.infrastructure.event_store import EventStore


class RunService:
    def __init__(
        self,
        database_path: str = ".weekendpilot/workflow.sqlite",
        runtime: AgentRuntime | None = None,
    ) -> None:
        self.database_path = database_path
        self.runtime = runtime or OpenAIAgentsRuntime(dry_run=True)
        self._workers: list[threading.Thread] = []
        self._transition_lock = threading.RLock()
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self.events = EventStore(database_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists runs (
                    run_id text primary key,
                    plan_id text not null,
                    user_id text not null,
                    goal text not null,
                    status text not null,
                    current_agent text,
                    error_json text,
                    answers_json text,
                    constraints_json text,
                    current_question_json text,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            self._ensure_run_context_columns(conn)
            conn.execute(
                """
                create table if not exists plans (
                    plan_id text primary key,
                    run_id text not null,
                    status text not null,
                    plan_json text not null,
                    actions_json text not null,
                    receipts_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )

    def _ensure_run_context_columns(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("pragma table_info(runs)").fetchall()}
        for column in ("answers_json", "constraints_json", "current_question_json"):
            if column not in columns:
                conn.execute(f"alter table runs add column {column} text")

    def create_run(self, request: DomainPlanRunRequest) -> RunRecord:
        if not request.goal.strip():
            raise ValueError("validation_error")
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        run_id = f"run_{uuid4().hex[:12]}"
        plan_id = f"plan_{uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                insert into runs(
                    run_id, plan_id, user_id, goal, status, current_agent, error_json,
                    answers_json, constraints_json, current_question_json, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    plan_id,
                    request.user_id,
                    request.goal,
                    RUN_STATUS_QUEUED,
                    None,
                    None,
                    self._json({}),
                    self._json({}),
                    None,
                    now,
                    now,
                ),
            )
        self.events.open_queue(run_id)
        self.events.append(run_id, plan_id, "run.started", {"status": RUN_STATUS_QUEUED})
        worker = threading.Thread(target=self._run_worker_thread, args=(run_id,), daemon=True)
        self._workers.append(worker)
        worker.start()
        return self.get_run(run_id)

    def wait_for_workers(self, timeout: float = 1.0) -> None:
        for worker in list(self._workers):
            worker.join(timeout=timeout)
            if not worker.is_alive():
                self._workers.remove(worker)

    def get_run(self, run_id: str) -> RunRecord:
        with self._connect() as conn:
            row = conn.execute("select * from runs where run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError("run_not_found")
        return RunRecord(
            run_id=row["run_id"],
            plan_id=row["plan_id"],
            user_id=row["user_id"],
            goal=row["goal"],
            status=row["status"],
            current_agent=row["current_agent"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error=json.loads(row["error_json"]) if row["error_json"] else None,
        )

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from plans where plan_id = ?", (plan_id,)).fetchone()
        if row is None:
            raise KeyError("plan_not_found")
        return {
            "plan_id": row["plan_id"],
            "run_id": row["run_id"],
            "status": row["status"],
            "plan": json.loads(row["plan_json"]),
            "actions": json.loads(row["actions_json"]),
            "receipts": json.loads(row["receipts_json"]),
            "trace": [event.to_dict() for event in self.events.replay(row["run_id"])],
        }

    def list_plans(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("select * from plans order by updated_at desc").fetchall()
        plans = [self._plan_summary(row) for row in rows]
        return {"plans": plans, "total": len(plans)}

    def update_run_status(self, run_id: str, *, status: str, current_agent: str | None) -> None:
        self._update_run(run_id, status=status, current_agent=current_agent)

    def update_plan_status(self, plan_id: str, status: str) -> None:
        plan = self.get_plan(plan_id)
        plan_payload = dict(plan["plan"])
        plan_payload["status"] = status
        self._save_plan(
            plan_id=plan_id,
            run_id=plan["run_id"],
            status=status,
            plan=plan_payload,
            actions=plan["actions"],
            receipts=plan["receipts"],
        )

    def add_receipts(self, plan_id: str, receipts: list[dict[str, Any]], status: str) -> None:
        plan = self.get_plan(plan_id)
        current_receipts = list(plan["receipts"])
        current_receipts.extend(receipts)
        receipt_by_action_id = {
            str(receipt["action_id"]): receipt for receipt in receipts if "action_id" in receipt
        }
        actions = []
        for action in plan["actions"]:
            action_payload = dict(action)
            receipt = receipt_by_action_id.get(str(action_payload.get("action_id")))
            if receipt is not None:
                action_payload["status"] = str(receipt.get("status", "completed"))
                if "id" in receipt:
                    action_payload["receipt_id"] = receipt["id"]
            actions.append(action_payload)
        plan_payload = dict(plan["plan"])
        plan_payload["status"] = status
        plan_payload["receipts"] = current_receipts
        plan_payload["actions"] = actions
        self._save_plan(
            plan_id=plan_id,
            run_id=plan["run_id"],
            status=status,
            plan=plan_payload,
            actions=actions,
            receipts=current_receipts,
        )

    def submit_clarification(self, run_id: str, question_id: str, answer: Any) -> RunRecord:
        with self._transition_lock:
            record = self.get_run(run_id)
            answers, _constraints, current_question = self._run_context(run_id)
            if record.status != RUN_STATUS_NEEDS_CLARIFICATION or current_question is None:
                raise ValueError("clarification_not_required")
            if current_question.get("id") != question_id:
                raise ValueError("clarification_question_mismatch")

            answers[question_id] = answer
            self._save_run_context(run_id, answers=answers, current_question=None)
            self._update_run(run_id, status=RUN_STATUS_RUNNING, current_agent="planner")
        self.events.open_queue(run_id)
        self.events.append(
            run_id,
            record.plan_id,
            "run.running",
            {"status": RUN_STATUS_RUNNING, "current_agent": "planner"},
        )
        worker = threading.Thread(target=self._run_worker_thread, args=(run_id,), daemon=True)
        self._workers.append(worker)
        worker.start()
        return self.get_run(run_id)

    def _run_worker_thread(self, run_id: str) -> None:
        try:
            asyncio.run(self._run_worker(run_id))
        except sqlite3.Error:
            pass

    async def _run_worker(self, run_id: str) -> None:
        record = self.get_run(run_id)
        answers, constraints, _current_question = self._run_context(run_id)
        approval_required_emitted = False
        paused_for_user = False

        async def sink(event_type: str, payload: dict[str, Any]) -> None:
            nonlocal approval_required_emitted
            if event_type == "approval.required":
                approval_required_emitted = True
            if event_type == "clarification.required":
                self._persist_clarification_pause(run_id, payload)
            self.events.append(run_id, record.plan_id, event_type, payload)

        try:
            if record.status != RUN_STATUS_RUNNING:
                self._update_run(run_id, status=RUN_STATUS_RUNNING, current_agent="planner")
                self.events.append(
                    run_id,
                    record.plan_id,
                    "run.running",
                    {"status": RUN_STATUS_RUNNING, "current_agent": "planner"},
                )
            result = await self.runtime.start_plan(
                RuntimePlanRunRequest(
                    goal=record.goal,
                    user_id=record.user_id,
                    answers=answers,
                    constraints=constraints,
                ),
                RuntimeContext(run_id=run_id, plan_id=record.plan_id, user_id=record.user_id),
                sink,
            )
            if result.status == RUN_STATUS_NEEDS_CLARIFICATION:
                if result.clarification is None:
                    raise RuntimeError("runtime_missing_clarification_question")
                self._persist_clarification_pause(run_id, result.clarification)
                paused_for_user = True
                return
            receipts = list(result.plan.get("receipts", [])) if isinstance(result.plan, dict) else []
            self._save_plan(
                plan_id=record.plan_id,
                run_id=run_id,
                status=result.status,
                plan=result.plan,
                actions=result.pending_actions,
                receipts=receipts,
            )
            if result.status == "approval_required" and not approval_required_emitted:
                self.events.append(
                    run_id,
                    record.plan_id,
                    "approval.required",
                    {"plan_id": record.plan_id, "actions": result.pending_actions},
                )
            self._update_run(run_id, status=result.status, current_agent=None)
            self.events.append(run_id, record.plan_id, "run.completed", {"status": result.status})
            if result.status == "approval_required":
                paused_for_user = True
        except Exception as exc:
            error = {"code": "runtime_failed", "message": str(exc) or exc.__class__.__name__}
            self._update_run(run_id, status=RUN_STATUS_FAILED, current_agent=None, error=error)
            self.events.append(run_id, record.plan_id, "run.failed", {"status": RUN_STATUS_FAILED, "error": error})
        finally:
            if not paused_for_user:
                self.events.close_queue(run_id)

    def _persist_clarification_pause(self, run_id: str, clarification: dict[str, Any]) -> None:
        question = clarification.get("question")
        if not isinstance(question, dict):
            raise RuntimeError("runtime_missing_clarification_question")
        question_id = question.get("id")
        with self._transition_lock:
            answers, _constraints, current_question = self._run_context(run_id)
            if question_id is not None and question_id in answers:
                return
            if current_question == question and self.get_run(run_id).status == RUN_STATUS_NEEDS_CLARIFICATION:
                return
            partial_constraints = clarification.get("partial_constraints")
            self._save_run_context(
                run_id,
                constraints=partial_constraints if isinstance(partial_constraints, dict) else None,
                current_question=question,
            )
            self._update_run(run_id, status=RUN_STATUS_NEEDS_CLARIFICATION, current_agent=None)

    def _update_run(
        self,
        run_id: str,
        *,
        status: str,
        current_agent: str | None,
        error: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            conn.execute(
                """
                update runs
                set status = ?, current_agent = ?, error_json = ?, updated_at = ?
                where run_id = ?
                """,
                (status, current_agent, self._json(error) if error is not None else None, now, run_id),
            )

    def _run_context(
        self,
        run_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
        with self._connect() as conn:
            row = conn.execute(
                """
                select answers_json, constraints_json, current_question_json
                from runs
                where run_id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError("run_not_found")
        answers = json.loads(row["answers_json"]) if row["answers_json"] else {}
        constraints = json.loads(row["constraints_json"]) if row["constraints_json"] else {}
        current_question = json.loads(row["current_question_json"]) if row["current_question_json"] else None
        return answers, constraints, current_question

    def _save_run_context(
        self,
        run_id: str,
        *,
        answers: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
        current_question: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        assignments = ["updated_at = ?"]
        values: list[Any] = [now]
        if answers is not None:
            assignments.append("answers_json = ?")
            values.append(self._json(answers))
        if constraints is not None:
            assignments.append("constraints_json = ?")
            values.append(self._json(constraints))
        assignments.append("current_question_json = ?")
        values.append(self._json(current_question) if current_question is not None else None)
        values.append(run_id)
        with self._connect() as conn:
            conn.execute(
                f"""
                update runs
                set {", ".join(assignments)}
                where run_id = ?
                """,
                values,
            )

    def _save_plan(
        self,
        *,
        plan_id: str,
        run_id: str,
        status: str,
        plan: dict[str, Any],
        actions: list[dict[str, Any]],
        receipts: list[dict[str, Any]],
    ) -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            conn.execute(
                """
                insert into plans(plan_id, run_id, status, plan_json, actions_json, receipts_json, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(plan_id) do update set
                    status = excluded.status,
                    plan_json = excluded.plan_json,
                    actions_json = excluded.actions_json,
                    receipts_json = excluded.receipts_json,
                    updated_at = excluded.updated_at
                """,
                (
                    plan_id,
                    run_id,
                    status,
                    self._json(plan),
                    self._json(actions),
                    self._json(receipts),
                    now,
                    now,
                ),
            )

    def _plan_summary(self, row: sqlite3.Row) -> dict[str, Any]:
        plan = json.loads(row["plan_json"])
        itinerary = plan.get("itinerary")
        if not isinstance(itinerary, list):
            itinerary = []
        tags = plan.get("tags")
        if not isinstance(tags, list):
            tags = ["本地生活"]
        status = self._summary_status(str(plan.get("status") or row["status"]))
        return {
            "id": row["plan_id"],
            "title": str(plan.get("title") or "未命名计划"),
            "status": status,
            "summary": str(plan.get("summary") or plan.get("goal") or ""),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "tags": [str(tag) for tag in tags],
            "location": plan.get("location") if isinstance(plan.get("location"), str) else None,
            "estimated_cost": self._estimated_cost(plan),
            "itinerary_count": len(itinerary),
        }

    def _estimated_cost(self, plan: dict[str, Any]) -> str | None:
        overview = plan.get("overview")
        if isinstance(overview, dict) and overview.get("estimatedCost") is not None:
            return str(overview["estimatedCost"])
        if plan.get("estimated_cost") is not None:
            return str(plan["estimated_cost"])
        return None

    def _summary_status(self, status: str) -> str:
        return {
            "approval_required": "pending_approval",
            "rejected": "cancelled",
            "failed": "validation_failed",
        }.get(status, status)

    def _json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
