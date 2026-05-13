from __future__ import annotations

from typing import Any, Literal, TypedDict
from uuid import uuid4

PHASE_DRAFT = "draft"
PHASE_NEEDS_CLARIFICATION = "needs_clarification"
PHASE_PLANNING = "planning"
PHASE_VALIDATION_FAILED = "validation_failed"
PHASE_PENDING_APPROVAL = "pending_approval"
PHASE_APPROVED = "approved"
PHASE_EXECUTING = "executing"
PHASE_PARTIALLY_COMPLETED = "partially_completed"
PHASE_COMPLETED = "completed"
PHASE_CANCELLED = "cancelled"
PHASE_FAILED = "failed"

WorkflowPhase = Literal[
    "draft",
    "needs_clarification",
    "planning",
    "validation_failed",
    "pending_approval",
    "approved",
    "executing",
    "partially_completed",
    "completed",
    "cancelled",
    "failed",
]


class PlanGraphState(TypedDict, total=False):
    thread_id: str
    run_id: str
    plan_id: str
    revision_id: str
    user_id: str
    phase: WorkflowPhase
    goal: str
    constraints: dict[str, Any]
    profile_snapshot: dict[str, Any]
    context: dict[str, Any]
    candidates: dict[str, list[dict[str, Any]]]
    candidate_sets: dict[str, list[dict[str, Any]]]
    rejected_candidates: dict[str, list[dict[str, Any]]]
    variants: list[dict[str, Any]]
    selected_variant_id: str | None
    validation: dict[str, Any]
    pending_decision: dict[str, Any] | None
    actions: list[dict[str, Any]]
    action_ledger: dict[str, Any]
    receipts: list[dict[str, Any]]
    recovery_history: list[dict[str, Any]]
    trace: list[dict[str, Any]]


class WorkflowTransitionError(ValueError):
    pass


ALLOWED_TRANSITIONS: set[tuple[str, str]] = {
    (PHASE_DRAFT, PHASE_NEEDS_CLARIFICATION),
    (PHASE_DRAFT, PHASE_PLANNING),
    (PHASE_NEEDS_CLARIFICATION, PHASE_PLANNING),
    (PHASE_PLANNING, PHASE_VALIDATION_FAILED),
    (PHASE_PLANNING, PHASE_PENDING_APPROVAL),
    (PHASE_VALIDATION_FAILED, PHASE_PLANNING),
    (PHASE_VALIDATION_FAILED, PHASE_NEEDS_CLARIFICATION),
    (PHASE_PENDING_APPROVAL, PHASE_APPROVED),
    (PHASE_PENDING_APPROVAL, PHASE_PLANNING),
    (PHASE_PENDING_APPROVAL, PHASE_CANCELLED),
    (PHASE_APPROVED, PHASE_EXECUTING),
    (PHASE_EXECUTING, PHASE_COMPLETED),
    (PHASE_EXECUTING, PHASE_PARTIALLY_COMPLETED),
    (PHASE_EXECUTING, PHASE_FAILED),
    (PHASE_PARTIALLY_COMPLETED, PHASE_EXECUTING),
    (PHASE_PARTIALLY_COMPLETED, PHASE_PLANNING),
    (PHASE_FAILED, PHASE_PLANNING),
}


def assert_transition_allowed(current: str, next_phase: str) -> None:
    if current == next_phase:
        return
    if (current, next_phase) not in ALLOWED_TRANSITIONS:
        raise WorkflowTransitionError(f"invalid_transition:{current}->{next_phase}")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def new_plan_id() -> str:
    return new_id("plan")


def new_revision_id() -> str:
    return new_id("rev")


def new_run_id() -> str:
    return new_id("run")


def new_thread_id() -> str:
    return new_id("thread")


def new_action_id() -> str:
    return new_id("act")
