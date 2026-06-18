# OpenAI Agents SDK Redesign Design

Date: 2026-06-19
Status: Proposed

## Goal

Replace the current LangGraph-centered planning runtime with an OpenAI Agents SDK-first backend and a redesigned REST + SSE frontend contract.

The redesign keeps the product intent of LocalLife-Agent: convert a natural-language local-life goal into a grounded itinerary, explain the evidence, require explicit user approval for side-effect actions, execute approved actions idempotently, and return auditable receipts. The implementation should become simpler by removing graph-specific orchestration from the business core and using the Agents SDK for agent execution, handoffs, tools, guardrails, streaming, and tracing.

## Non-Goals

- Do not migrate the app to WebSocket.
- Do not add multi-tenant account, billing, or production marketplace features.
- Do not connect real booking, payment, messaging, map, or calendar providers in this pass.
- Do not preserve LangGraph as a fallback runtime.
- Do not keep backward compatibility for old frontend API paths unless a test needs temporary transitional coverage.

## Current Problems

The current backend has useful domain behavior, but the runtime boundary is too tangled:

- `WorkflowService` owns run creation, pipeline execution, SSE queueing, revision persistence, action ledger seeding, validation transitions, and response shaping.
- `backend/orchestrator/pipeline.py` and related graph modules make LangGraph the central architecture concern instead of an implementation detail.
- Frontend code depends on backend-specific phase names and payload shapes, especially through `usePlanMachine` and `apiClient.ts`.
- API contracts are spread across Python models, TypeScript Zod schemas, tests, and ad hoc response shaping.
- Trace, tool call summaries, approval state, and final plan state are related but not modeled as one event stream.

## Target Architecture

```text
FastAPI
  api/routes
  api/schemas
    |
    v
Application Services
  RunService
  ApprovalService
  ProfileService
    |
    v
Domain
  Run
  Plan
  PlanRevision
  PendingAction
  Receipt
  RunEvent
    |
    v
Agent Runtime
  OpenAIAgentsRuntime
  PlannerAgent
  SearchAgent
  RankerAgent
  ValidatorAgent
  ExecutorAgent
    |
    v
Infrastructure
  WorkflowRepository
  EventStore
  ActionLedger
  LocalCatalogTools
```

The application layer owns product state. The Agents SDK owns agent execution.

### Backend Package Layout

```text
backend/
  api/
    app.py
    routes/
      health.py
      runs.py
      plans.py
      profiles.py
      tools.py
    schemas/
      runs.py
      plans.py
      actions.py
      events.py
      errors.py
  application/
    run_service.py
    approval_service.py
    profile_service.py
  domain/
    run.py
    plan.py
    actions.py
    events.py
    errors.py
  agents/
    runtime.py
    openai_runtime.py
    planner_agent.py
    validator_agent.py
    executor_agent.py
    tools.py
    guardrails.py
  infrastructure/
    repositories.py
    event_store.py
    local_catalog.py
    sqlite.py
  observability/
    traces.py
```

Existing modules can be moved incrementally, but the final architecture should remove `backend/orchestrator`, `backend/graph`, and the LangGraph dependency.

## API Contract

The contract is run-centered. A plan is the durable artifact produced by a run. A run can finish with a complete plan, require approval for side-effect actions, fail validation, or fail unexpectedly.

### Endpoints

```text
GET  /api/health
GET  /api/llm/status

POST /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/events
POST /api/runs/{run_id}/actions/approve
POST /api/runs/{run_id}/actions/reject

GET  /api/plans
GET  /api/plans/{plan_id}
GET  /api/plans/{plan_id}/versions

GET  /api/users/{user_id}/profile
PUT  /api/users/{user_id}/profile
GET  /api/tool-schemas
```

Remove these old paths after migration:

```text
POST /api/plans/runs
GET  /api/plans/runs/{run_id}/stream
POST /api/plans/{plan_id}/resume
```

### Request and Response Shapes

`POST /api/runs`

```json
{
  "goal": "今天下午想和老婆孩子出去玩几个小时，别太远",
  "user_id": "local_demo_user",
  "mode": "plan"
}
```

Response:

```json
{
  "run_id": "run_...",
  "plan_id": "plan_...",
  "status": "queued",
  "events_url": "/api/runs/run_.../events"
}
```

`GET /api/runs/{run_id}`

```json
{
  "run_id": "run_...",
  "plan_id": "plan_...",
  "status": "approval_required",
  "current_agent": "validator",
  "created_at": "2026-06-19T00:00:00Z",
  "updated_at": "2026-06-19T00:00:03Z",
  "error": null
}
```

`POST /api/runs/{run_id}/actions/approve`

```json
{
  "action_ids": ["act_1", "act_2"]
}
```

Response:

```json
{
  "run_id": "run_...",
  "status": "executing",
  "accepted_action_ids": ["act_1", "act_2"]
}
```

`POST /api/runs/{run_id}/actions/reject`

```json
{
  "reason": "user_rejected"
}
```

Response:

```json
{
  "run_id": "run_...",
  "status": "rejected"
}
```

### Status Values

```text
queued
running
needs_clarification
approval_required
executing
completed
validation_failed
rejected
failed
```

These are product states, not framework internals.

## SSE Contract

`GET /api/runs/{run_id}/events` streams `text/event-stream`.

Every event uses a stable server event id and a JSON payload:

```text
id: evt_000001
event: run.event
data: {"type":"run.started","run_id":"run_...","seq":1,"timestamp":"..."}
```

### Event Envelope

```ts
type RunEventEnvelope = {
  type: RunEventType;
  run_id: string;
  plan_id?: string;
  seq: number;
  timestamp: string;
  payload: Record<string, unknown>;
};
```

### Event Types

```text
run.started
run.heartbeat
agent.started
agent.completed
agent.handoff
tool.called
tool.completed
tool.failed
guardrail.triggered
plan.draft.created
plan.validation.completed
approval.required
actions.execution.started
actions.execution.completed
run.completed
run.failed
run.rejected
```

The frontend reducer should depend on this event vocabulary instead of backend file names, LangGraph node names, or one-off phase labels.

## Agent Runtime Design

Define a runtime protocol:

```python
class AgentRuntime(Protocol):
    async def start_plan(
        self,
        request: PlanRunRequest,
        context: RunContext,
        sink: EventSink,
    ) -> PlanRunResult:
        ...

    async def execute_actions(
        self,
        request: ExecuteActionsRequest,
        context: RunContext,
        sink: EventSink,
    ) -> ExecutionResult:
        ...
```

`OpenAIAgentsRuntime` is the only implementation after this migration.

### Agents

- `PlannerAgent`: turns the user goal and profile into structured planning intent and a work plan.
- `SearchAgent`: calls local catalog, weather, route, availability, and cost tools.
- `RankerAgent`: selects candidate itinerary variants and explains tradeoffs.
- `ValidatorAgent`: verifies time windows, weather risk, opening hours, capacity, budget, route feasibility, and action grounding.
- `ExecutorAgent`: executes only approved pending actions and returns receipts.

Use Agents SDK handoffs for specialist delegation where the model should choose the next specialist. Use explicit Python orchestration in `RunService` where product state must be deterministic, such as persisting run state, emitting product events, and pausing for approval.

### Tools

Keep deterministic local tools, but expose them as Agents SDK function tools:

```text
parse_user_goal
get_weather
search_places
search_restaurants
check_availability
optimize_route
build_itinerary
validate_plan
get_poi_details
check_weather
check_opening_hours
search_alternatives
estimate_cost
compare_alternatives
```

Side-effect tools remain separate and require approval:

```text
reserve_activity
create_reservation
claim_coupon
create_order
send_plan_message
create_calendar_event
```

The agent runtime may propose side-effect tool calls as pending actions. It must not execute them until `ApprovalService` receives explicit approval.

### Guardrails

Guardrails are product safety gates:

- Input guardrail: reject empty goals and block unsupported execution-only prompts.
- Tool input guardrail: ensure tool calls include required grounded ids, time, party size, and user id.
- Tool output guardrail: reject ungrounded POIs or malformed route/cost/availability outputs.
- Final output guardrail: require a valid plan schema and grounded pending actions before persistence.

Guardrail failures emit `guardrail.triggered` and normally produce `validation_failed` unless the failure is a user-facing clarification need.

### Tracing

Agents SDK tracing should be enabled. Convert SDK trace items into product-level `RunEvent` rows for the frontend:

- model/agent start and completion -> `agent.started`, `agent.completed`
- handoff -> `agent.handoff`
- tool call lifecycle -> `tool.called`, `tool.completed`, `tool.failed`
- guardrail tripwire -> `guardrail.triggered`

The app should store only product-safe trace metadata and tool summaries. Do not expose raw hidden prompts or sensitive environment values.

## Persistence

Keep SQLite for the migration. The schema should make run events first-class:

```text
runs
  run_id
  plan_id
  user_id
  status
  goal
  current_agent
  error_json
  created_at
  updated_at

run_events
  event_id
  run_id
  seq
  event_type
  payload_json
  created_at

plans
  plan_id
  run_id
  user_id
  latest_revision_id
  status
  created_at
  updated_at

plan_revisions
  revision_id
  plan_id
  version
  status
  plan_json
  validation_json
  created_at

pending_actions
  action_id
  run_id
  plan_id
  revision_id
  tool
  target
  payload_json
  status
  idempotency_key
  created_at
  updated_at

receipts
  receipt_id
  action_id
  tool
  status
  payload_json
  created_at
```

SSE should read from an in-memory per-run queue while a run is active and fall back to `run_events` for reconnects. This keeps the current responsive behavior while making event replay deterministic.

## Frontend Design

Replace `usePlanMachine` with a smaller event-driven feature module:

```text
features/runs/
  api.ts
  schemas.ts
  reducer.ts
  useRunController.ts

features/plans/
  api.ts
  schemas.ts
  selectors.ts
```

`useRunController` should:

- call `POST /api/runs`
- subscribe to `/api/runs/{run_id}/events`
- reduce `RunEventEnvelope` values into UI state
- fetch `/api/plans/{plan_id}` only when the event stream says a plan is available
- call approval/rejection endpoints by run id

The UI should not know about Agents SDK classes or backend module names.

## Testing Strategy

### Backend

- Unit-test `RunService` status transitions.
- Unit-test `EventStore` append/replay ordering.
- Unit-test OpenAI tool wrappers with deterministic local catalog fixtures.
- Unit-test guardrails for malformed tool inputs, ungrounded actions, and invalid final plan output.
- Test approval execution idempotency.
- Test API endpoints with FastAPI test client.
- Test SSE replay from active queue and persisted event history.

### Frontend

- Contract-test TypeScript schemas against representative backend fixtures.
- Unit-test run reducer for all event types.
- Unit-test `useRunController` for run start, stream completion, approval required, failure, and reconnect.
- Keep component tests for results, trace, action ledger, and receipts.

### E2E

- Start a run, observe streaming progress, reach plan result.
- Start a run that requires approval, approve selected actions, observe receipts.
- Reject a run requiring approval.
- Confirm SSE reconnect can recover persisted events.

## Migration Plan

1. Add new API/domain schemas and TypeScript contract schemas.
2. Add `EventStore` and new run-centered repository methods.
3. Add `OpenAIAgentsRuntime` and Agents SDK tool wrappers.
4. Implement new `/api/runs` and `/api/plans` routes.
5. Replace frontend planner API client and state hook with run-centered modules.
6. Port tests from old plan-run paths to new run paths.
7. Remove LangGraph dependency and delete `backend/orchestrator` and `backend/graph`.
8. Update README and backend README to describe OpenAI Agents SDK.

## Risks and Mitigations

- Agents SDK streaming/event APIs may expose lower-level events differently than the current UI expects. Mitigation: normalize everything through `RunEventEnvelope`.
- Fully removing LangGraph can break many backend tests at once. Mitigation: migrate tests by contract area rather than by old module name.
- Agent output can be less deterministic than rule-based fallback. Mitigation: keep local catalog deterministic and enforce final output guardrails.
- Approval resume semantics must remain safe. Mitigation: keep action ledger idempotency in the application layer, independent of the SDK.
- Existing README and diagrams will become stale. Mitigation: update docs after implementation, not before the code lands.

## Acceptance Criteria

- `pyproject.toml` no longer depends on `langgraph`.
- No backend production module imports `langgraph`.
- New run API contract is covered by backend and frontend contract tests.
- SSE events use the new `RunEventEnvelope` format.
- A user can create a plan, stream progress, view a plan, approve actions, and receive receipts through the Next app.
- Side-effect tools cannot execute without explicit approval.
- `npm run test:all` passes.

## References

- OpenAI Agents SDK agents: https://openai.github.io/openai-agents-python/agents/
- OpenAI Agents SDK tools: https://openai.github.io/openai-agents-python/tools/
- OpenAI Agents SDK handoffs: https://openai.github.io/openai-agents-python/handoffs/
- OpenAI Agents SDK guardrails: https://openai.github.io/openai-agents-python/guardrails/
- OpenAI Agents SDK tracing: https://openai.github.io/openai-agents-python/tracing/
