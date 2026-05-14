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
        conn.execute("pragma foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            self._reset_legacy_workflow_schema(conn)
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
                    revision_id text not null references plan_revisions(revision_id),
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
                    action_id text not null references action_ledger(action_id),
                    status text not null,
                    request_json text not null,
                    response_json text not null,
                    error text,
                    created_at text not null
                );

                create table if not exists receipts (
                    receipt_id text primary key,
                    action_id text not null references action_ledger(action_id),
                    revision_id text not null references plan_revisions(revision_id),
                    tool text not null,
                    status text not null,
                    detail text not null,
                    payload_json text not null,
                    created_at text not null
                );
                """
            )
            conn.execute(
                """
                create unique index if not exists idx_plan_revisions_plan_id_version
                on plan_revisions(plan_id, version)
                """
            )

    def _reset_legacy_workflow_schema(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("pragma table_info(receipts)").fetchall()}
        if not columns or ("message" not in columns and "metadata_json" not in columns):
            return
        conn.executescript(
            """
            drop table if exists receipts;
            drop table if exists action_attempts;
            drop table if exists action_ledger;
            drop table if exists plan_revisions;
            drop table if exists plan_threads;
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

    def get_thread_by_plan(self, plan_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select * from plan_threads
                where plan_id = ?
                order by created_at desc, thread_id desc
                limit 1
                """,
                (plan_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_thread_by_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select * from plan_threads
                where run_id = ?
                order by created_at desc, thread_id desc
                limit 1
                """,
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_thread_status_for_plan(self, plan_id: str, status: str) -> None:
        with self._connect() as conn:
            result = conn.execute(
                """
                update plan_threads
                set status = ?, updated_at = ?
                where plan_id = ?
                """,
                (status, _now(), plan_id),
            )
            if result.rowcount == 0:
                raise ValueError(f"unknown_plan_id:{plan_id}")

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
                order by version desc, created_at desc, revision_id desc
                limit 1
                """,
                (plan_id,),
            ).fetchone()
        return self._revision_from_row(row) if row else None

    def list_revisions(self, plan_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select * from plan_revisions
                where plan_id = ?
                order by version asc, created_at asc, revision_id asc
                """,
                (plan_id,),
            ).fetchall()
        return [self._revision_from_row(row) for row in rows]

    def list_latest_revisions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select revisions.*
                from plan_revisions revisions
                join (
                    select plan_id, max(version) as version
                    from plan_revisions
                    group by plan_id
                ) latest
                    on revisions.plan_id = latest.plan_id
                    and revisions.version = latest.version
                order by revisions.created_at desc, revisions.revision_id desc
                """
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
            existing_action = conn.execute(
                "select action_id, idempotency_key from action_ledger where action_id = ?",
                (action_id,),
            ).fetchone()
            if existing_action and existing_action["idempotency_key"] != idempotency_key:
                raise ValueError(
                    "action_id "
                    f"{action_id} already exists with idempotency_key {existing_action['idempotency_key']}"
                )

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
                on conflict(idempotency_key) do update set
                    revision_id = excluded.revision_id,
                    tool = excluded.tool,
                    status = excluded.status,
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

    def insert_action_if_absent(
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
            conn.execute("begin immediate")
            existing_action = conn.execute(
                """
                select * from action_ledger
                where action_id = ?
                """,
                (action_id,),
            ).fetchone()
            if existing_action is not None:
                if existing_action["idempotency_key"] != idempotency_key:
                    raise ValueError(f"action_id_conflict:{action_id}")
                receipt_matches = existing_action["receipt_id"] == receipt_id
                existing_receipt_was_recorded = False
                if existing_action["receipt_id"] is not None:
                    existing_receipt_was_recorded = (
                        conn.execute(
                            """
                            select 1 from receipts
                            where receipt_id = ? and action_id = ? and revision_id = ?
                            """,
                            (existing_action["receipt_id"], action_id, existing_action["revision_id"]),
                        ).fetchone()
                        is not None
                    )
                default_reseed_after_success = (
                    receipt_id is None
                    and status == "pending"
                    and existing_action["status"] == "succeeded"
                    and existing_receipt_was_recorded
                )
                if (
                    existing_action["revision_id"] != revision_id
                    or existing_action["tool"] != tool
                    or existing_action["payload_json"] != _json_dumps(payload)
                    or (not receipt_matches and not default_reseed_after_success)
                    or (status != "pending" and existing_action["status"] != status)
                ):
                    raise ValueError(f"action_seed_conflict:{action_id}")
                return

            existing_idempotency_key = conn.execute(
                """
                select action_id, idempotency_key from action_ledger
                where idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if existing_idempotency_key is not None:
                raise ValueError(f"idempotency_key_conflict:{idempotency_key}")

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
                """
                select * from action_ledger
                where revision_id = ?
                order by created_at asc, action_id asc
                """,
                (revision_id,),
            ).fetchall()
        return [self._action_from_row(row) for row in rows]

    def get_action(self, action_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "select * from action_ledger where action_id = ?",
                (action_id,),
            ).fetchone()
        return self._action_from_row(row) if row else None

    def claim_action_for_execution(self, action_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            result = conn.execute(
                """
                update action_ledger
                set status = 'executing', updated_at = ?
                where action_id = ? and status = 'pending'
                """,
                (_now(), action_id),
            )
            if result.rowcount == 0:
                return None
            row = conn.execute(
                "select * from action_ledger where action_id = ?",
                (action_id,),
            ).fetchone()
        return self._action_from_row(row) if row else None

    def claim_actions_for_execution(self, revision_id: str, selected_action_ids: list[str]) -> list[dict[str, Any]]:
        ordered_action_ids = list(dict.fromkeys(selected_action_ids))
        if not ordered_action_ids:
            return []

        placeholders = ",".join("?" for _ in ordered_action_ids)
        with self._connect() as conn:
            conn.execute("begin immediate")
            rows = conn.execute(
                f"""
                select * from action_ledger
                where revision_id = ? and action_id in ({placeholders})
                """,
                (revision_id, *ordered_action_ids),
            ).fetchall()
            actions_by_id = {row["action_id"]: row for row in rows}

            for action_id in ordered_action_ids:
                action = actions_by_id.get(action_id)
                if action is None:
                    raise ValueError(f"unknown_action_id:{action_id}")
                if action["status"] != "pending":
                    raise ValueError(f"action_not_pending:{action_id}")

            timestamp = _now()
            conn.execute(
                f"""
                update action_ledger
                set status = 'executing', updated_at = ?
                where revision_id = ? and action_id in ({placeholders})
                """,
                (timestamp, revision_id, *ordered_action_ids),
            )
            updated_rows = conn.execute(
                f"""
                select * from action_ledger
                where revision_id = ? and action_id in ({placeholders})
                """,
                (revision_id, *ordered_action_ids),
            ).fetchall()

        updated_by_id = {row["action_id"]: self._action_from_row(row) for row in updated_rows}
        return [updated_by_id[action_id] for action_id in ordered_action_ids]

    def record_action_succeeded(
        self,
        attempt_id: str,
        action_id: str,
        receipt_id: str,
        detail: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute("begin immediate")
            action = conn.execute(
                "select * from action_ledger where action_id = ?",
                (action_id,),
            ).fetchone()
            if action is None:
                raise ValueError(f"unknown_action_id:{action_id}")

            if action["status"] == "succeeded":
                if action["receipt_id"] == receipt_id:
                    return self._action_from_row(action)
                raise ValueError(f"receipt_conflict:{action_id}")

            receipt = conn.execute(
                """
                select action_id, revision_id from receipts
                where receipt_id = ?
                """,
                (receipt_id,),
            ).fetchone()
            if receipt and (receipt["action_id"] != action_id or receipt["revision_id"] != action["revision_id"]):
                raise ValueError(f"receipt_conflict:{action_id}")

            if action["receipt_id"] is not None and action["receipt_id"] != receipt_id:
                raise ValueError(f"receipt_conflict:{action_id}")

            timestamp = _now()
            if receipt is None:
                conn.execute(
                    """
                    insert into action_attempts(
                        attempt_id,
                        action_id,
                        status,
                        request_json,
                        response_json,
                        error,
                        created_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        attempt_id,
                        action_id,
                        "succeeded",
                        _json_dumps({"action_id": action_id, "payload": _json_loads(action["payload_json"])}),
                        _json_dumps({"receipt_id": receipt_id, "detail": detail, "payload": payload}),
                        None,
                        timestamp,
                    ),
                )
                conn.execute(
                    """
                    insert into receipts(receipt_id, action_id, revision_id, tool, status, detail, payload_json, created_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        receipt_id,
                        action_id,
                        action["revision_id"],
                        action["tool"],
                        "succeeded",
                        detail,
                        _json_dumps(payload),
                        timestamp,
                    ),
                )

            result = conn.execute(
                """
                update action_ledger
                set status = 'succeeded', receipt_id = ?, updated_at = ?
                where action_id = ? and (receipt_id is null or receipt_id = ?)
                """,
                (receipt_id, _now(), action_id, receipt_id),
            )
            if result.rowcount == 0:
                raise ValueError(f"receipt_conflict:{action_id}")
            updated = conn.execute(
                "select * from action_ledger where action_id = ?",
                (action_id,),
            ).fetchone()
            if updated is None:
                raise ValueError(f"unknown_action_id:{action_id}")
        return self._action_from_row(updated)

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
                """
                select * from action_attempts
                where action_id = ?
                order by created_at asc, attempt_id asc
                """,
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
                """
                select * from receipts
                where revision_id = ?
                order by created_at asc, receipt_id asc
                """,
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
