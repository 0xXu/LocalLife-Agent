from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.schemas import PlanAction


@dataclass
class ActionEntry:
    action_id: str
    plan_id: str
    action: PlanAction
    status: str = "pending"
    idempotency_keys: set[str] = field(default_factory=set)
    receipt_id: str = ""
    error: str = ""


@dataclass
class ActionLedger:
    plan_id: str
    entries: list[ActionEntry]

    def mark_executing(self, selected_action_ids: list[str], idempotency_key: str) -> list[ActionEntry]:
        selected = set(selected_action_ids)
        changed: list[ActionEntry] = []
        for entry in self.entries:
            if entry.action_id not in selected:
                continue
            if idempotency_key in entry.idempotency_keys:
                continue
            if entry.status in {"succeeded", "skipped"}:
                continue
            entry.idempotency_keys.add(idempotency_key)
            entry.status = "executing"
            changed.append(entry)
        return changed

    def mark_succeeded(self, action_id: str, receipt_id: str) -> None:
        entry = self.get(action_id)
        entry.status = "succeeded"
        entry.receipt_id = receipt_id

    def get(self, action_id: str) -> ActionEntry:
        for entry in self.entries:
            if entry.action_id == action_id:
                return entry
        raise KeyError(action_id)


def ledger_from_actions(plan_id: str, actions: list[PlanAction]) -> ActionLedger:
    return ActionLedger(plan_id, [ActionEntry(stable_action_id(action), plan_id, action) for action in actions])


def stable_action_id(action: PlanAction) -> str:
    target = action.target.replace(" ", "_")
    return f"{action.tool or action.type}_{target or 'default'}"
