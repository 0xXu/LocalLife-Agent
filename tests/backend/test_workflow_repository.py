import sqlite3
from pathlib import Path

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
