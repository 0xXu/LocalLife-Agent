# Single-Question Clarification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one-question-at-a-time clarification to the OpenAI Agents SDK run flow using REST + SSE.

**Architecture:** `RunService` stores accumulated answers and the current structured question on the run record, then resumes the same run after `POST /api/runs/{run_id}/clarifications`. The runtime returns `needs_clarification` before creating plans when a hard blocker is missing. The frontend stores `currentQuestion` from `clarification.required` SSE events and submits typed answers without creating a new run.

**Tech Stack:** FastAPI, Pydantic, SQLite, OpenAI Agents SDK runtime abstraction, Next.js, React, Zod, node:test, unittest.

---

## File Structure

- Modify: `backend/agents/runtime.py` - add accumulated answers/constraints and optional clarification result to runtime domain types.
- Modify: `backend/agents/openai_runtime.py` - dry-run clarification decision and payload generation before plan approval.
- Modify: `backend/application/run_service.py` - persist answer/context JSON, handle `needs_clarification`, resume existing worker.
- Modify: `backend/api/schemas/runs.py` - Pydantic request/response models for clarification answers.
- Modify: `backend/api/routes/runs.py` - add `POST /api/runs/{run_id}/clarifications`.
- Modify: `features/runs/schemas.ts` - Zod schemas for clarification question, event payload, and submit request.
- Modify: `features/runs/api.ts` - add `submitClarification`.
- Modify: `features/runs/reducer.ts` - track and clear `currentQuestion`.
- Modify: `features/runs/useRunController.ts` - expose `answerClarification`.
- Create: `components/clarification/ClarificationCard.tsx` - structured one-question form.
- Modify: `app/page.tsx` - render `ClarificationCard` from run state and remove old new-run clarification behavior.
- Tests: targeted backend, frontend, contract, and e2e tests listed below.

---

### Task 1: Backend Runtime And Run Context

**Files:**
- Modify: `backend/agents/runtime.py`
- Modify: `backend/agents/openai_runtime.py`
- Modify: `backend/application/run_service.py`
- Test: `tests/backend/test_openai_agents_runtime.py`
- Test: `tests/backend/test_runs_runtime_integration.py`

- [ ] **Step 1: Write failing runtime test**

Add to `tests/backend/test_openai_agents_runtime.py`:

```python
async def test_local_dry_run_asks_one_clarification_before_approval(self):
    events = []

    async def sink(event_type, payload):
        events.append((event_type, payload))

    runtime = OpenAIAgentsRuntime(dry_run=True)
    result = await runtime.start_plan(
        PlanRunRequest(goal="下午帮我安排个地方玩一下", user_id="user_1"),
        RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
        sink,
    )

    self.assertEqual(result.status, "needs_clarification")
    self.assertEqual(result.clarification["question"]["id"], "time_window")
    self.assertEqual([event[0] for event in events], ["agent.started", "clarification.required"])
```

Run: `uv run python -m pytest tests/backend/test_openai_agents_runtime.py -q`
Expected: FAIL because `PlanRunResult.clarification` does not exist and runtime returns approval.

- [ ] **Step 2: Write failing resume integration test**

Add to `tests/backend/test_runs_runtime_integration.py`:

```python
def test_run_resumes_same_run_after_single_clarification_answer(self):
    created = self.client.post("/api/runs", json={"goal": "下午帮我安排个地方玩一下"}).json()
    self.wait_for_status(created["run_id"], "needs_clarification")

    response = self.client.post(
        f"/api/runs/{created['run_id']}/clarifications",
        json={"question_id": "time_window", "answer": "今天下午 2 点开始，玩 3 小时"},
    )

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["run_id"], created["run_id"])
    self.assertEqual(response.json()["accepted_question_id"], "time_window")
    status = self.wait_for_status(created["run_id"], "approval_required")
    self.assertEqual(status["plan_id"], created["plan_id"])
```

Run: `uv run python -m pytest tests/backend/test_runs_runtime_integration.py -q`
Expected: FAIL with route missing.

- [ ] **Step 3: Implement domain/runtime fields**

Update `backend/agents/runtime.py`:

```python
@dataclass(frozen=True)
class PlanRunRequest:
    goal: str
    user_id: str = "local_demo_user"
    answers: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PlanRunResult:
    status: str
    plan: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    pending_actions: list[dict[str, Any]] = field(default_factory=list)
    clarification: dict[str, Any] | None = None
    raw_output: Any | None = None
```

- [ ] **Step 4: Implement first-version dry-run clarification selection**

In `backend/agents/openai_runtime.py`, before creating the dry-run pending action, return a `time_window` clarification when `request.answers` lacks `time_window`. Emit `clarification.required` with exactly one `question`, `partial_constraints`, and `missing_fields`.

The emitted question must be:

```python
{
    "id": "time_window",
    "label": "今天下午大概几点开始？",
    "description": "时间范围会影响营业状态、路线顺序和预约动作。",
    "kind": "time",
    "required": True,
    "options": [
        {"label": "今天下午 2 点", "value": "今天下午 2 点"},
        {"label": "今天下午 4 点", "value": "今天下午 4 点"},
        {"label": "今晚 7 点", "value": "今晚 7 点"},
    ],
    "allow_custom": True,
}
```

- [ ] **Step 5: Implement run context persistence and `needs_clarification` handling**

In `backend/application/run_service.py`:

- Add nullable JSON columns to `runs`: `answers_json`, `constraints_json`, `current_question_json`.
- Make `_init_db()` migrate existing tables with `alter table` guarded by `pragma table_info`.
- `create_run()` inserts `{}` for answers/constraints and `None` for current question.
- `get_run()` may keep returning the same `RunRecord`.
- Add `submit_clarification(run_id: str, question_id: str, answer: Any) -> RunRecord`.
- In `_run_worker()`, pass `answers` and `constraints` into `RuntimePlanRunRequest`.
- If `result.status == "needs_clarification"`, save `current_question_json`, update status to `needs_clarification`, do not save an approval plan, emit `run.completed` with status `needs_clarification`, close the queue, and return.
- `submit_clarification()` validates the current status/question, stores `answers[question_id] = answer`, clears `current_question_json`, sets status to `running`, opens a fresh queue, emits `run.running`, and starts a worker for the same run.

- [ ] **Step 6: Run targeted backend tests**

Run: `uv run python -m pytest tests/backend/test_openai_agents_runtime.py tests/backend/test_runs_runtime_integration.py -q`
Expected: PASS.

---

### Task 2: Backend REST Contract

**Files:**
- Modify: `backend/api/schemas/runs.py`
- Modify: `backend/api/routes/runs.py`
- Test: `tests/backend/test_runs_api.py`

- [ ] **Step 1: Write failing endpoint tests**

Add to `tests/backend/test_runs_api.py`:

```python
def test_submit_clarification_requires_current_question(self):
    created = self.client.post("/api/runs", json={"goal": "family afternoon"}).json()

    response = self.client.post(
        f"/api/runs/{created['run_id']}/clarifications",
        json={"question_id": "time_window", "answer": "今天下午 2 点"},
    )

    self.assertEqual(response.status_code, 400)
    self.assertEqual(response.json()["error"]["code"], "clarification_not_required")

def test_submit_clarification_validates_question_id(self):
    created = self.client.post("/api/runs", json={"goal": "下午帮我安排个地方玩一下"}).json()
    self.run_service.wait_for_workers(timeout=2.0)

    response = self.client.post(
        f"/api/runs/{created['run_id']}/clarifications",
        json={"question_id": "party_size", "answer": 3},
    )

    self.assertEqual(response.status_code, 400)
    self.assertEqual(response.json()["error"]["code"], "clarification_question_mismatch")
```

Run: `uv run python -m pytest tests/backend/test_runs_api.py -q`
Expected: FAIL with missing endpoint.

- [ ] **Step 2: Implement schemas**

Add to `backend/api/schemas/runs.py`:

```python
class SubmitClarificationRequest(BaseModel):
    question_id: str = Field(min_length=1)
    answer: Any


class SubmitClarificationResponse(BaseModel):
    run_id: str
    status: str
    accepted_question_id: str
```

- [ ] **Step 3: Implement route**

Add to `backend/api/routes/runs.py`:

```python
@router.post("/{run_id}/clarifications", response_model=SubmitClarificationResponse)
async def submit_clarification(run_id: str, body: SubmitClarificationRequest, request: Request) -> SubmitClarificationResponse:
    record = run_service(request).submit_clarification(run_id, body.question_id, body.answer)
    return SubmitClarificationResponse(
        run_id=record.run_id,
        status=record.status,
        accepted_question_id=body.question_id,
    )
```

- [ ] **Step 4: Run targeted API tests**

Run: `uv run python -m pytest tests/backend/test_runs_api.py -q`
Expected: PASS.

---

### Task 3: Frontend Contract And Controller

**Files:**
- Modify: `features/runs/schemas.ts`
- Modify: `features/runs/api.ts`
- Modify: `features/runs/reducer.ts`
- Modify: `features/runs/useRunController.ts`
- Test: `tests/frontend/run-schemas.test.ts`
- Test: `tests/contracts/weekendpilot-contracts.test.ts`
- Test: `tests/frontend/run-api-client.test.ts`
- Test: `tests/frontend/run-reducer.test.ts`
- Test: `tests/frontend/use-run-controller.test.tsx`

- [ ] **Step 1: Write failing schema/reducer/api/controller tests**

Tests must assert:

- `RunEventTypeSchema` accepts `clarification.required`.
- `ClarificationRequiredPayloadSchema` parses exactly one question.
- `runReducer` sets `status` to `needs_clarification` and stores `currentQuestion`.
- `runReducer` clears `currentQuestion` on `run.started`, `agent.started`, `run.completed`, `run.failed`, and `run.rejected`.
- `submitClarification("run_1", { question_id: "time_window", answer: "今天下午 2 点" })` posts to `/api/runs/run_1/clarifications`.
- `useRunController().answerClarification("time_window", "今天下午 2 点")` calls that endpoint for the current run.

Run: `npm run test:frontend -- --runInBand` if available, otherwise run the listed node tests directly through the repo's existing script.
Expected: FAIL because schemas/API/controller are missing.

- [ ] **Step 2: Implement schemas**

In `features/runs/schemas.ts`, add `clarification.required` to `RunEventTypeSchema` and export:

```ts
export const ClarificationOptionSchema = z.object({
  label: z.string().min(1),
  value: z.union([z.string(), z.number(), z.boolean()]),
});

export const ClarificationQuestionSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  description: z.string().optional(),
  kind: z.enum(['single_select', 'multi_select', 'number', 'text', 'time', 'location']),
  required: z.boolean(),
  options: z.array(ClarificationOptionSchema).optional(),
  allow_custom: z.boolean().optional(),
  validation: z.object({
    min: z.number().optional(),
    max: z.number().optional(),
    pattern: z.string().optional(),
  }).optional(),
});

export const ClarificationRequiredPayloadSchema = z.object({
  question: ClarificationQuestionSchema,
  partial_constraints: z.record(z.string(), z.unknown()).default({}),
  missing_fields: z.array(z.string()).default([]),
});

export const SubmitClarificationRequestSchema = z.object({
  question_id: z.string().min(1),
  answer: z.unknown(),
});
```

- [ ] **Step 3: Implement frontend API and reducer**

In `features/runs/api.ts`, add:

```ts
export async function submitClarification(runId: string, input: SubmitClarificationRequest) {
  const body = SubmitClarificationRequestSchema.parse(input);
  return apiRequest<unknown>(`/api/runs/${runId}/clarifications`, {
    method: 'POST',
    body,
  });
}
```

In `features/runs/reducer.ts`, add `currentQuestion` to state and handle the event behavior listed in Step 1.

- [ ] **Step 4: Implement controller method**

In `features/runs/useRunController.ts`, import `submitClarification`, expose `answerClarification(questionId, answer)`, and return early when there is no `state.runId`.

- [ ] **Step 5: Run targeted frontend tests**

Run: `npm run test:frontend`
Expected: PASS.

---

### Task 4: Frontend UI Integration And E2E

**Files:**
- Create: `components/clarification/ClarificationCard.tsx`
- Modify: `app/page.tsx`
- Modify: existing CSS file that owns app component classes
- Test: `tests/frontend/clarification-card.test.tsx`
- Test: `tests/e2e/weekendpilot.spec.ts`

- [ ] **Step 1: Write failing UI test**

Create `tests/frontend/clarification-card.test.tsx` to render a `number` question with preset options and custom input. Assert that clicking option `2 位` submits `answer: 2`, and custom value `5` submits `answer: 5`.

Run: `npm run test:frontend`
Expected: FAIL because component does not exist.

- [ ] **Step 2: Implement `ClarificationCard`**

Props:

```ts
type ClarificationCardProps = {
  question: ClarificationQuestion;
  submitting?: boolean;
  error?: string | null;
  onSubmit: (questionId: string, answer: unknown) => void | Promise<void>;
};
```

Render one question only. For options, render buttons. For `allow_custom`, render an input whose type is `number` for `kind === "number"` and text otherwise. Disable submit until required answer exists and numeric values satisfy `validation.min/max`.

- [ ] **Step 3: Wire app page**

In `app/page.tsx`, stop converting clarification into old `ClarificationView`. When `state.status === "needs_clarification"` and `state.currentQuestion` exists, render `ClarificationCard` and call `runController.answerClarification`. Keep the existing progress/results views unchanged.

- [ ] **Step 4: Add e2e coverage**

In `tests/e2e/weekendpilot.spec.ts`, add a flow that submits an underspecified goal, waits for the clarification card, answers the time question, then waits for approval/results state.

- [ ] **Step 5: Run UI/e2e verification**

Run: `npm run test:frontend`
Expected: PASS.

Run: `npm run test:e2e`
Expected: PASS.

---

## Final Verification

- [ ] Run `uv run python -m compileall backend`.
- [ ] Run `npm run test:all`.
- [ ] Run `npm run build`.
- [ ] Run `npm run test:e2e`.
- [ ] Confirm `git status --short` only contains intentional changes and untracked `.codegraph/`.
