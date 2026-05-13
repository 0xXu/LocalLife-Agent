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
            self.repository.insert_action_if_absent(
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
        ordered_action_ids = list(dict.fromkeys(selected_action_ids))
        for action_id in ordered_action_ids:
            if action_id not in actions:
                raise ValueError(f"unknown_action_id:{action_id}")

        updated: list[dict[str, Any]] = []
        for action_id in ordered_action_ids:
            claimed = self.repository.claim_action_for_execution(action_id)
            if claimed is not None:
                updated.append(claimed)
        return updated

    def mark_succeeded(self, action_id: str, receipt_id: str, detail: str, payload: dict[str, Any]) -> None:
        self.repository.record_action_succeeded(
            new_id("attempt"),
            action_id,
            receipt_id,
            detail,
            payload,
        )
