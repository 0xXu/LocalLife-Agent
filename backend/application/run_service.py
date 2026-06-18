from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.domain.events import RUN_STATUS_QUEUED
from backend.domain.run import PlanRunRequest, RunRecord
from backend.infrastructure.event_store import EventStore


class RunService:
    def __init__(self, database_path: str = ".weekendpilot/workflow.sqlite") -> None:
        self.database_path = database_path
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
                    created_at text not null,
                    updated_at text not null
                )
                """
            )

    def create_run(self, request: PlanRunRequest) -> RunRecord:
        if not request.goal.strip():
            raise ValueError("validation_error")
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        run_id = f"run_{uuid4().hex[:12]}"
        plan_id = f"plan_{uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                insert into runs(run_id, plan_id, user_id, goal, status, current_agent, error_json, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, plan_id, request.user_id, request.goal, RUN_STATUS_QUEUED, None, None, now, now),
            )
        self.events.open_queue(run_id)
        self.events.append(run_id, plan_id, "run.started", {"status": RUN_STATUS_QUEUED})
        return self.get_run(run_id)

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
            error=None,
        )
