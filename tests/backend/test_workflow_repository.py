import sqlite3
from pathlib import Path

import pytest

from backend.storage.workflow_repository import WorkflowRepository


def test_repository_persists_thread_revision_ledger_and_receipt(tmp_path: Path):
    db_path = tmp_path / "workflow.sqlite"
    repository = WorkflowRepository(db_path)

    constraints = {"budget": 500, "tags": ["夕食", "activity"]}
    plan = {"title": "Weekend plan", "steps": [{"kind": "restaurant", "name": "Sushi"}]}
    validation = {"ok": True, "warnings": []}
    payload = {"booking": {"party_size": 4}, "notes": "窓側"}
    request = {"method": "POST", "body": {"slot": "18:00"}}
    response = {"status_code": 200, "body": {"message_id": "MSG-1"}}
    receipt_payload = {"provider": "line", "raw": {"message_id": "MSG-1"}}

    repository.create_thread("thread_1", "run_1", "plan_1", "user_1", "planning")
    repository.save_revision(
        "rev_1",
        "plan_1",
        1,
        "draft",
        "Plan a weekend afternoon",
        constraints,
        plan,
        validation,
    )
    repository.upsert_action("act_1", "rev_1", "messaging", "pending", "idem_1", payload, None)
    repository.append_attempt("attempt_1", "act_1", "succeeded", request, response, None)
    repository.append_receipt("MSG-1", "act_1", "rev_1", "messaging", "sent", "Sent", receipt_payload)

    recreated = WorkflowRepository(db_path)

    assert recreated.get_thread("thread_1")["plan_id"] == "plan_1"

    latest_revision = recreated.get_latest_revision("plan_1")
    assert latest_revision["revision_id"] == "rev_1"
    assert latest_revision["constraints"] == constraints
    assert latest_revision["plan"] == plan
    assert latest_revision["validation"] == validation

    actions = recreated.list_actions("rev_1")
    assert actions[0]["action_id"] == "act_1"
    assert actions[0]["payload"] == payload
    assert recreated.get_action_by_idempotency_key("idem_1")["payload"] == payload

    attempts = recreated.list_attempts("act_1")
    assert attempts[0]["attempt_id"] == "attempt_1"
    assert attempts[0]["request"] == request
    assert attempts[0]["response"] == response

    receipts = recreated.list_receipts("rev_1")
    assert receipts[0]["receipt_id"] == "MSG-1"
    assert receipts[0]["detail"] == "Sent"
    assert receipts[0]["payload"] == receipt_payload

    with sqlite3.connect(db_path) as conn:
        receipt_columns = [row[1] for row in conn.execute("pragma table_info(receipts)").fetchall()]
    assert receipt_columns == [
        "receipt_id",
        "action_id",
        "revision_id",
        "tool",
        "status",
        "detail",
        "payload_json",
        "created_at",
    ]


def test_repository_uses_json_not_pickle(tmp_path: Path):
    db_path = tmp_path / "nested" / "workflow.sqlite"

    repository = WorkflowRepository(db_path)
    repository.create_thread("thread_1", "run_1", "plan_1", "user_1", "planning")

    raw_bytes = db_path.read_bytes()
    assert b"pickle" not in raw_bytes
    assert b"thread_1" in raw_bytes

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("select thread_id from plan_threads where thread_id = ?", ("thread_1",)).fetchone()
    assert row == ("thread_1",)


def test_repository_releases_sqlite_file_handles_between_operations(tmp_path: Path):
    db_path = tmp_path / "workflow.sqlite"
    repository = WorkflowRepository(db_path)

    repository.create_thread("thread_1", "run_1", "plan_1", "user_1", "planning")

    db_path.unlink()
    assert not db_path.exists()


def test_repository_resets_legacy_receipts_schema(tmp_path: Path):
    db_path = tmp_path / "workflow.sqlite"
    new_payload = {"provider": "line", "raw": {"message_id": "MSG-new"}}

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            create table plan_revisions (
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

            create table action_ledger (
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

            create table receipts (
                receipt_id text primary key,
                action_id text not null,
                revision_id text not null,
                tool text not null,
                status text not null,
                message text not null,
                metadata_json text not null,
                created_at text not null
            );
            """
        )
        conn.execute(
            """
            insert into plan_revisions(
                revision_id, plan_id, version, phase, goal, constraints_json, plan_json, validation_json, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("rev_legacy", "plan_1", 1, "draft", "Goal", "{}", "{}", "{}", "2026-05-13T00:00:00+00:00"),
        )
        conn.execute(
            """
            insert into action_ledger(
                action_id, revision_id, tool, status, idempotency_key, payload_json, receipt_id, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "act_legacy",
                "rev_legacy",
                "messaging",
                "pending",
                "idem_legacy",
                "{}",
                None,
                "2026-05-13T00:00:00+00:00",
                "2026-05-13T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            insert into receipts(receipt_id, action_id, revision_id, tool, status, message, metadata_json, created_at)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "MSG-legacy",
                "act_legacy",
                "rev_legacy",
                "messaging",
                "sent",
                "Legacy sent",
                '{"provider": "line", "raw": {"message_id": "MSG-legacy"}}',
                "2026-05-13T00:00:00+00:00",
            ),
        )

    repository = WorkflowRepository(db_path)
    assert repository.list_receipts("rev_legacy") == []

    with sqlite3.connect(db_path) as conn:
        receipt_columns = [row[1] for row in conn.execute("pragma table_info(receipts)").fetchall()]
        action_count = conn.execute("select count(*) from action_ledger").fetchone()[0]
    assert "message" not in receipt_columns
    assert "metadata_json" not in receipt_columns
    assert "detail" in receipt_columns
    assert "payload_json" in receipt_columns
    assert action_count == 0

    repository.save_revision("rev_new", "plan_1", 1, "draft", "Goal", {}, {}, {})
    repository.upsert_action("act_new", "rev_new", "messaging", "pending", "idem_new", {}, None)
    repository.append_receipt("MSG-new", "act_new", "rev_new", "messaging", "sent", "New sent", new_payload)
    receipts = repository.list_receipts("rev_new")
    assert receipts[0]["receipt_id"] == "MSG-new"
    assert receipts[0]["detail"] == "New sent"
    assert receipts[0]["payload"] == new_payload


def test_upsert_action_reuses_existing_action_for_same_idempotency_key(tmp_path: Path):
    repository = WorkflowRepository(tmp_path / "workflow.sqlite")
    repository.save_revision("rev_1", "plan_1", 1, "draft", "Goal", {}, {}, {})

    repository.upsert_action("act_original", "rev_1", "messaging", "pending", "idem_1", {"try": 1}, None)
    repository.upsert_action("act_retry", "rev_1", "messaging", "succeeded", "idem_1", {"try": 2}, "MSG-1")

    actions = repository.list_actions("rev_1")
    assert len(actions) == 1
    assert actions[0]["action_id"] == "act_original"
    assert actions[0]["idempotency_key"] == "idem_1"
    assert actions[0]["status"] == "succeeded"
    assert actions[0]["payload"] == {"try": 2}
    assert actions[0]["receipt_id"] == "MSG-1"


def test_upsert_action_rejects_action_id_with_different_idempotency_key(tmp_path: Path):
    repository = WorkflowRepository(tmp_path / "workflow.sqlite")
    repository.save_revision("rev_1", "plan_1", 1, "draft", "Goal", {}, {}, {})

    repository.upsert_action("act_1", "rev_1", "messaging", "pending", "idem_1", {}, None)

    with pytest.raises(ValueError, match="action_id act_1 already exists with idempotency_key idem_1"):
        repository.upsert_action("act_1", "rev_1", "messaging", "pending", "idem_2", {}, None)


def test_repository_uses_stable_secondary_ordering_and_unique_plan_versions(tmp_path: Path):
    db_path = tmp_path / "workflow.sqlite"
    repository = WorkflowRepository(db_path)
    repository.save_revision("rev_1", "plan_1", 1, "draft", "Goal", {}, {}, {})

    with pytest.raises(sqlite3.IntegrityError):
        repository.save_revision("rev_duplicate", "plan_1", 1, "draft", "Goal", {}, {}, {})

    repository.upsert_action("act_b", "rev_1", "messaging", "pending", "idem_b", {}, None)
    repository.upsert_action("act_a", "rev_1", "messaging", "pending", "idem_a", {}, None)
    repository.append_attempt("attempt_b", "act_a", "failed", {}, {}, "timeout")
    repository.append_attempt("attempt_a", "act_a", "succeeded", {}, {}, None)
    repository.append_receipt("MSG-B", "act_a", "rev_1", "messaging", "sent", "B", {})
    repository.append_receipt("MSG-A", "act_a", "rev_1", "messaging", "sent", "A", {})

    with sqlite3.connect(db_path) as conn:
        conn.execute("update action_ledger set created_at = ?", ("2026-05-13T00:00:00+00:00",))
        conn.execute("update action_attempts set created_at = ?", ("2026-05-13T00:00:00+00:00",))
        conn.execute("update receipts set created_at = ?", ("2026-05-13T00:00:00+00:00",))

    assert [action["action_id"] for action in repository.list_actions("rev_1")] == ["act_a", "act_b"]
    assert [attempt["attempt_id"] for attempt in repository.list_attempts("act_a")] == ["attempt_a", "attempt_b"]
    assert [receipt["receipt_id"] for receipt in repository.list_receipts("rev_1")] == ["MSG-A", "MSG-B"]
