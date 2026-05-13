from __future__ import annotations

from typing import Any

from backend.graph.state import new_id
from backend.storage.workflow_repository import WorkflowRepository


class DurableActionLedger:
    def __init__(self, repository: WorkflowRepository) -> None:
        self.repository = repository

    def seed_actions(self, revision_id: str, actions: list[dict[str, Any]]) -> None:
        for action in actions:
            action_id = action["action_id"]
            self.repository.upsert_action(
                action_id,
                revision_id,
                action["tool"],
                action.get("status", "pending"),
                action.get("idempotency_key", f"{revision_id}:{action_id}"),
                action.get("payload", {}),
                action.get("receipt_id"),
            )

    def list_actions(self, revision_id: str) -> list[dict[str, Any]]:
        return self.repository.list_actions(revision_id)

    def list_receipts(self, revision_id: str) -> list[dict[str, Any]]:
        return self.repository.list_receipts(revision_id)

    def mark_executing(self, revision_id: str, selected_action_ids: list[str]) -> list[dict[str, Any]]:
        actions = {action["action_id"]: action for action in self.repository.list_actions(revision_id)}
        for action_id in selected_action_ids:
            if action_id not in actions:
                raise ValueError(f"unknown_action_id:{action_id}")

        updated: list[dict[str, Any]] = []
        for action_id in selected_action_ids:
            action = actions[action_id]
            if action["status"] != "pending":
                continue
            self.repository.update_action_status(action_id, "executing", action.get("receipt_id"))
            changed = self.repository.get_action(action_id)
            if changed is not None:
                updated.append(changed)
        return updated

    def mark_succeeded(self, action_id: str, receipt_id: str, detail: str, payload: dict[str, Any]) -> None:
        action = self.repository.get_action(action_id)
        if action is None:
            raise ValueError(f"unknown_action_id:{action_id}")
        if action["status"] == "succeeded" and action.get("receipt_id") == receipt_id:
            return

        self.repository.append_attempt(
            new_id("attempt"),
            action_id,
            "succeeded",
            {"action_id": action_id, "payload": action["payload"]},
            {"receipt_id": receipt_id, "detail": detail, "payload": payload},
            None,
        )
        self.repository.append_receipt(
            receipt_id,
            action_id,
            action["revision_id"],
            action["tool"],
            "succeeded",
            detail,
            payload,
        )
        self.repository.update_action_status(action_id, "succeeded", receipt_id)
