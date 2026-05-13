from pathlib import Path

import pytest

from backend.actions.durable_ledger import DurableActionLedger
from backend.storage.workflow_repository import WorkflowRepository


def _repository(tmp_path: Path) -> WorkflowRepository:
    repository = WorkflowRepository(tmp_path / "workflow.sqlite")
    repository.save_revision("rev_1", "plan_1", 1, "draft", "Goal", {}, {}, {})
    return repository


def _seed_two_actions(ledger: DurableActionLedger) -> None:
    ledger.seed_actions(
        "rev_1",
        [
            {"action_id": "act_msg", "tool": "messaging", "payload": {"recipient": "traveler"}},
            {"action_id": "act_cal", "tool": "calendar", "payload": {"title": "Dinner"}},
        ],
    )


def test_ledger_executes_selected_actions_once_and_preserves_receipts(tmp_path: Path):
    repository = _repository(tmp_path)
    ledger = DurableActionLedger(repository)
    _seed_two_actions(ledger)

    executing = ledger.mark_executing("rev_1", ["act_msg"])
    ledger.mark_succeeded("act_msg", "MSG-1", "Sent", {"provider": "line"})
    repeated = ledger.mark_executing("rev_1", ["act_msg"])
    next_executing = ledger.mark_executing("rev_1", ["act_cal"])

    assert [action["action_id"] for action in executing] == ["act_msg"]
    assert repeated == []
    assert [action["action_id"] for action in next_executing] == ["act_cal"]
    assert {action["action_id"]: action["status"] for action in ledger.list_actions("rev_1")} == {
        "act_msg": "succeeded",
        "act_cal": "executing",
    }
    assert [receipt["receipt_id"] for receipt in ledger.list_receipts("rev_1")] == ["MSG-1"]


def test_ledger_survives_repository_reopen(tmp_path: Path):
    db_path = tmp_path / "workflow.sqlite"
    repository = WorkflowRepository(db_path)
    repository.save_revision("rev_1", "plan_1", 1, "draft", "Goal", {}, {}, {})
    ledger = DurableActionLedger(repository)
    ledger.seed_actions("rev_1", [{"action_id": "act_msg", "tool": "messaging", "payload": {"body": "hello"}}])
    ledger.mark_executing("rev_1", ["act_msg"])
    ledger.mark_succeeded("act_msg", "MSG-1", "Sent", {"provider": "line"})

    reopened = DurableActionLedger(WorkflowRepository(db_path))

    assert reopened.mark_executing("rev_1", ["act_msg"]) == []
    assert [receipt["receipt_id"] for receipt in reopened.list_receipts("rev_1")] == ["MSG-1"]


def test_unknown_action_id_fails_validation(tmp_path: Path):
    ledger = DurableActionLedger(_repository(tmp_path))
    ledger.seed_actions("rev_1", [{"action_id": "act_msg", "tool": "messaging", "payload": {}}])

    with pytest.raises(ValueError, match="unknown_action_id:act_missing"):
        ledger.mark_executing("rev_1", ["act_missing"])
    with pytest.raises(ValueError, match="unknown_action_id:act_missing"):
        ledger.mark_succeeded("act_missing", "MSG-1", "Sent", {})


def test_mark_succeeded_is_idempotent_for_same_receipt_id(tmp_path: Path):
    ledger = DurableActionLedger(_repository(tmp_path))
    ledger.seed_actions("rev_1", [{"action_id": "act_msg", "tool": "messaging", "payload": {"body": "hello"}}])
    ledger.mark_executing("rev_1", ["act_msg"])

    ledger.mark_succeeded("act_msg", "MSG-1", "Sent", {"provider": "line"})
    ledger.mark_succeeded("act_msg", "MSG-1", "Sent", {"provider": "line"})

    assert [receipt["receipt_id"] for receipt in ledger.list_receipts("rev_1")] == ["MSG-1"]


def test_duplicate_selected_ids_claim_once(tmp_path: Path):
    ledger = DurableActionLedger(_repository(tmp_path))
    ledger.seed_actions("rev_1", [{"action_id": "act_msg", "tool": "messaging", "payload": {"body": "hello"}}])

    claimed = ledger.mark_executing("rev_1", ["act_msg", "act_msg"])

    assert [action["action_id"] for action in claimed] == ["act_msg"]
    assert ledger.mark_executing("rev_1", ["act_msg"]) == []


def test_seed_actions_does_not_downgrade_existing_succeeded_action(tmp_path: Path):
    ledger = DurableActionLedger(_repository(tmp_path))
    action = {"action_id": "act_msg", "tool": "messaging", "payload": {"body": "hello"}}
    ledger.seed_actions("rev_1", [action])
    ledger.mark_executing("rev_1", ["act_msg"])
    ledger.mark_succeeded("act_msg", "MSG-1", "Sent", {"provider": "line"})

    ledger.seed_actions("rev_1", [action])

    actions = ledger.list_actions("rev_1")
    assert actions[0]["status"] == "succeeded"
    assert actions[0]["receipt_id"] == "MSG-1"


def test_seed_actions_rejects_action_id_conflict(tmp_path: Path):
    ledger = DurableActionLedger(_repository(tmp_path))
    ledger.seed_actions(
        "rev_1",
        [{"action_id": "act_msg", "tool": "messaging", "idempotency_key": "idem_1", "payload": {}}],
    )

    with pytest.raises(ValueError, match="action_id_conflict:act_msg"):
        ledger.seed_actions(
            "rev_1",
            [{"action_id": "act_msg", "tool": "messaging", "idempotency_key": "idem_2", "payload": {}}],
        )


def test_seed_actions_rejects_idempotency_key_conflict(tmp_path: Path):
    ledger = DurableActionLedger(_repository(tmp_path))
    ledger.seed_actions(
        "rev_1",
        [{"action_id": "act_msg", "tool": "messaging", "idempotency_key": "idem_1", "payload": {}}],
    )

    with pytest.raises(ValueError, match="idempotency_key_conflict:idem_1"):
        ledger.seed_actions(
            "rev_1",
            [{"action_id": "act_cal", "tool": "calendar", "idempotency_key": "idem_1", "payload": {}}],
        )


def test_seed_actions_rejects_changed_payload_for_same_action_and_key(tmp_path: Path):
    ledger = DurableActionLedger(_repository(tmp_path))
    ledger.seed_actions(
        "rev_1",
        [
            {
                "action_id": "act_msg",
                "tool": "messaging",
                "idempotency_key": "idem_1",
                "payload": {"body": "hello"},
            }
        ],
    )

    with pytest.raises(ValueError, match="action_seed_conflict:act_msg"):
        ledger.seed_actions(
            "rev_1",
            [
                {
                    "action_id": "act_msg",
                    "tool": "messaging",
                    "idempotency_key": "idem_1",
                    "payload": {"body": "changed"},
                }
            ],
        )


def test_seed_actions_rejects_changed_tool_for_same_action_and_key(tmp_path: Path):
    ledger = DurableActionLedger(_repository(tmp_path))
    ledger.seed_actions(
        "rev_1",
        [{"action_id": "act_msg", "tool": "messaging", "idempotency_key": "idem_1", "payload": {}}],
    )

    with pytest.raises(ValueError, match="action_seed_conflict:act_msg"):
        ledger.seed_actions(
            "rev_1",
            [{"action_id": "act_msg", "tool": "calendar", "idempotency_key": "idem_1", "payload": {}}],
        )


def test_seed_actions_rejects_missing_receipt_for_same_action_and_key(tmp_path: Path):
    ledger = DurableActionLedger(_repository(tmp_path))
    ledger.seed_actions(
        "rev_1",
        [
            {
                "action_id": "act_msg",
                "tool": "messaging",
                "idempotency_key": "idem_1",
                "payload": {},
                "receipt_id": "R1",
            }
        ],
    )

    with pytest.raises(ValueError, match="action_seed_conflict:act_msg"):
        ledger.seed_actions(
            "rev_1",
            [{"action_id": "act_msg", "tool": "messaging", "idempotency_key": "idem_1", "payload": {}}],
        )


def test_seed_actions_rejects_changed_revision_for_same_action_and_key(tmp_path: Path):
    repository = _repository(tmp_path)
    repository.save_revision("rev_2", "plan_1", 2, "draft", "Goal", {}, {}, {})
    ledger = DurableActionLedger(repository)
    ledger.seed_actions(
        "rev_1",
        [{"action_id": "act_msg", "tool": "messaging", "idempotency_key": "idem_1", "payload": {}}],
    )

    with pytest.raises(ValueError, match="action_seed_conflict:act_msg"):
        ledger.seed_actions(
            "rev_2",
            [{"action_id": "act_msg", "tool": "messaging", "idempotency_key": "idem_1", "payload": {}}],
        )


def test_mark_succeeded_finishes_action_when_receipt_already_exists(tmp_path: Path):
    repository = _repository(tmp_path)
    ledger = DurableActionLedger(repository)
    ledger.seed_actions("rev_1", [{"action_id": "act_msg", "tool": "messaging", "payload": {"body": "hello"}}])
    ledger.mark_executing("rev_1", ["act_msg"])
    repository.append_receipt("MSG-1", "act_msg", "rev_1", "messaging", "succeeded", "Sent", {"provider": "line"})

    ledger.mark_succeeded("act_msg", "MSG-1", "Sent", {"provider": "line"})

    actions = ledger.list_actions("rev_1")
    assert actions[0]["status"] == "succeeded"
    assert actions[0]["receipt_id"] == "MSG-1"
    assert [receipt["receipt_id"] for receipt in ledger.list_receipts("rev_1")] == ["MSG-1"]


def test_mark_succeeded_rejects_conflicting_receipt(tmp_path: Path):
    ledger = DurableActionLedger(_repository(tmp_path))
    ledger.seed_actions("rev_1", [{"action_id": "act_msg", "tool": "messaging", "payload": {"body": "hello"}}])
    ledger.mark_executing("rev_1", ["act_msg"])
    ledger.mark_succeeded("act_msg", "MSG-1", "Sent", {"provider": "line"})

    with pytest.raises(ValueError, match="receipt_conflict:act_msg"):
        ledger.mark_succeeded("act_msg", "MSG-2", "Sent again", {"provider": "line"})

    actions = ledger.list_actions("rev_1")
    assert actions[0]["status"] == "succeeded"
    assert actions[0]["receipt_id"] == "MSG-1"
    assert [receipt["receipt_id"] for receipt in ledger.list_receipts("rev_1")] == ["MSG-1"]


def test_mark_succeeded_rejects_receipt_id_owned_by_another_action(tmp_path: Path):
    repository = _repository(tmp_path)
    ledger = DurableActionLedger(repository)
    _seed_two_actions(ledger)
    ledger.mark_executing("rev_1", ["act_msg"])
    repository.append_receipt("MSG-1", "act_cal", "rev_1", "calendar", "succeeded", "Booked", {})

    with pytest.raises(ValueError, match="receipt_conflict:act_msg"):
        ledger.mark_succeeded("act_msg", "MSG-1", "Sent", {"provider": "line"})

    actions = {action["action_id"]: action for action in ledger.list_actions("rev_1")}
    assert actions["act_msg"]["status"] == "executing"
    assert actions["act_msg"]["receipt_id"] is None
