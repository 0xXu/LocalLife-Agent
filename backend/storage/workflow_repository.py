from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str) -> Any:
    return json.loads(value)


class WorkflowRepository:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists plan_threads (
                    thread_id text primary key,
                    run_id text not null,
                    plan_id text not null,
                    user_id text not null,
                    status text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists plan_revisions (
                    revision_id text primary key,
                    plan_id text not null,
                    version integer not null,
                    phase text not null,
                    goal text not null,
                    constraints_json text not null,
                    plan_json text not null,
                    validation_json text not null,
                    created_at text not null
                );

                create table if not exists action_ledger (
                    action_id text primary key,
                    revision_id text not null,
                    tool text not null,
                    status text not null,
                    idempotency_key text not null unique,
                    payload_json text not null,
                    receipt_id text,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists action_attempts (
                    attempt_id text primary key,
                    action_id text not null,
                    status text not null,
                    request_json text not null,
                    response_json text not null,
                    error text,
                    created_at text not null
                );

                create table if not exists receipts (
                    receipt_id text primary key,
                    action_id text not null,
                    revision_id text not null,
                    tool text not null,
                    status text not null,
                    detail text not null,
                    payload_json text not null,
                    created_at text not null
                );
                """
            )

    def create_thread(self, thread_id: str, run_id: str, plan_id: str, user_id: str, status: str) -> None:
        timestamp = _now()
        with self._connect() as conn:
            conn.execute(
                """
                insert into plan_threads(thread_id, run_id, plan_id, user_id, status, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (thread_id, run_id, plan_id, user_id, status, timestamp, timestamp),
            )

    def update_thread_status(self, thread_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "update plan_threads set status = ?, updated_at = ? where thread_id = ?",
                (status, _now(), thread_id),
            )

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select * from plan_threads where thread_id = ?", (thread_id,)).fetchone()
        return dict(row) if row else None

    def save_revision(
        self,
        revision_id: str,
        plan_id: str,
        version: int,
        phase: str,
        goal: str,
        constraints: dict[str, Any],
        plan: dict[str, Any],
        validation: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into plan_revisions(
                    revision_id,
                    plan_id,
                    version,
                    phase,
                    goal,
                    constraints_json,
                    plan_json,
                    validation_json,
                    created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    plan_id,
                    version,
                    phase,
                    goal,
                    _json_dumps(constraints),
                    _json_dumps(plan),
                    _json_dumps(validation),
                    _now(),
                ),
            )

    def get_latest_revision(self, plan_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select * from plan_revisions
                where plan_id = ?
                order by version desc, created_at desc
                limit 1
                """,
                (plan_id,),
            ).fetchone()
        return self._revision_from_row(row) if row else None

    def list_revisions(self, plan_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from plan_revisions where plan_id = ? order by version asc, created_at asc",
                (plan_id,),
            ).fetchall()
        return [self._revision_from_row(row) for row in rows]

    def upsert_action(
        self,
        action_id: str,
        revision_id: str,
        tool: str,
        status: str,
        idempotency_key: str,
        payload: dict[str, Any],
        receipt_id: str | None,
    ) -> None:
        timestamp = _now()
        with self._connect() as conn:
            conn.execute(
                """
                insert into action_ledger(
                    action_id,
                    revision_id,
                    tool,
                    status,
                    idempotency_key,
                    payload_json,
                    receipt_id,
                    created_at,
                    updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(action_id) do update set
                    revision_id = excluded.revision_id,
                    tool = excluded.tool,
                    status = excluded.status,
                    idempotency_key = excluded.idempotency_key,
                    payload_json = excluded.payload_json,
                    receipt_id = excluded.receipt_id,
                    updated_at = excluded.updated_at
                """,
                (
                    action_id,
                    revision_id,
                    tool,
                    status,
                    idempotency_key,
                    _json_dumps(payload),
                    receipt_id,
                    timestamp,
                    timestamp,
                ),
            )

    def list_actions(self, revision_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from action_ledger where revision_id = ? order by created_at asc",
                (revision_id,),
            ).fetchall()
        return [self._action_from_row(row) for row in rows]

    def get_action_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "select * from action_ledger where idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return self._action_from_row(row) if row else None

    def append_attempt(
        self,
        attempt_id: str,
        action_id: str,
        status: str,
        request: dict[str, Any],
        response: dict[str, Any],
        error: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into action_attempts(attempt_id, action_id, status, request_json, response_json, error, created_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (attempt_id, action_id, status, _json_dumps(request), _json_dumps(response), error, _now()),
            )

    def list_attempts(self, action_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from action_attempts where action_id = ? order by created_at asc",
                (action_id,),
            ).fetchall()
        return [self._attempt_from_row(row) for row in rows]

    def append_receipt(
        self,
        receipt_id: str,
        action_id: str,
        revision_id: str,
        tool: str,
        status: str,
        detail: str,
        payload: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into receipts(receipt_id, action_id, revision_id, tool, status, detail, payload_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (receipt_id, action_id, revision_id, tool, status, detail, _json_dumps(payload), _now()),
            )

    def list_receipts(self, revision_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from receipts where revision_id = ? order by created_at asc",
                (revision_id,),
            ).fetchall()
        return [self._receipt_from_row(row) for row in rows]

    def _revision_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        revision = dict(row)
        revision["constraints"] = _json_loads(revision.pop("constraints_json"))
        revision["plan"] = _json_loads(revision.pop("plan_json"))
        revision["validation"] = _json_loads(revision.pop("validation_json"))
        return revision

    def _action_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        action = dict(row)
        action["payload"] = _json_loads(action.pop("payload_json"))
        return action

    def _attempt_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        attempt = dict(row)
        attempt["request"] = _json_loads(attempt.pop("request_json"))
        attempt["response"] = _json_loads(attempt.pop("response_json"))
        return attempt

    def _receipt_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        receipt = dict(row)
        receipt["payload"] = _json_loads(receipt.pop("payload_json"))
        return receipt
