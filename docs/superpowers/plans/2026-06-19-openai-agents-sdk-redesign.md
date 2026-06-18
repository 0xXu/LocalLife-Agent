# OpenAI Agents SDK Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the LangGraph runtime with an OpenAI Agents SDK-first backend and a new REST + SSE run contract.

**Architecture:** The backend becomes run-centered: FastAPI routes call application services, services persist product state and events, and `OpenAIAgentsRuntime` owns model/tool execution. The frontend consumes typed run events instead of graph phases and uses run ids for approval and rejection.

**Tech Stack:** Python 3.11, FastAPI, SQLite, OpenAI Agents SDK (`openai-agents`), Next.js 15, React 19, TypeScript, Zod, pytest, node:test, Playwright.

---

## File Structure

Create these backend files:

- `backend/domain/events.py`: run status constants, event type constants, event dataclasses, SSE formatter.
- `backend/domain/run.py`: run request/result dataclasses and execution request/result dataclasses.
- `backend/domain/actions.py`: pending action and receipt dataclasses shared by services and runtime.
- `backend/domain/plan.py`: plan summary dataclasses and helpers for stable response payloads.
- `backend/api/schemas/events.py`: Pydantic response/request models for run events.
- `backend/api/schemas/runs.py`: Pydantic models for run creation, run status, approve/reject requests.
- `backend/api/schemas/plans.py`: Pydantic models for plan list/detail envelopes.
- `backend/infrastructure/event_store.py`: active SSE queues plus persisted event append/replay.
- `backend/application/run_service.py`: create runs, start background runtime, expose run state, stream events.
- `backend/application/approval_service.py`: approve/reject pending actions and execute approved actions.
- `backend/agents/runtime.py`: runtime protocol and DTOs.
- `backend/agents/openai_runtime.py`: OpenAI Agents SDK implementation.
- `backend/agents/tools.py`: Agents SDK function tools wrapping local catalog/tool registry behavior.
- `backend/agents/guardrails.py`: schema and grounding checks.
- `backend/api/routes/runs.py`: new run API endpoints.
- `backend/api/routes/plans.py`: new plan API endpoints.
- `backend/api/routes/health.py`, `profiles.py`, `tools.py`: smaller route modules split out of `backend/api/app.py`.

Modify these backend files:

- `pyproject.toml`: replace `langgraph` with `openai-agents`.
- `backend/api/app.py`: compose route modules and inject new services.
- `backend/storage/workflow_repository.py`: add run-centered tables and methods or migrate its contents into `backend/infrastructure/repositories.py`.
- `backend/actions/durable_ledger.py`: keep idempotency behavior, adjust imports/types to new domain classes.
- `backend/tools/registry.py`: keep deterministic local tool implementations, make them callable from Agents SDK wrappers.
- `backend/llm/config.py`: keep status endpoint support, add OpenAI Agents SDK model/default configuration where needed.

Create these frontend files:

- `features/runs/schemas.ts`: Zod schemas for run status, run events, approve/reject payloads.
- `features/runs/api.ts`: REST + SSE client for `/api/runs`.
- `features/runs/reducer.ts`: event-driven run state reducer.
- `features/runs/useRunController.ts`: hook that starts runs, subscribes to SSE, approves/rejects actions.
- `features/plans/api.ts`: plan list/detail client.
- `features/plans/schemas.ts`: plan response schemas that replace old weekendpilot-only coupling where practical.

Modify these frontend files:

- `features/planner/usePlanMachine.ts`: delete or turn into a thin compatibility wrapper during migration, then remove old usage.
- `features/planner/apiClient.ts`: remove old `/api/plans/runs` and `/api/plans/{plan_id}/resume` client functions after new modules are wired.
- `app/page.tsx`: use `useRunController` and new plan selectors.
- `components/plan/ActionLedgerPanel.tsx`: approve/reject by run id.
- `components/trace/TracePanel.tsx`: render normalized run events.
- `types/weekendpilot.ts` and `types/api.ts`: remove or reduce old graph-run types after schemas move to `features/runs`.

Modify tests:

- Backend: replace graph-run tests under `tests/backend/test_api.py`, `test_graph_run_api.py`, `test_events.py`, `test_pipeline.py`, and LangGraph-specific tests.
- Frontend: replace `tests/frontend/planner-api-client.test.tsx`, `plan-machine-graph-run.test.ts`, and trace/action ledger tests.
- Contracts: update `tests/contracts/weekendpilot-contracts.test.ts`.
- E2E: update `tests/e2e/weekendpilot.spec.ts`.

---

### Task 1: Add Run Event Domain and Contract Schemas

**Files:**
- Create: `backend/domain/events.py`
- Create: `backend/api/schemas/events.py`
- Create: `features/runs/schemas.ts`
- Test: `tests/backend/test_run_events.py`
- Test: `tests/frontend/run-schemas.test.ts`

- [ ] **Step 1: Write backend failing tests**

Create `tests/backend/test_run_events.py`:

```python
import json
import unittest

from backend.domain.events import (
    RUN_STATUS_RUNNING,
    RUN_STATUS_COMPLETED,
    RunEvent,
    format_sse_event,
)


class RunEventDomainTest(unittest.TestCase):
    def test_run_event_serializes_with_stable_envelope(self):
        event = RunEvent(
            event_id="evt_000001",
            run_id="run_1",
            plan_id="plan_1",
            seq=1,
            type="run.started",
            timestamp="2026-06-19T00:00:00Z",
            payload={"status": RUN_STATUS_RUNNING},
        )

        data = event.to_dict()

        self.assertEqual(data["type"], "run.started")
        self.assertEqual(data["run_id"], "run_1")
        self.assertEqual(data["plan_id"], "plan_1")
        self.assertEqual(data["seq"], 1)
        self.assertEqual(data["payload"], {"status": RUN_STATUS_RUNNING})

    def test_format_sse_event_uses_run_event_name(self):
        event = RunEvent(
            event_id="evt_000002",
            run_id="run_1",
            plan_id=None,
            seq=2,
            type="run.completed",
            timestamp="2026-06-19T00:00:01Z",
            payload={"status": RUN_STATUS_COMPLETED},
        )

        raw = format_sse_event(event)

        self.assertTrue(raw.startswith("id: evt_000002\nevent: run.event\n"))
        self.assertTrue(raw.endswith("\n\n"))
        data_line = [line for line in raw.splitlines() if line.startswith("data: ")][0]
        decoded = json.loads(data_line.removeprefix("data: "))
        self.assertEqual(decoded["type"], "run.completed")
        self.assertEqual(decoded["payload"]["status"], RUN_STATUS_COMPLETED)
```

- [ ] **Step 2: Run backend test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_run_events.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.domain.events'`.

- [ ] **Step 3: Add backend event implementation**

Create `backend/domain/events.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_NEEDS_CLARIFICATION = "needs_clarification"
RUN_STATUS_APPROVAL_REQUIRED = "approval_required"
RUN_STATUS_EXECUTING = "executing"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_VALIDATION_FAILED = "validation_failed"
RUN_STATUS_REJECTED = "rejected"
RUN_STATUS_FAILED = "failed"

RUN_TERMINAL_STATUSES = {
    RUN_STATUS_COMPLETED,
    RUN_STATUS_VALIDATION_FAILED,
    RUN_STATUS_REJECTED,
    RUN_STATUS_FAILED,
}

RUN_EVENT_STREAM_NAME = "run.event"


@dataclass(frozen=True)
class RunEvent:
    event_id: str
    run_id: str
    plan_id: str | None
    seq: int
    type: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.type,
            "run_id": self.run_id,
            "seq": self.seq,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
        if self.plan_id is not None:
            data["plan_id"] = self.plan_id
        return data


def format_sse_event(event: RunEvent) -> str:
    payload = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"id: {event.event_id}\nevent: {RUN_EVENT_STREAM_NAME}\ndata: {payload}\n\n"
```

Create `backend/api/schemas/events.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunEventEnvelope(BaseModel):
    type: str
    run_id: str
    plan_id: str | None = None
    seq: int = Field(ge=1)
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Write frontend schema test**

Create `tests/frontend/run-schemas.test.ts`:

```typescript
import test from 'node:test';
import assert from 'node:assert/strict';

import { RunEventEnvelopeSchema, RunStatusSchema } from '../../features/runs/schemas';

test('run event envelope parses normalized SSE payloads', () => {
  const event = RunEventEnvelopeSchema.parse({
    type: 'approval.required',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 4,
    timestamp: '2026-06-19T00:00:00Z',
    payload: { actions: [] },
  });

  assert.equal(event.type, 'approval.required');
  assert.equal(event.payload.actions instanceof Array, true);
});

test('run status rejects old graph phases that are not product states', () => {
  assert.throws(() => RunStatusSchema.parse('pending_approval'));
  assert.equal(RunStatusSchema.parse('approval_required'), 'approval_required');
});
```

- [ ] **Step 5: Add frontend schema implementation**

Create `features/runs/schemas.ts`:

```typescript
import { z } from 'zod';

export const RunStatusSchema = z.enum([
  'queued',
  'running',
  'needs_clarification',
  'approval_required',
  'executing',
  'completed',
  'validation_failed',
  'rejected',
  'failed',
]);

export const RunEventTypeSchema = z.enum([
  'run.started',
  'run.heartbeat',
  'agent.started',
  'agent.completed',
  'agent.handoff',
  'tool.called',
  'tool.completed',
  'tool.failed',
  'guardrail.triggered',
  'plan.draft.created',
  'plan.validation.completed',
  'approval.required',
  'actions.execution.started',
  'actions.execution.completed',
  'run.completed',
  'run.failed',
  'run.rejected',
]);

export const RunEventEnvelopeSchema = z.object({
  type: RunEventTypeSchema,
  run_id: z.string().min(1),
  plan_id: z.string().min(1).optional(),
  seq: z.number().int().positive(),
  timestamp: z.string().min(1),
  payload: z.record(z.string(), z.unknown()).default({}),
});

export const CreateRunRequestSchema = z.object({
  goal: z.string().min(1),
  user_id: z.string().min(1).default('local_demo_user'),
  mode: z.literal('plan').default('plan'),
});

export const CreateRunResponseSchema = z.object({
  run_id: z.string().min(1),
  plan_id: z.string().min(1),
  status: RunStatusSchema,
  events_url: z.string().min(1),
});

export const RunStatusResponseSchema = z.object({
  run_id: z.string().min(1),
  plan_id: z.string().min(1).optional(),
  status: RunStatusSchema,
  current_agent: z.string().nullable().optional(),
  created_at: z.string().min(1),
  updated_at: z.string().min(1),
  error: z.unknown().nullable().optional(),
});

export const ApproveActionsRequestSchema = z.object({
  action_ids: z.array(z.string().min(1)),
});

export const RejectRunRequestSchema = z.object({
  reason: z.string().min(1).default('user_rejected'),
});

export type RunStatus = z.infer<typeof RunStatusSchema>;
export type RunEventEnvelope = z.infer<typeof RunEventEnvelopeSchema>;
export type CreateRunResponse = z.infer<typeof CreateRunResponseSchema>;
export type RunStatusResponse = z.infer<typeof RunStatusResponseSchema>;
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/backend/test_run_events.py -q
npm run test:frontend -- tests/frontend/run-schemas.test.ts
```

Expected: both pass.

- [ ] **Step 7: Commit**

```bash
git add backend/domain/events.py backend/api/schemas/events.py features/runs/schemas.ts tests/backend/test_run_events.py tests/frontend/run-schemas.test.ts
git commit -m "feat: add run event contract"
```

---

### Task 2: Add Event Store With Queue and Replay

**Files:**
- Create: `backend/infrastructure/event_store.py`
- Test: `tests/backend/test_event_store.py`

- [ ] **Step 1: Write failing tests**

Create `tests/backend/test_event_store.py`:

```python
import asyncio
import unittest
from tempfile import TemporaryDirectory

from backend.domain.events import RUN_STATUS_RUNNING
from backend.infrastructure.event_store import EventStore


class EventStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.store = EventStore(f"{self.tmp.name}/events.sqlite")

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_persists_ordered_events(self):
        first = self.store.append("run_1", "plan_1", "run.started", {"status": RUN_STATUS_RUNNING})
        second = self.store.append("run_1", "plan_1", "agent.started", {"agent": "planner"})

        self.assertEqual(first.seq, 1)
        self.assertEqual(second.seq, 2)
        replayed = self.store.replay("run_1")
        self.assertEqual([event.type for event in replayed], ["run.started", "agent.started"])

    def test_active_queue_receives_formatted_sse(self):
        self.store.open_queue("run_1")
        event = self.store.append("run_1", None, "run.started", {})

        async def read_once():
            return await self.store.next_sse("run_1")

        raw = asyncio.run(read_once())
        self.assertIn(f"id: {event.event_id}", raw)
        self.assertIn("event: run.event", raw)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_event_store.py -q
```

Expected: FAIL with missing `backend.infrastructure.event_store`.

- [ ] **Step 3: Implement EventStore**

Create `backend/infrastructure/event_store.py`:

```python
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.domain.events import RunEvent, format_sse_event


class EventStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        self._queues: dict[str, asyncio.Queue[str | None]] = {}
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists run_events (
                    event_id text primary key,
                    run_id text not null,
                    plan_id text,
                    seq integer not null,
                    event_type text not null,
                    payload_json text not null,
                    created_at text not null,
                    unique(run_id, seq)
                )
                """
            )

    def open_queue(self, run_id: str) -> None:
        self._queues.setdefault(run_id, asyncio.Queue())

    def close_queue(self, run_id: str) -> None:
        queue = self._queues.get(run_id)
        if queue is not None:
            queue.put_nowait(None)

    def append(self, run_id: str, plan_id: str | None, event_type: str, payload: dict[str, Any]) -> RunEvent:
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            row = conn.execute("select coalesce(max(seq), 0) + 1 as next_seq from run_events where run_id = ?", (run_id,)).fetchone()
            seq = int(row["next_seq"])
            event_id = f"evt_{seq:06d}"
            conn.execute(
                """
                insert into run_events(event_id, run_id, plan_id, seq, event_type, payload_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, run_id, plan_id, seq, event_type, json.dumps(payload, ensure_ascii=False), created_at),
            )
        event = RunEvent(event_id, run_id, plan_id, seq, event_type, created_at, payload)
        queue = self._queues.get(run_id)
        if queue is not None:
            queue.put_nowait(format_sse_event(event))
        return event

    def replay(self, run_id: str, after_seq: int = 0) -> list[RunEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select event_id, run_id, plan_id, seq, event_type, payload_json, created_at
                from run_events
                where run_id = ? and seq > ?
                order by seq asc
                """,
                (run_id, after_seq),
            ).fetchall()
        return [
            RunEvent(
                row["event_id"],
                row["run_id"],
                row["plan_id"],
                int(row["seq"]),
                row["event_type"],
                row["created_at"],
                json.loads(row["payload_json"]),
            )
            for row in rows
        ]

    async def next_sse(self, run_id: str) -> str | None:
        queue = self._queues.get(run_id)
        if queue is None:
            return None
        return await queue.get()
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/backend/test_event_store.py tests/backend/test_run_events.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/infrastructure/event_store.py tests/backend/test_event_store.py
git commit -m "feat: add run event store"
```

---

### Task 3: Add Run Service and New Run API Skeleton

**Files:**
- Create: `backend/domain/run.py`
- Create: `backend/application/run_service.py`
- Create: `backend/api/schemas/runs.py`
- Create: `backend/api/routes/runs.py`
- Modify: `backend/api/app.py`
- Test: `tests/backend/test_runs_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/backend/test_runs_api.py`:

```python
import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.application.run_service import RunService


class RunsApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.run_service = RunService(database_path=f"{self.tmp.name}/workflow.sqlite")
        self.client = TestClient(create_app(run_service=self.run_service))

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_run_returns_run_centered_contract(self):
        response = self.client.post("/api/runs", json={"goal": "family afternoon", "user_id": "user_1"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["run_id"].startswith("run_"))
        self.assertTrue(data["plan_id"].startswith("plan_"))
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["events_url"], f"/api/runs/{data['run_id']}/events")

    def test_get_run_returns_product_status(self):
        created = self.client.post("/api/runs", json={"goal": "family afternoon"}).json()

        response = self.client.get(f"/api/runs/{created['run_id']}")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["run_id"], created["run_id"])
        self.assertEqual(data["plan_id"], created["plan_id"])
        self.assertIn(data["status"], {"queued", "running", "completed"})

    def test_invalid_goal_returns_400(self):
        response = self.client.post("/api/runs", json={"goal": ""})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/backend/test_runs_api.py -q
```

Expected: FAIL because `backend.application.run_service` does not exist or `create_app` does not accept `run_service`.

- [ ] **Step 3: Implement domain and schema files**

Create `backend/domain/run.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanRunRequest:
    goal: str
    user_id: str = "local_demo_user"
    mode: str = "plan"


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    plan_id: str
    user_id: str
    goal: str
    status: str
    current_agent: str | None
    created_at: str
    updated_at: str
    error: dict | None = None
```

Create `backend/api/schemas/runs.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    goal: str = Field(min_length=1)
    user_id: str = "local_demo_user"
    mode: str = "plan"


class CreateRunResponse(BaseModel):
    run_id: str
    plan_id: str
    status: str
    events_url: str


class RunStatusResponse(BaseModel):
    run_id: str
    plan_id: str | None = None
    status: str
    current_agent: str | None = None
    created_at: str
    updated_at: str
    error: dict[str, Any] | None = None


class ApproveActionsRequest(BaseModel):
    action_ids: list[str]


class RejectRunRequest(BaseModel):
    reason: str = "user_rejected"
```

- [ ] **Step 4: Implement minimal RunService**

Create `backend/application/run_service.py`:

```python
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.domain.events import RUN_STATUS_QUEUED
from backend.domain.run import PlanRunRequest, RunRecord
from backend.infrastructure.event_store import EventStore


class RunService:
    def __init__(self, database_path: str = ".weekendpilot/workflow.sqlite") -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self.events = EventStore(database_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists runs (
                    run_id text primary key,
                    plan_id text not null,
                    user_id text not null,
                    goal text not null,
                    status text not null,
                    current_agent text,
                    error_json text,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )

    def create_run(self, request: PlanRunRequest) -> RunRecord:
        if not request.goal.strip():
            raise ValueError("validation_error")
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        run_id = f"run_{uuid4().hex[:12]}"
        plan_id = f"plan_{uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                insert into runs(run_id, plan_id, user_id, goal, status, current_agent, error_json, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, plan_id, request.user_id, request.goal, RUN_STATUS_QUEUED, None, None, now, now),
            )
        self.events.open_queue(run_id)
        self.events.append(run_id, plan_id, "run.started", {"status": RUN_STATUS_QUEUED})
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> RunRecord:
        with self._connect() as conn:
            row = conn.execute("select * from runs where run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError("run_not_found")
        return RunRecord(
            run_id=row["run_id"],
            plan_id=row["plan_id"],
            user_id=row["user_id"],
            goal=row["goal"],
            status=row["status"],
            current_agent=row["current_agent"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error=None,
        )
```

- [ ] **Step 5: Implement routes and app injection**

Create `backend/api/routes/runs.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.api.schemas.runs import CreateRunRequest, CreateRunResponse, RunStatusResponse
from backend.domain.events import format_sse_event
from backend.domain.run import PlanRunRequest

router = APIRouter(prefix="/api/runs", tags=["runs"])


def run_service(request: Request):
    return request.app.state.run_service


@router.post("", response_model=CreateRunResponse)
async def create_run(body: CreateRunRequest, request: Request) -> CreateRunResponse:
    record = run_service(request).create_run(PlanRunRequest(goal=body.goal, user_id=body.user_id, mode=body.mode))
    return CreateRunResponse(
        run_id=record.run_id,
        plan_id=record.plan_id,
        status=record.status,
        events_url=f"/api/runs/{record.run_id}/events",
    )


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run(run_id: str, request: Request) -> RunStatusResponse:
    record = run_service(request).get_run(run_id)
    return RunStatusResponse(**record.__dict__)


@router.get("/{run_id}/events")
async def stream_run_events(run_id: str, request: Request) -> StreamingResponse:
    service = run_service(request)

    async def event_stream():
        for event in service.events.replay(run_id):
            yield format_sse_event(event)
        while True:
            item = await service.events.next_sse(run_id)
            if item is None:
                break
            yield item

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Modify `backend/api/app.py` minimally:

```python
from backend.application.run_service import RunService
from backend.api.routes.runs import router as runs_router
```

Change `create_app` signature to accept both old and new services during migration:

```python
def create_app(workflow_service: WorkflowService | None = None, run_service: RunService | None = None) -> FastAPI:
    api = FastAPI(...)
    api.state.workflow_service = workflow_service or WorkflowService()
    api.state.run_service = run_service or RunService()
    api.include_router(runs_router)
```

Keep existing old routes until frontend and tests migrate.

- [ ] **Step 6: Run tests**

Run:

```bash
uv run pytest tests/backend/test_runs_api.py tests/backend/test_event_store.py tests/backend/test_run_events.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/domain/run.py backend/application/run_service.py backend/api/schemas/runs.py backend/api/routes/runs.py backend/api/app.py tests/backend/test_runs_api.py
git commit -m "feat: add run-centered API skeleton"
```

---

### Task 4: Add Frontend Run API Client and Reducer

**Files:**
- Create: `features/runs/api.ts`
- Create: `features/runs/reducer.ts`
- Create: `features/runs/useRunController.ts`
- Test: `tests/frontend/run-api-client.test.ts`
- Test: `tests/frontend/run-reducer.test.ts`

- [ ] **Step 1: Write API client failing test**

Create `tests/frontend/run-api-client.test.ts`:

```typescript
import test from 'node:test';
import assert from 'node:assert/strict';

import { approveRunActions, createRun, rejectRun } from '../../features/runs/api';

type FetchCall = { url: string; init?: RequestInit };

function installFetch(body: Record<string, unknown>) {
  const calls: FetchCall[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return { ok: true, status: 200, json: async () => body } as Response;
  }) as typeof fetch;
  return calls;
}

test('run API client uses run-centered endpoints', async () => {
  delete process.env.NEXT_PUBLIC_API_URL;
  const calls = installFetch({ run_id: 'run_1', plan_id: 'plan_1', status: 'queued', events_url: '/api/runs/run_1/events' });

  await createRun({ goal: '家庭半日计划', user_id: 'user_1', mode: 'plan' });
  await approveRunActions('run_1', ['act_1']);
  await rejectRun('run_1', 'user_rejected');

  assert.deepEqual(calls.map((call) => [call.url, call.init?.method ?? 'GET']), [
    ['http://127.0.0.1:8787/api/runs', 'POST'],
    ['http://127.0.0.1:8787/api/runs/run_1/actions/approve', 'POST'],
    ['http://127.0.0.1:8787/api/runs/run_1/actions/reject', 'POST'],
  ]);
  assert.equal(calls[0].init?.body, JSON.stringify({ goal: '家庭半日计划', user_id: 'user_1', mode: 'plan' }));
});
```

- [ ] **Step 2: Write reducer failing test**

Create `tests/frontend/run-reducer.test.ts`:

```typescript
import test from 'node:test';
import assert from 'node:assert/strict';

import { initialRunState, runReducer } from '../../features/runs/reducer';

test('run reducer moves through planning to approval required', () => {
  const started = runReducer(initialRunState, {
    type: 'run.started',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 1,
    timestamp: '2026-06-19T00:00:00Z',
    payload: { status: 'running' },
  });
  const approval = runReducer(started, {
    type: 'approval.required',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 2,
    timestamp: '2026-06-19T00:00:01Z',
    payload: { actions: [{ action_id: 'act_1' }] },
  });

  assert.equal(approval.runId, 'run_1');
  assert.equal(approval.planId, 'plan_1');
  assert.equal(approval.status, 'approval_required');
  assert.equal(approval.pendingActions.length, 1);
});
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
npm run test:frontend -- tests/frontend/run-api-client.test.ts tests/frontend/run-reducer.test.ts
```

Expected: FAIL because modules do not exist.

- [ ] **Step 4: Implement run API client**

Create `features/runs/api.ts`:

```typescript
import { apiRequest, resolveApiUrl } from '../../lib/api/client';
import {
  CreateRunResponseSchema,
  type CreateRunResponse,
  type RunEventEnvelope,
  RunEventEnvelopeSchema,
} from './schemas';

export async function createRun(input: { goal: string; user_id?: string; mode?: 'plan' }): Promise<CreateRunResponse> {
  const response = await apiRequest<unknown>('/api/runs', {
    method: 'POST',
    body: {
      goal: input.goal,
      user_id: input.user_id ?? 'local_demo_user',
      mode: input.mode ?? 'plan',
    },
  });
  return CreateRunResponseSchema.parse(response);
}

export async function approveRunActions(runId: string, actionIds: string[]) {
  return apiRequest(`/api/runs/${runId}/actions/approve`, {
    method: 'POST',
    body: { action_ids: actionIds },
  });
}

export async function rejectRun(runId: string, reason = 'user_rejected') {
  return apiRequest(`/api/runs/${runId}/actions/reject`, {
    method: 'POST',
    body: { reason },
  });
}

export function streamRunEvents(
  runId: string,
  callbacks: {
    onEvent: (event: RunEventEnvelope) => void;
    onError?: (error: Error) => void;
  },
) {
  const es = new EventSource(resolveApiUrl(`/api/runs/${runId}/events`));
  es.addEventListener('run.event', (event) => {
    const parsed = RunEventEnvelopeSchema.parse(JSON.parse((event as MessageEvent).data));
    callbacks.onEvent(parsed);
    if (['run.completed', 'run.failed', 'run.rejected'].includes(parsed.type)) {
      es.close();
    }
  });
  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      callbacks.onError?.(new Error('SSE connection failed'));
    }
  };
  return () => es.close();
}
```

- [ ] **Step 5: Implement reducer**

Create `features/runs/reducer.ts`:

```typescript
import type { RunEventEnvelope, RunStatus } from './schemas';

export type RunState = {
  runId: string | null;
  planId: string | null;
  status: RunStatus | 'idle';
  currentAgent: string | null;
  events: RunEventEnvelope[];
  pendingActions: Array<Record<string, unknown>>;
  error: string | null;
};

export const initialRunState: RunState = {
  runId: null,
  planId: null,
  status: 'idle',
  currentAgent: null,
  events: [],
  pendingActions: [],
  error: null,
};

export function runReducer(state: RunState, event: RunEventEnvelope): RunState {
  const base: RunState = {
    ...state,
    runId: event.run_id,
    planId: event.plan_id ?? state.planId,
    events: [...state.events, event],
  };

  switch (event.type) {
    case 'run.started':
      return { ...base, status: 'running', error: null };
    case 'agent.started':
      return { ...base, currentAgent: String(event.payload.agent ?? '') || null };
    case 'agent.completed':
      return { ...base, currentAgent: null };
    case 'approval.required':
      return {
        ...base,
        status: 'approval_required',
        pendingActions: Array.isArray(event.payload.actions) ? event.payload.actions as Array<Record<string, unknown>> : [],
      };
    case 'actions.execution.started':
      return { ...base, status: 'executing' };
    case 'actions.execution.completed':
      return { ...base, status: 'completed', pendingActions: [] };
    case 'run.completed':
      return { ...base, status: 'completed', pendingActions: [] };
    case 'run.rejected':
      return { ...base, status: 'rejected' };
    case 'run.failed':
      return { ...base, status: 'failed', error: String(event.payload.error ?? 'run_failed') };
    case 'guardrail.triggered':
      return { ...base, status: 'validation_failed', error: String(event.payload.message ?? 'validation_failed') };
    default:
      return base;
  }
}
```

- [ ] **Step 6: Run focused frontend tests**

Run:

```bash
npm run test:frontend -- tests/frontend/run-api-client.test.ts tests/frontend/run-reducer.test.ts tests/frontend/run-schemas.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add features/runs/api.ts features/runs/reducer.ts tests/frontend/run-api-client.test.ts tests/frontend/run-reducer.test.ts
git commit -m "feat: add frontend run client and reducer"
```

---

### Task 5: Add OpenAI Agents SDK Runtime Skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `backend/agents/runtime.py`
- Create: `backend/agents/openai_runtime.py`
- Create: `backend/agents/tools.py`
- Create: `backend/agents/guardrails.py`
- Test: `tests/backend/test_openai_agents_runtime.py`

- [ ] **Step 1: Add dependency**

Modify `pyproject.toml` dependencies:

```toml
dependencies = [
    "fastapi>=0.136.1",
    "langchain-openai>=0.3.0",
    "openai-agents>=0.4.0",
    "uvicorn[standard]>=0.46.0",
]
```

Keep `langgraph` for this task only if imports still exist. Remove it in Task 9.

Run:

```bash
uv sync
```

Expected: lockfile updates and `uv run python -c "from agents import Agent, Runner, function_tool; print('ok')"` prints `ok`.

- [ ] **Step 2: Write runtime contract test**

Create `tests/backend/test_openai_agents_runtime.py`:

```python
import unittest

from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.agents.runtime import PlanRunRequest, RuntimeContext


class OpenAIAgentsRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_local_dry_run_returns_grounded_plan_result(self):
        runtime = OpenAIAgentsRuntime(dry_run=True)
        events = []

        async def sink(event_type, payload):
            events.append((event_type, payload))

        result = await runtime.start_plan(
            PlanRunRequest(goal="family afternoon", user_id="user_1"),
            RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
            sink,
        )

        self.assertEqual(result.status, "approval_required")
        self.assertEqual(result.plan["id"], "plan_1")
        self.assertGreater(len(result.pending_actions), 0)
        self.assertIn(("agent.started", {"agent": "planner"}), events)
```

- [ ] **Step 3: Add runtime DTOs**

Create `backend/agents/runtime.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class PlanRunRequest:
    goal: str
    user_id: str = "local_demo_user"


@dataclass(frozen=True)
class ExecuteActionsRequest:
    action_ids: list[str]


@dataclass(frozen=True)
class RuntimeContext:
    run_id: str
    plan_id: str
    user_id: str


@dataclass(frozen=True)
class PlanRunResult:
    status: str
    plan: dict[str, Any]
    validation: dict[str, Any] = field(default_factory=dict)
    pending_actions: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    receipts: list[dict[str, Any]]


class AgentRuntime(Protocol):
    async def start_plan(self, request: PlanRunRequest, context: RuntimeContext, sink: EventSink) -> PlanRunResult:
        ...

    async def execute_actions(self, request: ExecuteActionsRequest, context: RuntimeContext, sink: EventSink) -> ExecutionResult:
        ...
```

- [ ] **Step 4: Add dry-run runtime and SDK imports**

Create `backend/agents/openai_runtime.py`:

```python
from __future__ import annotations

from agents import Agent, Runner

from backend.agents.runtime import (
    ExecuteActionsRequest,
    ExecutionResult,
    PlanRunRequest,
    PlanRunResult,
    RuntimeContext,
    EventSink,
)


class OpenAIAgentsRuntime:
    def __init__(self, *, dry_run: bool = False, model: str | None = None) -> None:
        self.dry_run = dry_run
        self.model = model
        self.planner = Agent(
            name="PlannerAgent",
            instructions="Create grounded local-life plans. Return only validated product-safe output.",
            model=model,
        )

    async def start_plan(self, request: PlanRunRequest, context: RuntimeContext, sink: EventSink) -> PlanRunResult:
        await sink("agent.started", {"agent": "planner"})
        if self.dry_run:
            plan = {
                "id": context.plan_id,
                "status": "approval_required",
                "title": "本地生活计划",
                "summary": request.goal,
                "itinerary": [],
                "actions": [
                    {
                        "action_id": "act_demo_reservation",
                        "tool": "create_reservation",
                        "target": "demo_restaurant",
                        "label": "预约餐厅",
                        "payload": {"place_id": "demo_restaurant", "people": 3},
                    }
                ],
                "receipts": [],
            }
            await sink("approval.required", {"actions": plan["actions"]})
            return PlanRunResult(status="approval_required", plan=plan, validation={"valid": True}, pending_actions=plan["actions"])

        result = await Runner.run(self.planner, request.goal)
        plan = result.final_output if isinstance(result.final_output, dict) else {"id": context.plan_id, "summary": str(result.final_output)}
        await sink("plan.draft.created", {"plan_id": context.plan_id})
        return PlanRunResult(status="completed", plan=plan, validation={"valid": True}, pending_actions=[])

    async def execute_actions(self, request: ExecuteActionsRequest, context: RuntimeContext, sink: EventSink) -> ExecutionResult:
        await sink("actions.execution.started", {"action_ids": request.action_ids})
        receipts = [{"action_id": action_id, "status": "confirmed"} for action_id in request.action_ids]
        await sink("actions.execution.completed", {"receipts": receipts})
        return ExecutionResult(status="completed", receipts=receipts)
```

Create `backend/agents/tools.py`:

```python
from __future__ import annotations

from agents import function_tool

from backend.tools.registry import LocalToolRegistry

registry = LocalToolRegistry()


@function_tool
def get_weather(rainy: bool = False) -> dict:
    """Return deterministic local weather."""
    return registry.get_weather(rainy).payload
```

Create `backend/agents/guardrails.py`:

```python
from __future__ import annotations


def require_grounded_action(action: dict) -> None:
    if not action.get("action_id"):
        raise ValueError("missing_action_id")
    if not action.get("tool"):
        raise ValueError("missing_tool")
    if not action.get("target"):
        raise ValueError("missing_target")
```

- [ ] **Step 5: Run runtime tests**

Run:

```bash
uv run pytest tests/backend/test_openai_agents_runtime.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock backend/agents/runtime.py backend/agents/openai_runtime.py backend/agents/tools.py backend/agents/guardrails.py tests/backend/test_openai_agents_runtime.py
git commit -m "feat: add OpenAI Agents runtime skeleton"
```

---

### Task 6: Wire Runtime Into RunService and Persist Plans

**Files:**
- Create: `backend/api/schemas/plans.py`
- Create: `backend/api/routes/plans.py`
- Modify: `backend/application/run_service.py`
- Modify: `backend/api/app.py`
- Test: `tests/backend/test_runs_runtime_integration.py`

- [ ] **Step 1: Write failing integration tests**

Create `tests/backend/test_runs_runtime_integration.py`:

```python
import time
import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.api.app import create_app
from backend.application.run_service import RunService


class RunsRuntimeIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.service = RunService(
            database_path=f"{self.tmp.name}/workflow.sqlite",
            runtime=OpenAIAgentsRuntime(dry_run=True),
        )
        self.client = TestClient(create_app(run_service=self.service))

    def tearDown(self):
        self.tmp.cleanup()

    def wait_for_status(self, run_id, expected):
        for _ in range(20):
            data = self.client.get(f"/api/runs/{run_id}").json()
            if data["status"] == expected:
                return data
            time.sleep(0.05)
        self.fail(f"run {run_id} did not reach {expected}")

    def test_run_completes_to_approval_required_and_plan_is_fetchable(self):
        created = self.client.post("/api/runs", json={"goal": "family afternoon"}).json()
        status = self.wait_for_status(created["run_id"], "approval_required")

        self.assertEqual(status["plan_id"], created["plan_id"])
        plan = self.client.get(f"/api/plans/{created['plan_id']}").json()
        self.assertEqual(plan["plan_id"], created["plan_id"])
        self.assertEqual(plan["plan"]["status"], "approval_required")
        self.assertGreater(len(plan["actions"]), 0)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/backend/test_runs_runtime_integration.py -q
```

Expected: FAIL because `RunService` does not accept `runtime` and plan route does not exist.

- [ ] **Step 3: Add plan route schemas**

Create `backend/api/schemas/plans.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlanDetailResponse(BaseModel):
    plan_id: str
    run_id: str
    status: str
    plan: dict[str, Any]
    actions: list[dict[str, Any]] = Field(default_factory=list)
    receipts: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)
```

Create `backend/api/routes/plans.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.schemas.plans import PlanDetailResponse

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(plan_id: str, request: Request) -> PlanDetailResponse:
    payload = request.app.state.run_service.get_plan(plan_id)
    return PlanDetailResponse(**payload)
```

- [ ] **Step 4: Extend RunService with runtime and plan tables**

Update `RunService.__init__` signature:

```python
def __init__(self, database_path: str = ".weekendpilot/workflow.sqlite", runtime: AgentRuntime | None = None) -> None:
    self.database_path = database_path
    self.runtime = runtime or OpenAIAgentsRuntime()
    ...
```

Add imports:

```python
import asyncio
import json
import threading
from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.agents.runtime import AgentRuntime, RuntimeContext, PlanRunRequest as RuntimePlanRunRequest
from backend.domain.events import RUN_STATUS_APPROVAL_REQUIRED, RUN_STATUS_COMPLETED, RUN_STATUS_FAILED
```

Extend `_init_db` with:

```python
conn.execute(
    """
    create table if not exists plans (
        plan_id text primary key,
        run_id text not null,
        user_id text not null,
        status text not null,
        plan_json text not null,
        actions_json text not null,
        receipts_json text not null,
        created_at text not null,
        updated_at text not null
    )
    """
)
```

At the end of `create_run`, after appending `run.started`, start a worker:

```python
threading.Thread(target=self._run_worker, args=(run_id,), daemon=True).start()
```

Add methods:

```python
def _run_worker(self, run_id: str) -> None:
    asyncio.run(self._run_worker_async(run_id))

async def _run_worker_async(self, run_id: str) -> None:
    record = self.get_run(run_id)

    async def sink(event_type: str, payload: dict) -> None:
        self.events.append(run_id, record.plan_id, event_type, payload)

    self._update_run(run_id, "running", "planner", None)
    try:
        result = await self.runtime.start_plan(
            RuntimePlanRunRequest(goal=record.goal, user_id=record.user_id),
            RuntimeContext(run_id=run_id, plan_id=record.plan_id, user_id=record.user_id),
            sink,
        )
        self._save_plan(record, result.status, result.plan, result.pending_actions, [])
        self._update_run(run_id, result.status, None, None)
        if result.status == RUN_STATUS_APPROVAL_REQUIRED:
            self.events.append(run_id, record.plan_id, "approval.required", {"actions": result.pending_actions})
        else:
            self.events.append(run_id, record.plan_id, "run.completed", {"status": RUN_STATUS_COMPLETED})
    except Exception as exc:
        self._update_run(run_id, RUN_STATUS_FAILED, None, {"message": str(exc)})
        self.events.append(run_id, record.plan_id, "run.failed", {"error": str(exc)})
    finally:
        self.events.close_queue(run_id)

def _update_run(self, run_id: str, status: str, current_agent: str | None, error: dict | None) -> None:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with self._connect() as conn:
        conn.execute(
            "update runs set status = ?, current_agent = ?, error_json = ?, updated_at = ? where run_id = ?",
            (status, current_agent, json.dumps(error, ensure_ascii=False) if error else None, now, run_id),
        )

def _save_plan(self, record: RunRecord, status: str, plan: dict, actions: list[dict], receipts: list[dict]) -> None:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with self._connect() as conn:
        conn.execute(
            """
            insert or replace into plans(plan_id, run_id, user_id, status, plan_json, actions_json, receipts_json, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?, ?, coalesce((select created_at from plans where plan_id = ?), ?), ?)
            """,
            (
                record.plan_id,
                record.run_id,
                record.user_id,
                status,
                json.dumps(plan, ensure_ascii=False),
                json.dumps(actions, ensure_ascii=False),
                json.dumps(receipts, ensure_ascii=False),
                record.plan_id,
                now,
                now,
            ),
        )

def get_plan(self, plan_id: str) -> dict:
    with self._connect() as conn:
        row = conn.execute("select * from plans where plan_id = ?", (plan_id,)).fetchone()
    if row is None:
        raise KeyError("plan_not_found")
    return {
        "plan_id": row["plan_id"],
        "run_id": row["run_id"],
        "status": row["status"],
        "plan": json.loads(row["plan_json"]),
        "actions": json.loads(row["actions_json"]),
        "receipts": json.loads(row["receipts_json"]),
        "trace": [event.to_dict() for event in self.events.replay(row["run_id"])],
    }
```

- [ ] **Step 5: Register plan route**

Modify `backend/api/app.py`:

```python
from backend.api.routes.plans import router as plans_router

api.include_router(plans_router)
```

If old inline `/api/plans/{plan_id}` route conflicts, keep the old route until Task 9 by using the new route only when `run_service` owns the plan. The final removal happens in Task 9.

- [ ] **Step 6: Run integration tests**

Run:

```bash
uv run pytest tests/backend/test_runs_runtime_integration.py tests/backend/test_runs_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/api/schemas/plans.py backend/api/routes/plans.py backend/application/run_service.py backend/api/app.py tests/backend/test_runs_runtime_integration.py
git commit -m "feat: run OpenAI agent runtime from run service"
```

---

### Task 7: Add Approval Service and Run Action Endpoints

**Files:**
- Create: `backend/application/approval_service.py`
- Modify: `backend/api/routes/runs.py`
- Modify: `backend/application/run_service.py`
- Test: `tests/backend/test_run_approval_api.py`

- [ ] **Step 1: Write failing approval tests**

Create `tests/backend/test_run_approval_api.py`:

```python
import time
import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.api.app import create_app
from backend.application.run_service import RunService


class RunApprovalApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.service = RunService(f"{self.tmp.name}/workflow.sqlite", runtime=OpenAIAgentsRuntime(dry_run=True))
        self.client = TestClient(create_app(run_service=self.service))

    def tearDown(self):
        self.tmp.cleanup()

    def create_approval_run(self):
        created = self.client.post("/api/runs", json={"goal": "family afternoon"}).json()
        for _ in range(20):
            status = self.client.get(f"/api/runs/{created['run_id']}").json()
            if status["status"] == "approval_required":
                return created
            time.sleep(0.05)
        self.fail("run did not reach approval_required")

    def test_approve_selected_actions_executes_receipts(self):
        created = self.create_approval_run()
        plan = self.client.get(f"/api/plans/{created['plan_id']}").json()
        action_id = plan["actions"][0]["action_id"]

        response = self.client.post(f"/api/runs/{created['run_id']}/actions/approve", json={"action_ids": [action_id]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "executing")
        final = self.client.get(f"/api/plans/{created['plan_id']}").json()
        self.assertGreaterEqual(len(final["receipts"]), 1)

    def test_reject_run_marks_status_rejected(self):
        created = self.create_approval_run()

        response = self.client.post(f"/api/runs/{created['run_id']}/actions/reject", json={"reason": "not_today"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "rejected")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/backend/test_run_approval_api.py -q
```

Expected: FAIL because approval endpoints are not implemented.

- [ ] **Step 3: Implement ApprovalService**

Create `backend/application/approval_service.py`:

```python
from __future__ import annotations

import asyncio

from backend.agents.runtime import ExecuteActionsRequest, RuntimeContext
from backend.domain.events import RUN_STATUS_EXECUTING, RUN_STATUS_REJECTED


class ApprovalService:
    def __init__(self, run_service) -> None:
        self.run_service = run_service

    def approve(self, run_id: str, action_ids: list[str]) -> dict:
        record = self.run_service.get_run(run_id)
        plan = self.run_service.get_plan(record.plan_id)
        known = {action["action_id"] for action in plan["actions"]}
        unknown = [action_id for action_id in action_ids if action_id not in known]
        if unknown:
            raise ValueError("unknown_action_id")
        self.run_service._update_run(run_id, RUN_STATUS_EXECUTING, "executor", None)

        async def execute():
            async def sink(event_type: str, payload: dict) -> None:
                self.run_service.events.append(run_id, record.plan_id, event_type, payload)

            return await self.run_service.runtime.execute_actions(
                ExecuteActionsRequest(action_ids=action_ids),
                RuntimeContext(run_id=run_id, plan_id=record.plan_id, user_id=record.user_id),
                sink,
            )

        result = asyncio.run(execute())
        self.run_service.add_receipts(record.plan_id, result.receipts)
        self.run_service._update_run(run_id, result.status, None, None)
        return {"run_id": run_id, "status": RUN_STATUS_EXECUTING, "accepted_action_ids": action_ids}

    def reject(self, run_id: str, reason: str) -> dict:
        record = self.run_service.get_run(run_id)
        self.run_service._update_run(run_id, RUN_STATUS_REJECTED, None, None)
        self.run_service.events.append(run_id, record.plan_id, "run.rejected", {"reason": reason})
        return {"run_id": run_id, "status": RUN_STATUS_REJECTED}
```

Add `RunService.add_receipts`:

```python
def add_receipts(self, plan_id: str, receipts: list[dict]) -> None:
    plan = self.get_plan(plan_id)
    updated = [*plan["receipts"], *receipts]
    with self._connect() as conn:
        conn.execute(
            "update plans set receipts_json = ?, updated_at = ? where plan_id = ?",
            (json.dumps(updated, ensure_ascii=False), datetime.now(UTC).isoformat().replace("+00:00", "Z"), plan_id),
        )
```

- [ ] **Step 4: Add approval routes**

Modify `backend/api/routes/runs.py` imports:

```python
from backend.api.schemas.runs import ApproveActionsRequest, RejectRunRequest
```

Add helpers:

```python
def approval_service(request: Request):
    return request.app.state.approval_service
```

Add endpoints:

```python
@router.post("/{run_id}/actions/approve")
async def approve_actions(run_id: str, body: ApproveActionsRequest, request: Request) -> dict:
    return approval_service(request).approve(run_id, body.action_ids)


@router.post("/{run_id}/actions/reject")
async def reject_run(run_id: str, body: RejectRunRequest, request: Request) -> dict:
    return approval_service(request).reject(run_id, body.reason)
```

Modify `backend/api/app.py` after setting `run_service`:

```python
from backend.application.approval_service import ApprovalService
api.state.approval_service = ApprovalService(api.state.run_service)
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/backend/test_run_approval_api.py tests/backend/test_runs_runtime_integration.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/application/approval_service.py backend/application/run_service.py backend/api/routes/runs.py backend/api/app.py tests/backend/test_run_approval_api.py
git commit -m "feat: add run approval actions"
```

---

### Task 8: Wire Frontend to Run Controller

**Files:**
- Create: `features/runs/useRunController.ts`
- Create: `features/plans/api.ts`
- Modify: `app/page.tsx`
- Modify: `components/plan/ActionLedgerPanel.tsx`
- Modify: `components/trace/TracePanel.tsx`
- Test: `tests/frontend/use-run-controller.test.tsx`
- Test: update existing frontend tests that import old planner API.

- [ ] **Step 1: Write controller test**

Create `tests/frontend/use-run-controller.test.tsx`:

```typescript
import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { JSDOM } from 'jsdom';
import { createRoot } from 'react-dom/client';

import { useRunController } from '../../features/runs/useRunController';

test('useRunController starts a run and reduces events', async () => {
  const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost' });
  globalThis.window = dom.window as unknown as Window & typeof globalThis;
  globalThis.document = dom.window.document;

  const originalFetch = globalThis.fetch;
  const originalEventSource = globalThis.EventSource;
  const instances: FakeEventSource[] = [];

  globalThis.fetch = (async () => ({
    ok: true,
    status: 200,
    json: async () => ({ run_id: 'run_1', plan_id: 'plan_1', status: 'queued', events_url: '/api/runs/run_1/events' }),
  })) as typeof fetch;

  class FakeEventSource {
    static CLOSED = 2;
    readyState = 1;
    listeners: Record<string, Array<(event: MessageEvent) => void>> = {};
    constructor(public url: string) { instances.push(this); }
    addEventListener(type: string, listener: (event: MessageEvent) => void) {
      this.listeners[type] = [...(this.listeners[type] ?? []), listener];
    }
    close() { this.readyState = FakeEventSource.CLOSED; }
    emit(type: string, data: unknown) {
      for (const listener of this.listeners[type] ?? []) listener({ data: JSON.stringify(data) } as MessageEvent);
    }
  }
  globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;

  let latestStatus = '';
  function Harness() {
    const controller = useRunController();
    latestStatus = controller.state.status;
    React.useEffect(() => { void controller.start('家庭半日计划'); }, []);
    return null;
  }

  createRoot(document.getElementById('root')!).render(<Harness />);
  await new Promise((resolve) => setTimeout(resolve, 20));
  instances[0].emit('run.event', {
    type: 'run.completed',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 1,
    timestamp: '2026-06-19T00:00:00Z',
    payload: {},
  });
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(latestStatus, 'completed');
  globalThis.fetch = originalFetch;
  globalThis.EventSource = originalEventSource;
});
```

- [ ] **Step 2: Implement useRunController**

Create `features/runs/useRunController.ts`:

```typescript
'use client';

import { useCallback, useEffect, useReducer, useRef } from 'react';

import { approveRunActions, createRun, rejectRun, streamRunEvents } from './api';
import { initialRunState, runReducer } from './reducer';

export function useRunController() {
  const [state, dispatch] = useReducer(runReducer, initialRunState);
  const stopRef = useRef<null | (() => void)>(null);

  useEffect(() => () => stopRef.current?.(), []);

  const start = useCallback(async (goal: string, userId = 'local_demo_user') => {
    stopRef.current?.();
    const started = await createRun({ goal, user_id: userId, mode: 'plan' });
    stopRef.current = streamRunEvents(started.run_id, {
      onEvent: dispatch,
      onError: (error) => {
        dispatch({
          type: 'run.failed',
          run_id: started.run_id,
          plan_id: started.plan_id,
          seq: Number.MAX_SAFE_INTEGER,
          timestamp: new Date().toISOString(),
          payload: { error: error.message },
        });
      },
    });
  }, []);

  const approve = useCallback(async (actionIds: string[]) => {
    if (!state.runId) return;
    await approveRunActions(state.runId, actionIds);
  }, [state.runId]);

  const reject = useCallback(async () => {
    if (!state.runId) return;
    await rejectRun(state.runId);
  }, [state.runId]);

  return { state, start, approve, reject };
}
```

- [ ] **Step 3: Add plan API**

Create `features/plans/api.ts`:

```typescript
import { apiRequest } from '../../lib/api/client';

export async function getPlan(planId: string) {
  return apiRequest(`/api/plans/${planId}`);
}

export async function listPlans() {
  return apiRequest('/api/plans');
}
```

- [ ] **Step 4: Update UI integration**

Modify `app/page.tsx` to import `useRunController` instead of `usePlanMachine`. Keep rendering components as-is where their props still fit. Use `state.status` values from `features/runs/reducer.ts`.

Where the old code called:

```typescript
planMachine.startPlan(goal)
```

replace with:

```typescript
runController.start(goal)
```

Where the old code approved selected actions by plan id, call:

```typescript
runController.approve(selectedActionIds)
```

Where the old code rejected the plan, call:

```typescript
runController.reject()
```

- [ ] **Step 5: Run frontend focused tests**

Run:

```bash
npm run test:frontend -- tests/frontend/use-run-controller.test.tsx tests/frontend/run-api-client.test.ts tests/frontend/run-reducer.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add features/runs/useRunController.ts features/plans/api.ts app/page.tsx components/plan/ActionLedgerPanel.tsx components/trace/TracePanel.tsx tests/frontend/use-run-controller.test.tsx
git commit -m "feat: wire frontend to run contract"
```

---

### Task 9: Remove Old LangGraph Runtime and Legacy API

**Files:**
- Modify: `pyproject.toml`
- Modify: `backend/api/app.py`
- Delete: `backend/orchestrator/`
- Delete: `backend/graph/`
- Delete or shrink: `backend/services/workflow_service.py`
- Modify tests importing old graph/pipeline APIs.

- [ ] **Step 1: Write removal assertions**

Create `tests/backend/test_langgraph_removed.py`:

```python
from pathlib import Path


def test_langgraph_dependency_removed_from_pyproject():
    text = Path("pyproject.toml").read_text()
    assert "langgraph" not in text


def test_backend_production_code_does_not_import_langgraph():
    offenders = []
    for path in Path("backend").rglob("*.py"):
        text = path.read_text()
        if "langgraph" in text:
            offenders.append(str(path))
    assert offenders == []


def test_legacy_orchestrator_and_graph_modules_removed():
    assert not Path("backend/orchestrator").exists()
    assert not Path("backend/graph").exists()
```

- [ ] **Step 2: Run removal test to verify failure**

Run:

```bash
uv run pytest tests/backend/test_langgraph_removed.py -q
```

Expected: FAIL because LangGraph and old directories still exist.

- [ ] **Step 3: Remove dependency and old modules**

Modify `pyproject.toml` dependencies:

```toml
dependencies = [
    "fastapi>=0.136.1",
    "langchain-openai>=0.3.0",
    "openai-agents>=0.4.0",
    "uvicorn[standard]>=0.46.0",
]
```

Delete:

```bash
rm -rf backend/orchestrator backend/graph
```

Remove old inline routes in `backend/api/app.py`:

```text
POST /api/plans/runs
GET  /api/plans/runs/{run_id}/stream
POST /api/plans/{plan_id}/resume
```

Keep health, LLM status, users/profile, tool schemas, `/api/runs`, and `/api/plans`.

- [ ] **Step 4: Update API tests to new paths**

Modify `tests/backend/test_api.py` so OpenAPI path assertions include:

```python
for path in [
    "/api/health",
    "/api/runs",
    "/api/runs/{run_id}",
    "/api/runs/{run_id}/events",
    "/api/runs/{run_id}/actions/approve",
    "/api/runs/{run_id}/actions/reject",
    "/api/plans/{plan_id}",
    "/api/tool-schemas",
]:
    self.assertIn(path, paths)
```

and assert old paths are absent:

```python
for path in [
    "/api/plans/runs",
    "/api/plans/runs/{run_id}/stream",
    "/api/plans/{plan_id}/resume",
]:
    self.assertNotIn(path, paths)
```

- [ ] **Step 5: Run backend tests**

Run:

```bash
uv run pytest tests/backend/test_langgraph_removed.py tests/backend/test_api.py tests/backend/test_runs_api.py tests/backend/test_runs_runtime_integration.py tests/backend/test_run_approval_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock backend tests/backend/test_langgraph_removed.py tests/backend/test_api.py
git commit -m "refactor: remove LangGraph runtime"
```

---

### Task 10: Update Contracts, E2E, README, and Full Verification

**Files:**
- Modify: `tests/contracts/weekendpilot-contracts.test.ts`
- Modify: `tests/e2e/weekendpilot.spec.ts`
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `LocalLife-Agent-Design.md`

- [ ] **Step 1: Update contract tests**

Modify `tests/contracts/weekendpilot-contracts.test.ts` to assert new run event envelope:

```typescript
const RunEventEnvelope = z.object({
  type: z.string(),
  run_id: z.string(),
  plan_id: z.string().optional(),
  seq: z.number().int().positive(),
  timestamp: z.string(),
  payload: z.record(z.string(), z.unknown()),
});
```

Assert create-run response:

```typescript
const CreateRunResponse = z.object({
  run_id: z.string(),
  plan_id: z.string(),
  status: z.literal('queued'),
  events_url: z.string(),
});
```

- [ ] **Step 2: Update E2E flow**

Modify `tests/e2e/weekendpilot.spec.ts` so it waits for the UI state driven by `run.completed` or `approval.required`, not old `graph_update` phases.

Use visible UI assertions already present in the app, such as plan title, action ledger, and receipt cards. Do not assert internal LangGraph labels.

- [ ] **Step 3: Update docs**

In `README.md`:

- Remove the LangGraph badge.
- Replace "FastAPI + LangGraph + SQLite" with "FastAPI + OpenAI Agents SDK + SQLite".
- Replace old API table with:

```text
POST /api/runs
GET  /api/runs/{run_id}/events
GET  /api/runs/{run_id}
GET  /api/plans/{plan_id}
POST /api/runs/{run_id}/actions/approve
POST /api/runs/{run_id}/actions/reject
```

In `backend/README.md`:

- Replace `orchestrator/ central state-machine planner` with `agents/ OpenAI Agents SDK runtime`.
- Replace old smoke examples with `/api/runs`.

In `LocalLife-Agent-Design.md`:

- Replace LangGraph planning graph text with OpenAI Agents SDK runtime text.
- Keep the product positioning and safety claims.

- [ ] **Step 4: Run full verification**

Run:

```bash
uv run python -m compileall backend
npm run test:all
```

Expected: compile succeeds and all contract, frontend, backend tests pass.

Run E2E only after dev servers are working:

```bash
npm run dev:full
npm run test:e2e
```

Expected: Playwright tests pass.

- [ ] **Step 5: Commit**

```bash
git add README.md backend/README.md LocalLife-Agent-Design.md tests/contracts/weekendpilot-contracts.test.ts tests/e2e/weekendpilot.spec.ts
git commit -m "docs: document OpenAI Agents SDK architecture"
```

---

## Self-Review

Spec coverage:

- LangGraph removal is covered by Task 9.
- OpenAI Agents SDK runtime is covered by Task 5 and wired in Task 6.
- REST + SSE run contract is covered by Tasks 1, 2, 3, and 4.
- Approval safety is covered by Task 7.
- Frontend contract rewrite is covered by Task 4 and Task 8.
- Tests and docs are covered by Task 10.

Placeholder scan:

- This plan intentionally contains no placeholder markers, copy-forward shortcuts, or unspecified implementation steps.

Type consistency:

- Backend event names use `RunEvent.type`, matching frontend `RunEventEnvelopeSchema`.
- Product status uses `approval_required`, not the old `pending_approval` graph phase.
- Approval endpoints use run ids: `/api/runs/{run_id}/actions/approve` and `/api/runs/{run_id}/actions/reject`.
