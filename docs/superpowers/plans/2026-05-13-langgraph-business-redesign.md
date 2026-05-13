# LangGraph Business Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current linear backend planning flow with a backend-authoritative graph-run workflow that has durable state, explicit interrupts, immutable revisions, persistent side-effect ledgers, and enforceable business transitions.

**Architecture:** Add a new backend workflow layer beside the existing `PlanningPipeline`, then route new graph-run APIs through it. The current planner can still generate candidate plan content, but workflow state, validation gates, approval, execution, revisions, receipts, and stream identity move into new focused modules. Old direct confirm and execute endpoints are hard-disabled after the new run/resume contract is available.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, SQLite, pytest, existing local seed catalog and tool registry.

---

## File Structure

Create these focused backend modules:

- `backend/graph/state.py`: typed workflow state, phase enum constants, ID helpers, and allowed transition policy.
- `backend/graph/events.py`: serializable graph stream event helpers with stable event ids.
- `backend/storage/workflow_repository.py`: SQLite JSON persistence for runs, revisions, action ledger rows, attempts, receipts, and trace events.
- `backend/actions/durable_ledger.py`: durable ledger operations over `WorkflowRepository`.
- `backend/actions/policy.py`: deterministic conversion from a plan revision plus user intent into executable actions.
- `backend/validation/business.py`: blocking and warning validation rules for approval eligibility.
- `backend/services/workflow_service.py`: graph-run service facade used by API endpoints.
- `backend/orchestrator/business_graph.py`: StateGraph wrapper that owns run phases, interrupts, approval, execution, and recovery routing.

Modify these existing files:

- `backend/api/app.py`: add new graph-run endpoints and hard-disable old direct state mutation endpoints.
- `backend/services/__init__.py`: export `WorkflowService`.
- `backend/actions/__init__.py`: export durable action helpers.
- `backend/validation/__init__.py`: export business validation helpers.

Add these tests:

- `tests/backend/test_graph_state.py`
- `tests/backend/test_workflow_repository.py`
- `tests/backend/test_durable_ledger.py`
- `tests/backend/test_action_policy.py`
- `tests/backend/test_business_validation.py`
- `tests/backend/test_workflow_service.py`
- `tests/backend/test_graph_run_api.py`

## Task 1: Workflow State and Transition Policy

**Files:**
- Create: `backend/graph/state.py`
- Create: `backend/graph/__init__.py`
- Test: `tests/backend/test_graph_state.py`

- [ ] **Step 1: Write failing state transition tests**

Create `tests/backend/test_graph_state.py`:

```python
import pytest

from backend.graph.state import (
    PHASE_APPROVED,
    PHASE_CANCELLED,
    PHASE_COMPLETED,
    PHASE_DRAFT,
    PHASE_EXECUTING,
    PHASE_NEEDS_CLARIFICATION,
    PHASE_PENDING_APPROVAL,
    PHASE_PLANNING,
    PHASE_VALIDATION_FAILED,
    WorkflowTransitionError,
    assert_transition_allowed,
    new_action_id,
    new_plan_id,
    new_revision_id,
    new_run_id,
    new_thread_id,
)


def test_allowed_workflow_transitions_cover_happy_path():
    assert_transition_allowed(PHASE_DRAFT, PHASE_PLANNING)
    assert_transition_allowed(PHASE_PLANNING, PHASE_PENDING_APPROVAL)
    assert_transition_allowed(PHASE_PENDING_APPROVAL, PHASE_APPROVED)
    assert_transition_allowed(PHASE_APPROVED, PHASE_EXECUTING)
    assert_transition_allowed(PHASE_EXECUTING, PHASE_COMPLETED)


def test_validation_failed_cannot_be_approved_or_executed():
    with pytest.raises(WorkflowTransitionError, match="validation_failed->approved"):
        assert_transition_allowed(PHASE_VALIDATION_FAILED, PHASE_APPROVED)
    with pytest.raises(WorkflowTransitionError, match="validation_failed->executing"):
        assert_transition_allowed(PHASE_VALIDATION_FAILED, PHASE_EXECUTING)


def test_completed_and_cancelled_are_terminal_for_execution():
    with pytest.raises(WorkflowTransitionError, match="completed->pending_approval"):
        assert_transition_allowed(PHASE_COMPLETED, PHASE_PENDING_APPROVAL)
    with pytest.raises(WorkflowTransitionError, match="cancelled->executing"):
        assert_transition_allowed(PHASE_CANCELLED, PHASE_EXECUTING)


def test_clarification_can_resume_planning():
    assert_transition_allowed(PHASE_DRAFT, PHASE_NEEDS_CLARIFICATION)
    assert_transition_allowed(PHASE_NEEDS_CLARIFICATION, PHASE_PLANNING)


def test_generated_ids_have_stable_prefixes_and_are_unique():
    ids = {new_plan_id(), new_revision_id(), new_run_id(), new_thread_id(), new_action_id()}
    assert len(ids) == 5
    assert all("_" in value for value in ids)
    assert new_plan_id().startswith("plan_")
    assert new_revision_id().startswith("rev_")
    assert new_run_id().startswith("run_")
    assert new_thread_id().startswith("thread_")
    assert new_action_id().startswith("act_")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_graph_state.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.graph'`.

- [ ] **Step 3: Implement workflow state helpers**

Create `backend/graph/__init__.py`:

```python
from backend.graph.state import (
    PHASE_APPROVED,
    PHASE_CANCELLED,
    PHASE_COMPLETED,
    PHASE_DRAFT,
    PHASE_EXECUTING,
    PHASE_FAILED,
    PHASE_NEEDS_CLARIFICATION,
    PHASE_PARTIALLY_COMPLETED,
    PHASE_PENDING_APPROVAL,
    PHASE_PLANNING,
    PHASE_VALIDATION_FAILED,
    WorkflowTransitionError,
    assert_transition_allowed,
)

__all__ = [
    "PHASE_APPROVED",
    "PHASE_CANCELLED",
    "PHASE_COMPLETED",
    "PHASE_DRAFT",
    "PHASE_EXECUTING",
    "PHASE_FAILED",
    "PHASE_NEEDS_CLARIFICATION",
    "PHASE_PARTIALLY_COMPLETED",
    "PHASE_PENDING_APPROVAL",
    "PHASE_PLANNING",
    "PHASE_VALIDATION_FAILED",
    "WorkflowTransitionError",
    "assert_transition_allowed",
]
```

Create `backend/graph/state.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/backend/test_graph_state.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/graph tests/backend/test_graph_state.py
git commit -m "feat: add workflow state transitions"
```

## Task 2: JSON SQLite Workflow Repository

**Files:**
- Create: `backend/storage/workflow_repository.py`
- Test: `tests/backend/test_workflow_repository.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/backend/test_workflow_repository.py`:

```python
from pathlib import Path

from backend.storage.workflow_repository import WorkflowRepository


def test_repository_persists_thread_revision_ledger_and_receipt(tmp_path: Path):
    repo = WorkflowRepository(tmp_path / "workflow.sqlite")
    repo.create_thread("thread_1", "run_1", "plan_1", "user_1", "planning")
    repo.save_revision(
        revision_id="rev_1",
        plan_id="plan_1",
        version=1,
        phase="pending_approval",
        goal="friends dinner",
        constraints={"people": {"adults": 4}},
        plan={"id": "plan_1", "title": "Friend plan"},
        validation={"valid": True, "blocking": []},
    )
    repo.upsert_action(
        action_id="act_1",
        revision_id="rev_1",
        tool="send_plan_message",
        status="pending",
        idempotency_key="rev_1:act_1",
        payload={"recipient": "同行人"},
        receipt_id="",
    )
    repo.append_attempt("attempt_1", "act_1", "succeeded", {"tool": "send_plan_message"}, {"id": "MSG-1"}, "")
    repo.append_receipt("MSG-1", "act_1", "rev_1", "send_plan_message", "confirmed", "发送完成", {"recipient": "同行人"})

    loaded = WorkflowRepository(tmp_path / "workflow.sqlite")

    assert loaded.get_thread("thread_1")["plan_id"] == "plan_1"
    assert loaded.get_latest_revision("plan_1")["revision_id"] == "rev_1"
    assert loaded.list_actions("rev_1")[0]["action_id"] == "act_1"
    assert loaded.list_attempts("act_1")[0]["attempt_id"] == "attempt_1"
    assert loaded.list_receipts("rev_1")[0]["receipt_id"] == "MSG-1"


def test_repository_uses_json_not_pickle(tmp_path: Path):
    repo = WorkflowRepository(tmp_path / "workflow.sqlite")
    repo.create_thread("thread_1", "run_1", "plan_1", "user_1", "planning")

    raw = (tmp_path / "workflow.sqlite").read_bytes()

    assert b"pickle" not in raw.lower()
    assert b"thread_1" in raw
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_workflow_repository.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.storage.workflow_repository'`.

- [ ] **Step 3: Implement repository**

Create `backend/storage/workflow_repository.py`:

```python
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class WorkflowRepository:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists plan_threads (
                    thread_id text primary key,
                    run_id text not null,
                    plan_id text not null,
                    user_id text not null,
                    status text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
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
                )
                """
            )
            conn.execute(
                """
                create table if not exists action_ledger (
                    action_id text primary key,
                    revision_id text not null,
                    tool text not null,
                    status text not null,
                    idempotency_key text not null unique,
                    payload_json text not null,
                    receipt_id text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists action_attempts (
                    attempt_id text primary key,
                    action_id text not null,
                    status text not null,
                    request_json text not null,
                    response_json text not null,
                    error text not null,
                    created_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists receipts (
                    receipt_id text primary key,
                    action_id text not null,
                    revision_id text not null,
                    tool text not null,
                    status text not null,
                    detail text not null,
                    payload_json text not null,
                    created_at text not null
                )
                """
            )

    def create_thread(self, thread_id: str, run_id: str, plan_id: str, user_id: str, status: str) -> None:
        now = now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                insert into plan_threads(thread_id, run_id, plan_id, user_id, status, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (thread_id, run_id, plan_id, user_id, status, now, now),
            )

    def update_thread_status(self, thread_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "update plan_threads set status = ?, updated_at = ? where thread_id = ?",
                (status, now_iso(), thread_id),
            )

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from plan_threads where thread_id = ?", (thread_id,)).fetchone()
        if row is None:
            raise KeyError("thread_not_found")
        return dict(row)

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
                insert or replace into plan_revisions(
                    revision_id, plan_id, version, phase, goal,
                    constraints_json, plan_json, validation_json, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    plan_id,
                    version,
                    phase,
                    goal,
                    dumps(constraints),
                    dumps(plan),
                    dumps(validation),
                    now_iso(),
                ),
            )

    def get_latest_revision(self, plan_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "select * from plan_revisions where plan_id = ? order by version desc limit 1",
                (plan_id,),
            ).fetchone()
        if row is None:
            raise KeyError("revision_not_found")
        return decode_revision(row)

    def list_revisions(self, plan_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from plan_revisions where plan_id = ? order by version",
                (plan_id,),
            ).fetchall()
        return [decode_revision(row) for row in rows]

    def upsert_action(
        self,
        action_id: str,
        revision_id: str,
        tool: str,
        status: str,
        idempotency_key: str,
        payload: dict[str, Any],
        receipt_id: str,
    ) -> None:
        now = now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                insert into action_ledger(action_id, revision_id, tool, status, idempotency_key, payload_json, receipt_id, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(action_id) do update set
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    receipt_id = excluded.receipt_id,
                    updated_at = excluded.updated_at
                """,
                (action_id, revision_id, tool, status, idempotency_key, dumps(payload), receipt_id, now, now),
            )

    def list_actions(self, revision_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from action_ledger where revision_id = ? order by created_at, action_id",
                (revision_id,),
            ).fetchall()
        return [decode_action(row) for row in rows]

    def get_action_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select * from action_ledger where idempotency_key = ?", (idempotency_key,)).fetchone()
        return decode_action(row) if row else None

    def append_attempt(self, attempt_id: str, action_id: str, status: str, request: dict[str, Any], response: dict[str, Any], error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "insert into action_attempts(attempt_id, action_id, status, request_json, response_json, error, created_at) values (?, ?, ?, ?, ?, ?, ?)",
                (attempt_id, action_id, status, dumps(request), dumps(response), error, now_iso()),
            )

    def list_attempts(self, action_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from action_attempts where action_id = ? order by created_at",
                (action_id,),
            ).fetchall()
        return [decode_attempt(row) for row in rows]

    def append_receipt(self, receipt_id: str, action_id: str, revision_id: str, tool: str, status: str, detail: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "insert or ignore into receipts(receipt_id, action_id, revision_id, tool, status, detail, payload_json, created_at) values (?, ?, ?, ?, ?, ?, ?, ?)",
                (receipt_id, action_id, revision_id, tool, status, detail, dumps(payload), now_iso()),
            )

    def list_receipts(self, revision_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from receipts where revision_id = ? order by created_at, receipt_id",
                (revision_id,),
            ).fetchall()
        return [decode_receipt(row) for row in rows]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def loads(value: str) -> dict[str, Any]:
    return json.loads(value)


def decode_revision(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["constraints"] = loads(data.pop("constraints_json"))
    data["plan"] = loads(data.pop("plan_json"))
    data["validation"] = loads(data.pop("validation_json"))
    return data


def decode_action(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["payload"] = loads(data.pop("payload_json"))
    return data


def decode_attempt(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["request"] = loads(data.pop("request_json"))
    data["response"] = loads(data.pop("response_json"))
    return data


def decode_receipt(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["payload"] = loads(data.pop("payload_json"))
    return data
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/backend/test_workflow_repository.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/storage/workflow_repository.py tests/backend/test_workflow_repository.py
git commit -m "feat: add workflow repository"
```

## Task 3: Durable Ledger

**Files:**
- Create: `backend/actions/durable_ledger.py`
- Modify: `backend/actions/__init__.py`
- Test: `tests/backend/test_durable_ledger.py`

- [ ] **Step 1: Write failing ledger tests**

Create `tests/backend/test_durable_ledger.py`:

```python
from pathlib import Path

import pytest

from backend.actions.durable_ledger import DurableActionLedger
from backend.storage.workflow_repository import WorkflowRepository


def test_ledger_executes_selected_actions_once_and_preserves_receipts(tmp_path: Path):
    repo = WorkflowRepository(tmp_path / "workflow.sqlite")
    ledger = DurableActionLedger(repo)
    ledger.seed_actions(
        "rev_1",
        [
            {"action_id": "act_msg", "tool": "send_plan_message", "payload": {"recipient": "同行人"}},
            {"action_id": "act_cal", "tool": "create_calendar_event", "payload": {"participants": 1}},
        ],
    )

    first = ledger.mark_executing("rev_1", ["act_msg"])
    ledger.mark_succeeded("act_msg", "MSG-1", "发送完成", {"recipient": "同行人"})
    repeated = ledger.mark_executing("rev_1", ["act_msg"])
    second = ledger.mark_executing("rev_1", ["act_cal"])

    assert [entry["action_id"] for entry in first] == ["act_msg"]
    assert repeated == []
    assert [entry["action_id"] for entry in second] == ["act_cal"]
    assert [receipt["receipt_id"] for receipt in ledger.list_receipts("rev_1")] == ["MSG-1"]
    assert {entry["action_id"]: entry["status"] for entry in ledger.list_actions("rev_1")} == {
        "act_msg": "succeeded",
        "act_cal": "executing",
    }


def test_ledger_survives_repository_reopen(tmp_path: Path):
    db = tmp_path / "workflow.sqlite"
    repo = WorkflowRepository(db)
    ledger = DurableActionLedger(repo)
    ledger.seed_actions("rev_1", [{"action_id": "act_msg", "tool": "send_plan_message", "payload": {"recipient": "同行人"}}])
    ledger.mark_executing("rev_1", ["act_msg"])
    ledger.mark_succeeded("act_msg", "MSG-1", "发送完成", {"recipient": "同行人"})

    reopened = DurableActionLedger(WorkflowRepository(db))

    assert reopened.mark_executing("rev_1", ["act_msg"]) == []
    assert reopened.list_receipts("rev_1")[0]["receipt_id"] == "MSG-1"


def test_unknown_action_id_fails_validation(tmp_path: Path):
    ledger = DurableActionLedger(WorkflowRepository(tmp_path / "workflow.sqlite"))
    ledger.seed_actions("rev_1", [{"action_id": "act_msg", "tool": "send_plan_message", "payload": {}}])

    with pytest.raises(ValueError, match="unknown_action_id"):
        ledger.mark_executing("rev_1", ["missing"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_durable_ledger.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.actions.durable_ledger'`.

- [ ] **Step 3: Implement durable ledger**

Create `backend/actions/durable_ledger.py`:

```python
from __future__ import annotations

from typing import Any

from backend.graph.state import new_id
from backend.storage.workflow_repository import WorkflowRepository


class DurableActionLedger:
    def __init__(self, repository: WorkflowRepository) -> None:
        self.repository = repository

    def seed_actions(self, revision_id: str, actions: list[dict[str, Any]]) -> None:
        for action in actions:
            action_id = str(action["action_id"])
            tool = str(action["tool"])
            payload = dict(action.get("payload", {}))
            self.repository.upsert_action(
                action_id=action_id,
                revision_id=revision_id,
                tool=tool,
                status=str(action.get("status", "pending")),
                idempotency_key=str(action.get("idempotency_key", f"{revision_id}:{action_id}")),
                payload=payload,
                receipt_id=str(action.get("receipt_id", "")),
            )

    def list_actions(self, revision_id: str) -> list[dict[str, Any]]:
        return self.repository.list_actions(revision_id)

    def list_receipts(self, revision_id: str) -> list[dict[str, Any]]:
        return self.repository.list_receipts(revision_id)

    def mark_executing(self, revision_id: str, selected_action_ids: list[str]) -> list[dict[str, Any]]:
        actions = self.repository.list_actions(revision_id)
        by_id = {action["action_id"]: action for action in actions}
        missing = [action_id for action_id in selected_action_ids if action_id not in by_id]
        if missing:
            raise ValueError(f"unknown_action_id:{missing[0]}")
        changed: list[dict[str, Any]] = []
        for action_id in selected_action_ids:
            action = by_id[action_id]
            if action["status"] in {"succeeded", "skipped"}:
                continue
            if action["status"] != "executing":
                self.repository.upsert_action(
                    action_id=action["action_id"],
                    revision_id=action["revision_id"],
                    tool=action["tool"],
                    status="executing",
                    idempotency_key=action["idempotency_key"],
                    payload=action["payload"],
                    receipt_id=action["receipt_id"],
                )
                action = {**action, "status": "executing"}
            changed.append(action)
        return changed

    def mark_succeeded(self, action_id: str, receipt_id: str, detail: str, payload: dict[str, Any]) -> None:
        action = self._find_action(action_id)
        self.repository.append_attempt(
            attempt_id=new_id("attempt"),
            action_id=action_id,
            status="succeeded",
            request={"tool": action["tool"], "payload": action["payload"]},
            response={"receipt_id": receipt_id, "detail": detail},
            error="",
        )
        self.repository.append_receipt(
            receipt_id=receipt_id,
            action_id=action_id,
            revision_id=action["revision_id"],
            tool=action["tool"],
            status="confirmed",
            detail=detail,
            payload=payload,
        )
        self.repository.upsert_action(
            action_id=action["action_id"],
            revision_id=action["revision_id"],
            tool=action["tool"],
            status="succeeded",
            idempotency_key=action["idempotency_key"],
            payload=action["payload"],
            receipt_id=receipt_id,
        )

    def _find_action(self, action_id: str) -> dict[str, Any]:
        for revision_id in self._revision_ids_for_action_scan():
            for action in self.repository.list_actions(revision_id):
                if action["action_id"] == action_id:
                    return action
        raise ValueError(f"unknown_action_id:{action_id}")

    def _revision_ids_for_action_scan(self) -> list[str]:
        with self.repository._connect() as conn:
            rows = conn.execute("select distinct revision_id from action_ledger order by revision_id").fetchall()
        return [str(row["revision_id"]) for row in rows]
```

Modify `backend/actions/__init__.py`:

```python
from backend.actions.durable_ledger import DurableActionLedger

__all__ = ["DurableActionLedger"]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/backend/test_durable_ledger.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/actions/durable_ledger.py backend/actions/__init__.py tests/backend/test_durable_ledger.py
git commit -m "feat: persist action ledger"
```

## Task 4: Deterministic Action Policy

**Files:**
- Create: `backend/actions/policy.py`
- Test: `tests/backend/test_action_policy.py`

- [ ] **Step 1: Write failing action policy tests**

Create `tests/backend/test_action_policy.py`:

```python
from backend.actions.policy import build_executable_actions


def test_policy_does_not_create_activity_reservation_without_booking_intent():
    plan = {
        "itinerary": [
            {"type": "activity", "place_id": "poi_activity", "title": "自习咖啡馆", "start": "14:00", "end": "15:00"}
        ]
    }
    candidates = {"poi_activity": {"booking_supported": True, "category": "social_activity"}}
    constraints = {"required_actions": ["send_plan_message"], "people": {"adults": 1, "children": []}}

    actions = build_executable_actions("rev_1", plan, candidates, constraints)

    assert [action["tool"] for action in actions] == []


def test_policy_creates_restaurant_actions_only_when_requested_and_grounded():
    plan = {
        "itinerary": [
            {"type": "activity", "place_id": "poi_activity", "title": "活动", "start": "14:00", "end": "15:00"},
            {"type": "restaurant", "place_id": "poi_restaurant", "title": "餐厅", "start": "15:45", "end": "16:45"},
        ]
    }
    candidates = {
        "poi_activity": {"booking_supported": False, "category": "social_activity"},
        "poi_restaurant": {"booking_supported": True, "category": "restaurant", "coupon": {"id": "deal_1"}, "menu": [{"id": "menu_1"}]},
    }
    constraints = {
        "required_actions": ["restaurant_reservation", "claim_coupon", "create_order"],
        "people": {"adults": 4, "children": []},
    }

    actions = build_executable_actions("rev_1", plan, candidates, constraints)

    assert [action["tool"] for action in actions] == ["create_reservation", "claim_coupon", "create_order"]
    assert actions[0]["payload"]["time"] == "15:45"
    assert actions[0]["payload"]["party_size"] == 4
    assert all(action["revision_id"] == "rev_1" for action in actions)
    assert all(action["idempotency_key"].startswith("rev_1:") for action in actions)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_action_policy.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.actions.policy'`.

- [ ] **Step 3: Implement action policy**

Create `backend/actions/policy.py`:

```python
from __future__ import annotations

from typing import Any

from backend.graph.state import new_action_id


def build_executable_actions(
    revision_id: str,
    plan: dict[str, Any],
    candidate_lookup: dict[str, dict[str, Any]],
    constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    required = set(constraints.get("required_actions", []))
    party_size = int(constraints.get("people", {}).get("adults", 0)) + len(constraints.get("people", {}).get("children", []))
    actions: list[dict[str, Any]] = []
    steps = list(plan.get("itinerary", []))

    for step in steps:
        place_id = str(step.get("place_id", ""))
        candidate = candidate_lookup.get(place_id, {})
        if step.get("type") == "activity" and "activity_reservation" in required and candidate.get("booking_supported"):
            actions.append(
                make_action(
                    revision_id,
                    "reserve_activity",
                    "预约活动",
                    place_id,
                    {
                        "place_id": place_id,
                        "time": step.get("start", ""),
                        "party_size": party_size,
                    },
                )
            )
        if step.get("type") == "restaurant":
            if "restaurant_reservation" in required and candidate.get("booking_supported"):
                actions.append(
                    make_action(
                        revision_id,
                        "create_reservation",
                        "预订餐厅",
                        place_id,
                        {
                            "place_id": place_id,
                            "time": step.get("start", ""),
                            "party_size": party_size,
                        },
                    )
                )
            if "claim_coupon" in required and candidate.get("coupon"):
                actions.append(
                    make_action(
                        revision_id,
                        "claim_coupon",
                        "领取团购券",
                        place_id,
                        {
                            "place_id": place_id,
                            "deal_id": candidate["coupon"]["id"],
                        },
                    )
                )
            if "create_order" in required and candidate.get("menu"):
                actions.append(
                    make_action(
                        revision_id,
                        "create_order",
                        "创建点单",
                        place_id,
                        {
                            "shop_id": place_id,
                            "items": candidate["menu"],
                            "pickup_time": step.get("start", ""),
                        },
                    )
                )
    return actions


def make_action(revision_id: str, tool: str, label: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
    action_id = new_action_id()
    return {
        "action_id": action_id,
        "revision_id": revision_id,
        "tool": tool,
        "label": label,
        "target": target,
        "status": "pending",
        "idempotency_key": f"{revision_id}:{action_id}",
        "requires_confirmation": True,
        "payload": payload,
        "receipt_id": "",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/backend/test_action_policy.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/actions/policy.py tests/backend/test_action_policy.py
git commit -m "feat: add deterministic action policy"
```

## Task 5: Business Validation Gate

**Files:**
- Create: `backend/validation/business.py`
- Modify: `backend/validation/__init__.py`
- Test: `tests/backend/test_business_validation.py`

- [ ] **Step 1: Write failing validation tests**

Create `tests/backend/test_business_validation.py`:

```python
from backend.validation.business import validate_revision_for_approval


def test_validation_blocks_mismatched_availability_slot():
    plan = {
        "itinerary": [
            {"type": "restaurant", "place_id": "poi_restaurant", "title": "餐厅", "start": "15:35", "end": "16:35"}
        ],
        "route": {"legs": [{"from": "origin_home", "to": "poi_restaurant"}], "total_travel_minutes": 12},
    }
    candidates = {
        "poi_restaurant": {
            "category": "restaurant",
            "open_hours": [{"day": "today", "start": "10:00", "end": "22:00"}],
            "availability": [{"time": "13:30", "available": True, "capacity": 4}],
            "avg_price": 200,
            "tags": [],
        }
    }
    constraints = {"time_window": {"date": "today", "duration_hours": 2}, "people": {"adults": 2, "children": []}, "preferences": {"budget_level": "medium"}}
    actions = [{"tool": "create_reservation", "payload": {"place_id": "poi_restaurant", "time": "15:35", "party_size": 2}}]

    report = validate_revision_for_approval(plan, candidates, constraints, actions, weather={"condition": "clear"})

    assert not report["valid"]
    assert "availability_slot_mismatch" in [issue["code"] for issue in report["blocking"]]


def test_validation_blocks_missing_origin_route_leg():
    plan = {
        "itinerary": [
            {"type": "activity", "place_id": "poi_activity", "title": "活动", "start": "14:00", "end": "15:00"}
        ],
        "route": {"legs": [], "total_travel_minutes": 0},
    }
    candidates = {
        "poi_activity": {
            "category": "social_activity",
            "open_hours": [{"day": "today", "start": "10:00", "end": "22:00"}],
            "availability": [],
            "avg_price": 100,
            "tags": [],
        }
    }
    constraints = {"time_window": {"date": "today", "duration_hours": 1}, "people": {"adults": 1, "children": []}, "preferences": {"budget_level": "medium"}}

    report = validate_revision_for_approval(plan, candidates, constraints, [], weather={"condition": "clear"})

    assert not report["valid"]
    assert "missing_origin_route_leg" in [issue["code"] for issue in report["blocking"]]


def test_validation_passes_grounded_executable_plan():
    plan = {
        "itinerary": [
            {"type": "activity", "place_id": "poi_activity", "title": "活动", "start": "14:00", "end": "15:00"}
        ],
        "route": {"legs": [{"from": "origin_home", "to": "poi_activity"}], "total_travel_minutes": 12},
    }
    candidates = {
        "poi_activity": {
            "category": "social_activity",
            "open_hours": [{"day": "today", "start": "10:00", "end": "22:00"}],
            "availability": [],
            "avg_price": 100,
            "tags": [],
        }
    }
    constraints = {"time_window": {"date": "today", "duration_hours": 2}, "people": {"adults": 1, "children": []}, "preferences": {"budget_level": "medium"}}

    report = validate_revision_for_approval(plan, candidates, constraints, [], weather={"condition": "clear"})

    assert report["valid"]
    assert report["blocking"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_business_validation.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.validation.business'`.

- [ ] **Step 3: Implement validation gate**

Create `backend/validation/business.py`:

```python
from __future__ import annotations

from typing import Any


def validate_revision_for_approval(
    plan: dict[str, Any],
    candidate_lookup: dict[str, dict[str, Any]],
    constraints: dict[str, Any],
    actions: list[dict[str, Any]],
    weather: dict[str, Any],
) -> dict[str, Any]:
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    steps = [step for step in plan.get("itinerary", []) if step.get("type") != "transport"]
    date_value = str(constraints.get("time_window", {}).get("date", "today"))
    party_size = int(constraints.get("people", {}).get("adults", 0)) + len(constraints.get("people", {}).get("children", []))

    if party_size <= 0:
        blocking.append({"code": "party_size_missing"})

    if steps and not has_origin_route_leg(plan.get("route", {}), steps[0].get("place_id", "")):
        blocking.append({"code": "missing_origin_route_leg"})

    for step in steps:
        place_id = str(step.get("place_id", ""))
        candidate = candidate_lookup.get(place_id)
        if not candidate:
            blocking.append({"code": "ungrounded_step", "place_id": place_id})
            continue
        if not is_open_at(candidate.get("open_hours", []), date_value, str(step.get("start", ""))):
            blocking.append({"code": "closed_at_visit_time", "place_id": place_id, "time": step.get("start", "")})
        if weather.get("condition") == "rain" and "outdoor" in candidate.get("tags", []):
            warnings.append({"code": "weather_mismatch", "place_id": place_id})
        if step.get("type") == "restaurant":
            validate_restaurant_slot(blocking, candidate, step, party_size)

    for action in actions:
        payload = action.get("payload", {})
        place_id = payload.get("place_id") or payload.get("shop_id")
        matching_step = next((step for step in steps if step.get("place_id") == place_id), None)
        if matching_step and payload.get("time") and payload.get("time") != matching_step.get("start"):
            blocking.append({"code": "action_time_mismatch", "action_id": action.get("action_id"), "place_id": place_id})
        if not action.get("idempotency_key"):
            blocking.append({"code": "missing_idempotency_key", "action_id": action.get("action_id")})

    return {"valid": not blocking, "blocking": blocking, "warnings": warnings}


def has_origin_route_leg(route: dict[str, Any], first_place_id: str) -> bool:
    return any(leg.get("from") == "origin_home" and leg.get("to") == first_place_id for leg in route.get("legs", []))


def is_open_at(open_hours: list[dict[str, Any]], date_value: str, time_value: str) -> bool:
    if not open_hours:
        return True
    for item in open_hours:
        day = str(item.get("day", date_value))
        if day != date_value:
            continue
        if str(item.get("start", "00:00")) <= time_value <= str(item.get("end", "23:59")):
            return True
    return False


def validate_restaurant_slot(blocking: list[dict[str, Any]], candidate: dict[str, Any], step: dict[str, Any], party_size: int) -> None:
    availability = candidate.get("availability", [])
    if not availability:
        return
    for slot in availability:
        if slot.get("time") == step.get("start") and bool(slot.get("available")) and int(slot.get("capacity", 0)) >= party_size:
            return
    blocking.append({"code": "availability_slot_mismatch", "place_id": step.get("place_id"), "time": step.get("start")})
```

Modify `backend/validation/__init__.py`:

```python
from backend.validation.business import validate_revision_for_approval

__all__ = ["validate_revision_for_approval"]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/backend/test_business_validation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/validation/business.py backend/validation/__init__.py tests/backend/test_business_validation.py
git commit -m "feat: add business validation gate"
```

## Task 6: Workflow Service Initial Run and Revision Creation

**Files:**
- Create: `backend/services/workflow_service.py`
- Modify: `backend/services/__init__.py`
- Test: `tests/backend/test_workflow_service.py`

- [ ] **Step 1: Write failing workflow service tests**

Create `tests/backend/test_workflow_service.py`:

```python
from pathlib import Path

from backend.llm.config import LLMConfig
from backend.services.workflow_service import WorkflowService
from tests.backend.helpers import RuleBasedLLMClient


def make_service(tmp_path: Path) -> WorkflowService:
    service = WorkflowService(
        repository_path=tmp_path / "workflow.sqlite",
        llm_config=LLMConfig(base_url="https://example.test/v1", api_key="secret", model="test-model", remote_enabled=True),
    )
    service.pipeline.llm = RuleBasedLLMClient()
    return service


def test_start_run_creates_durable_ids_and_latest_revision(tmp_path: Path):
    service = make_service(tmp_path)

    started = service.start_run("我想找个地方写代码一小时", user_id="user_1")
    plan = service.get_plan(started["plan_id"])

    assert started["run_id"].startswith("run_")
    assert started["thread_id"].startswith("thread_")
    assert started["plan_id"].startswith("plan_")
    assert plan["plan_id"] == started["plan_id"]
    assert plan["revision"]["revision_id"].startswith("rev_")
    assert plan["revision"]["phase"] in {"pending_approval", "validation_failed", "needs_clarification"}


def test_clarification_run_is_not_listed_as_executable_plan(tmp_path: Path):
    service = make_service(tmp_path)

    started = service.start_run("周末安排一下", user_id="user_1")
    plan = service.get_plan(started["plan_id"])
    listed = service.list_plans()

    assert plan["revision"]["phase"] == "needs_clarification"
    assert listed["plans"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_workflow_service.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.workflow_service'`.

- [ ] **Step 3: Implement workflow service start path**

Create `backend/services/workflow_service.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.actions.policy import build_executable_actions
from backend.data.catalog import LocalDataCatalog
from backend.graph.state import (
    PHASE_NEEDS_CLARIFICATION,
    PHASE_PENDING_APPROVAL,
    PHASE_VALIDATION_FAILED,
    new_plan_id,
    new_revision_id,
    new_run_id,
    new_thread_id,
)
from backend.llm import LLMConfig
from backend.orchestrator import PlanningPipeline
from backend.storage.workflow_repository import WorkflowRepository
from backend.validation.business import validate_revision_for_approval


class WorkflowService:
    def __init__(
        self,
        catalog: LocalDataCatalog | None = None,
        llm_config: LLMConfig | None = None,
        repository_path: Path | str | None = None,
    ) -> None:
        self.catalog = catalog or LocalDataCatalog()
        self.pipeline = PlanningPipeline(self.catalog, llm_config)
        self.repository = WorkflowRepository(repository_path or Path(".weekendpilot/workflow.sqlite"))

    def start_run(self, goal: str, user_id: str = "local_demo_user") -> dict[str, str]:
        if not goal.strip():
            raise ValueError("validation_error")
        thread_id = new_thread_id()
        run_id = new_run_id()
        plan_id = new_plan_id()
        revision_id = new_revision_id()
        self.repository.create_thread(thread_id, run_id, plan_id, user_id, "planning")
        state = self.pipeline.build(goal)
        if state.status == "needs_clarification":
            phase = PHASE_NEEDS_CLARIFICATION
            plan_payload = {
                "id": plan_id,
                "status": phase,
                "missing_fields": state.context.get("missing_fields", []),
                "clarifying_questions": state.context.get("clarifying_questions", []),
            }
            validation = {"valid": False, "blocking": [{"code": "needs_clarification"}], "warnings": []}
            constraints = {}
        else:
            plan_payload = state.plan_dict()
            plan_payload["id"] = plan_id
            constraints = plan_payload.get("constraints") or {}
            candidate_lookup = {item["id"]: item for group in state.ranked.values() for item in group}
            actions = build_executable_actions(revision_id, plan_payload, candidate_lookup, constraints)
            route = ensure_origin_route(state.route or plan_payload.get("route") or {}, plan_payload.get("itinerary", []))
            plan_payload["route"] = route
            validation = validate_revision_for_approval(
                {**plan_payload, "route": route},
                candidate_lookup,
                constraints,
                actions,
                state.context.get("weather", {}),
            )
            phase = PHASE_PENDING_APPROVAL if validation["valid"] else PHASE_VALIDATION_FAILED
            for action in actions:
                self.repository.upsert_action(
                    action_id=action["action_id"],
                    revision_id=revision_id,
                    tool=action["tool"],
                    status=action["status"],
                    idempotency_key=action["idempotency_key"],
                    payload=action["payload"],
                    receipt_id="",
                )
        self.repository.save_revision(
            revision_id=revision_id,
            plan_id=plan_id,
            version=1,
            phase=phase,
            goal=goal,
            constraints=constraints,
            plan=plan_payload,
            validation=validation,
        )
        self.repository.update_thread_status(thread_id, phase)
        return {"run_id": run_id, "thread_id": thread_id, "plan_id": plan_id}

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        revision = self.repository.get_latest_revision(plan_id)
        actions = self.repository.list_actions(revision["revision_id"])
        receipts = self.repository.list_receipts(revision["revision_id"])
        return {
            "plan_id": plan_id,
            "revision": revision,
            "actions": actions,
            "receipts": receipts,
        }

    def list_plans(self) -> dict[str, Any]:
        with self.repository._connect() as conn:
            rows = conn.execute(
                """
                select r.*
                from plan_revisions r
                join (
                    select plan_id, max(version) as version
                    from plan_revisions
                    group by plan_id
                ) latest
                on latest.plan_id = r.plan_id and latest.version = r.version
                where r.phase != ?
                order by r.created_at desc
                """,
                (PHASE_NEEDS_CLARIFICATION,),
            ).fetchall()
        plans = []
        for row in rows:
            revision = self.repository.get_latest_revision(row["plan_id"])
            plan = revision["plan"]
            plans.append(
                {
                    "id": revision["plan_id"],
                    "revision_id": revision["revision_id"],
                    "phase": revision["phase"],
                    "title": plan.get("title", "本地生活计划"),
                    "summary": plan.get("summary", ""),
                }
            )
        return {"plans": plans, "total": len(plans)}
```

Modify `backend/services/__init__.py`:

```python
from backend.services.planning_service import PlanningService
from backend.services.workflow_service import WorkflowService

__all__ = ["PlanningService", "WorkflowService"]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/backend/test_workflow_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/workflow_service.py backend/services/__init__.py tests/backend/test_workflow_service.py
git commit -m "feat: start durable workflow runs"
```

## Task 7: Resume Approval and Execute Selected Actions

**Files:**
- Modify: `backend/services/workflow_service.py`
- Test: `tests/backend/test_workflow_service.py`

- [ ] **Step 1: Add failing resume tests**

Append to `tests/backend/test_workflow_service.py`:

```python
def test_validation_failed_revision_cannot_be_approved(tmp_path: Path):
    service = make_service(tmp_path)
    started = service.start_run("今天下午朋友10个人出去玩，先活动再吃饭", user_id="user_1")
    plan = service.get_plan(started["plan_id"])

    assert plan["revision"]["phase"] == "validation_failed"

    try:
        service.resume(started["plan_id"], {"decision": "approve", "selected_action_ids": []})
    except ValueError as exc:
        assert str(exc) == "validation_failed"
    else:
        raise AssertionError("validation_failed revision was approved")


def test_resume_approve_executes_selected_actions_and_appends_receipts(tmp_path: Path):
    service = make_service(tmp_path)
    started = service.start_run("我想找个地方写代码一小时", user_id="user_1")
    plan = service.get_plan(started["plan_id"])
    selected = [action["action_id"] for action in plan["actions"][:1]]

    resumed = service.resume(started["plan_id"], {"decision": "approve", "selected_action_ids": selected})
    loaded = service.get_plan(started["plan_id"])

    assert resumed["revision"]["phase"] in {"completed", "partially_completed"}
    assert len(loaded["receipts"]) == 1
    assert loaded["receipts"][0]["action_id"] == selected[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_workflow_service.py::test_validation_failed_revision_cannot_be_approved tests/backend/test_workflow_service.py::test_resume_approve_executes_selected_actions_and_appends_receipts -q
```

Expected: FAIL with `AttributeError: 'WorkflowService' object has no attribute 'resume'`.

- [ ] **Step 3: Implement resume path**

Add these imports to `backend/services/workflow_service.py`:

```python
from backend.actions.durable_ledger import DurableActionLedger
from backend.graph.state import PHASE_COMPLETED, PHASE_PARTIALLY_COMPLETED
```

Add this method to `WorkflowService`:

```python
    def resume(self, plan_id: str, decision: dict[str, Any]) -> dict[str, Any]:
        revision = self.repository.get_latest_revision(plan_id)
        phase = revision["phase"]
        if decision.get("decision") == "reject":
            self.repository.save_revision(
                revision_id=revision["revision_id"],
                plan_id=plan_id,
                version=int(revision["version"]),
                phase="cancelled",
                goal=revision["goal"],
                constraints=revision["constraints"],
                plan=revision["plan"],
                validation=revision["validation"],
            )
            return self.get_plan(plan_id)
        if decision.get("decision") != "approve":
            raise ValueError("unsupported_decision")
        if phase != PHASE_PENDING_APPROVAL:
            raise ValueError(phase)
        selected = [str(action_id) for action_id in decision.get("selected_action_ids", [])]
        ledger = DurableActionLedger(self.repository)
        executable = ledger.mark_executing(revision["revision_id"], selected)
        for action in executable:
            receipt_id = receipt_id_for(action)
            ledger.mark_succeeded(
                action_id=action["action_id"],
                receipt_id=receipt_id,
                detail=f"{action['tool']} completed",
                payload=action["payload"],
            )
        actions = ledger.list_actions(revision["revision_id"])
        remaining = [action for action in actions if action["status"] not in {"succeeded", "skipped"}]
        next_phase = PHASE_COMPLETED if not remaining else PHASE_PARTIALLY_COMPLETED
        self.repository.save_revision(
            revision_id=revision["revision_id"],
            plan_id=plan_id,
            version=int(revision["version"]),
            phase=next_phase,
            goal=revision["goal"],
            constraints=revision["constraints"],
            plan={**revision["plan"], "status": next_phase},
            validation=revision["validation"],
        )
        return self.get_plan(plan_id)
```

Add these functions at module level in `backend/services/workflow_service.py`:

```python
def receipt_id_for(action: dict[str, Any]) -> str:
    prefix = {
        "reserve_activity": "TKT",
        "create_reservation": "RES",
        "claim_coupon": "CPN",
        "create_order": "ORD",
        "send_plan_message": "MSG",
        "create_calendar_event": "CAL",
    }.get(action["tool"], "RCT")
    return f"{prefix}-{action['action_id'].split('_', 1)[1][:12].upper()}"


def ensure_origin_route(route: dict[str, Any], itinerary: list[dict[str, Any]]) -> dict[str, Any]:
    first = next((step for step in itinerary if step.get("place_id") and step.get("place_id") != "origin_home"), None)
    if not first:
        return route
    first_place_id = str(first["place_id"])
    legs = list(route.get("legs", []))
    has_origin = any(leg.get("from") == "origin_home" and leg.get("to") == first_place_id for leg in legs)
    if has_origin:
        return route
    origin_leg = {
        "from": "origin_home",
        "to": first_place_id,
        "mode": "taxi",
        "duration_minutes": 12,
        "distance_km": 2.0,
        "route_summary": "当前位置到第一站",
    }
    return {
        **route,
        "legs": [origin_leg, *legs],
        "total_travel_minutes": int(route.get("total_travel_minutes", 0)) + 12,
        "drive_time_minutes": int(route.get("drive_time_minutes", 0)) + 12,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/backend/test_workflow_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/workflow_service.py tests/backend/test_workflow_service.py
git commit -m "feat: resume workflow approvals"
```

## Task 8: Graph Run API

**Files:**
- Modify: `backend/api/app.py`
- Test: `tests/backend/test_graph_run_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/backend/test_graph_run_api.py`:

```python
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.llm.config import LLMConfig
from backend.services.workflow_service import WorkflowService
from tests.backend.helpers import RuleBasedLLMClient


def make_client(tmp_path):
    workflow = WorkflowService(
        repository_path=tmp_path / "workflow.sqlite",
        llm_config=LLMConfig(base_url="https://example.test/v1", api_key="secret", model="test-model", remote_enabled=True),
    )
    workflow.pipeline.llm = RuleBasedLLMClient()
    client = TestClient(create_app(workflow_service=workflow), raise_server_exceptions=False)
    return client


def test_start_run_get_plan_and_resume(tmp_path):
    client = make_client(tmp_path)

    start = client.post("/api/plans/runs", json={"goal": "我想找个地方写代码一小时", "user_id": "user_1"})
    assert start.status_code == 200
    plan_id = start.json()["plan_id"]

    loaded = client.get(f"/api/plans/{plan_id}")
    assert loaded.status_code == 200
    actions = loaded.json()["actions"]

    resumed = client.post(f"/api/plans/{plan_id}/resume", json={"decision": "approve", "selected_action_ids": [actions[0]["action_id"]]})
    assert resumed.status_code == 200
    assert len(resumed.json()["receipts"]) == 1


def test_legacy_direct_confirm_and_execute_are_disabled(tmp_path):
    client = make_client(tmp_path)

    assert client.post("/api/plans/plan_1/confirm", json={"confirmed": True}).status_code == 410
    assert client.post("/api/plans/plan_1/execute", json={"confirmed": True}).status_code == 410
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_graph_run_api.py -q
```

Expected: FAIL with `TypeError: create_app() got an unexpected keyword argument 'workflow_service'`.

- [ ] **Step 3: Add graph-run API endpoints and disable old direct mutation**

Change the signature in `backend/api/app.py`:

```python
def create_app(service: PlanningService | None = None, workflow_service: WorkflowService | None = None) -> FastAPI:
```

Add import:

```python
from backend.services import PlanningService, WorkflowService
```

Set app state after `planning_service`:

```python
    api.state.workflow_service = workflow_service or WorkflowService()
```

Add endpoints before the old `/api/plans/{plan_id}` route:

```python
    @api.post("/api/plans/runs")
    async def start_plan_run(request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        return workflow(request).start_run(
            str(body.get("goal", "")),
            user_id=str(body.get("user_id", "local_demo_user")),
        )

    @api.get("/api/plans/{plan_id}/versions")
    async def plan_versions(plan_id: str, request: Request) -> dict[str, Any]:
        repo = workflow(request).repository
        return {"plan_id": plan_id, "versions": repo.list_revisions(plan_id)}
```

Change existing `get_plan` endpoint to use workflow service:

```python
    @api.get("/api/plans/{plan_id}")
    async def get_plan(plan_id: str, request: Request) -> dict[str, Any]:
        return workflow(request).get_plan(plan_id)
```

Add resume endpoint:

```python
    @api.post("/api/plans/{plan_id}/resume")
    async def resume_plan(plan_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        return workflow(request).resume(plan_id, body)
```

Replace old direct confirm and execute endpoint bodies:

```python
    @api.post("/api/plans/{plan_id}/confirm")
    async def confirm_plan(plan_id: str, request: Request) -> dict[str, Any]:
        return error_payload("legacy_endpoint_disabled", 410)

    @api.post("/api/plans/{plan_id}/execute")
    async def execute_plan(plan_id: str, request: Request) -> dict[str, Any]:
        return error_payload("legacy_endpoint_disabled", 410)
```

Add helpers at the bottom of `backend/api/app.py`:

```python
def workflow(request: Request) -> WorkflowService:
    return request.app.state.workflow_service


def error_payload(error: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": error, "message": error}}, status_code=status_code)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/backend/test_graph_run_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/app.py tests/backend/test_graph_run_api.py
git commit -m "feat: expose graph run api"
```

## Task 9: Stable Run Stream Events

**Files:**
- Create: `backend/graph/events.py`
- Modify: `backend/services/workflow_service.py`
- Modify: `backend/api/app.py`
- Test: `tests/backend/test_graph_run_api.py`

- [ ] **Step 1: Add failing stream test**

Append to `tests/backend/test_graph_run_api.py`:

```python
def test_run_stream_has_stable_event_ids_and_does_not_create_new_plan(tmp_path):
    client = make_client(tmp_path)
    start = client.post("/api/plans/runs", json={"goal": "我想找个地方写代码一小时", "user_id": "user_1"}).json()

    response = client.get(f"/api/plans/runs/{start['run_id']}/stream")

    assert response.status_code == 200
    text = response.text
    assert "id: evt_" in text
    assert "event: graph_update" in text
    assert start["plan_id"] in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_graph_run_api.py::test_run_stream_has_stable_event_ids_and_does_not_create_new_plan -q
```

Expected: FAIL with HTTP 404.

- [ ] **Step 3: Implement stream event helper and endpoint**

Create `backend/graph/events.py`:

```python
from __future__ import annotations

import json
from typing import Any


def sse_event(event_id: str, event: str, data: dict[str, Any]) -> str:
    return f"id: {event_id}\nevent: {event}\ndata: {json.dumps(data, ensure_ascii=False, sort_keys=True)}\n\n"
```

Add method to `WorkflowService`:

```python
    def stream_run_events(self, run_id: str) -> list[dict[str, Any]]:
        with self.repository._connect() as conn:
            thread = conn.execute("select * from plan_threads where run_id = ?", (run_id,)).fetchone()
        if thread is None:
            raise KeyError("run_not_found")
        plan = self.get_plan(str(thread["plan_id"]))
        return [
            {
                "event_id": "evt_000001",
                "event": "graph_update",
                "data": {
                    "run_id": run_id,
                    "thread_id": str(thread["thread_id"]),
                    "plan_id": str(thread["plan_id"]),
                    "phase": plan["revision"]["phase"],
                    "revision_id": plan["revision"]["revision_id"],
                },
            }
        ]
```

Add endpoint in `backend/api/app.py`:

```python
    @api.get("/api/plans/runs/{run_id}/stream")
    async def stream_plan_run(run_id: str, request: Request) -> StreamingResponse:
        from backend.graph.events import sse_event

        events = workflow(request).stream_run_events(run_id)

        async def event_stream():
            for item in events:
                yield sse_event(item["event_id"], item["event"], item["data"])

        return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/backend/test_graph_run_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/graph/events.py backend/services/workflow_service.py backend/api/app.py tests/backend/test_graph_run_api.py
git commit -m "feat: stream graph run events"
```

## Task 10: Full Backend Regression

**Files:**
- Modify: existing tests if old direct endpoint assertions need to move to graph-run API expectations.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
uv run pytest tests/backend/test_graph_state.py tests/backend/test_workflow_repository.py tests/backend/test_durable_ledger.py tests/backend/test_action_policy.py tests/backend/test_business_validation.py tests/backend/test_workflow_service.py tests/backend/test_graph_run_api.py -q
```

Expected: PASS.

- [ ] **Step 2: Run all backend tests**

Run:

```bash
uv run pytest tests/backend -q
```

Expected: Either PASS, or failures only in tests that still assert legacy confirm/execute behavior.

- [ ] **Step 3: Update legacy tests to assert disabled endpoints**

For tests that call `/api/plans/{plan_id}/confirm` or `/api/plans/{plan_id}/execute`, change the expected behavior to HTTP 410 for direct API calls. Service-level tests for `PlanningService` can remain temporarily if they document the legacy layer, but new graph-run tests must be the release gate.

Example replacement for old API test assertions:

```python
response = client.post(f"/api/plans/{plan_id}/confirm", json={"confirmed": True})
assert response.status_code == 410
assert response.json()["error"]["code"] == "legacy_endpoint_disabled"
```

- [ ] **Step 4: Run complete project tests**

Run:

```bash
npm run test:all
```

Expected: PASS after frontend/contract tests that assumed legacy direct endpoints are either updated or marked out of scope for the backend-only redesign.

- [ ] **Step 5: Commit**

```bash
git add backend tests
git commit -m "test: align backend with graph workflow contract"
```

## Self-Review Checklist

- Spec coverage:
  - Durable state and transitions: Task 1.
  - JSON persistence instead of pickle for new workflow state: Task 2.
  - Persistent side-effect ledger and append-only receipts: Task 3.
  - Deterministic action policy: Task 4.
  - Approval validation gate: Task 5.
  - Run, revision, and plan service: Task 6.
  - Approval resume and selected action execution: Task 7.
  - Backend-authoritative graph-run API: Task 8.
  - Stable SSE run stream identity: Task 9.
  - Regression pass and old endpoint hard-disable expectations: Task 10.
- Scope note: this plan intentionally leaves full planner node decomposition for a follow-up plan after the new workflow contract is in place.
- Type consistency: `plan_id`, `revision_id`, `run_id`, `thread_id`, `action_id`, `phase`, `validation`, `actions`, and `receipts` use the same field names across tasks.
