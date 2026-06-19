# Single-Question Clarification Design

Date: 2026-06-19
Status: Proposed

## Goal

Add a multi-turn clarification loop for LocalLife-Agent. When the agent cannot safely plan because a required field is missing, the run pauses and asks one highest-priority structured question. The user answers through the UI, the answer is persisted into the run context, and the same run continues. This repeats until enough information exists to produce a plan or approval ledger.

## Non-Goals

- Do not ask several clarification questions in one event.
- Do not start a new run for each answer.
- Do not restore the removed LangGraph or legacy planner API.
- Do not build a general survey/form builder beyond the local-life planning needs.
- Do not rely on unstructured free-text agent questions as the frontend contract.

## Product Behavior

The user may submit an underspecified goal such as:

```text
下午帮我安排个地方玩一下
```

The system should pause planning and ask one question:

```text
今天下午大概几点开始？
```

After the user answers, the run continues. If another blocker remains, the system asks the next question:

```text
从哪里出发？
```

The loop continues through one question at a time until required planning constraints are available.

## Missing Field Priority

The agent chooses one question per turn using this priority order:

1. `time_window`
2. `start_location`
3. `party_size`
4. `scenario`
5. `budget`
6. `diet_preferences`
7. `accessibility`
8. `transport_preference`
9. `activity_preference`

The highest-priority missing hard blocker wins. Soft preferences should not block planning unless the user explicitly asked for them and the agent cannot resolve them.

## API Contract

Add:

```text
POST /api/runs/{run_id}/clarifications
```

Request:

```json
{
  "question_id": "party_size",
  "answer": 3
}
```

Response:

```json
{
  "run_id": "run_...",
  "status": "running",
  "accepted_question_id": "party_size"
}
```

The endpoint updates run context and starts the background worker again for the same run.

## SSE Contract

Add one event type:

```text
clarification.required
```

Payload:

```json
{
  "question": {
    "id": "party_size",
    "label": "这次一共有几位？",
    "description": "人数会影响餐厅容量、预算和路线时间。",
    "kind": "number",
    "required": true,
    "options": [
      { "label": "1 位", "value": 1 },
      { "label": "2 位", "value": 2 },
      { "label": "3 位", "value": 3 },
      { "label": "4 位", "value": 4 }
    ],
    "allow_custom": true,
    "validation": { "min": 1, "max": 20 }
  },
  "partial_constraints": {
    "time_window": "this_afternoon"
  },
  "missing_fields": ["party_size", "start_location"]
}
```

`clarification.required` sets run status to `needs_clarification`.

## Question Model

```ts
type ClarificationQuestion = {
  id: string;
  label: string;
  description?: string;
  kind: 'single_select' | 'multi_select' | 'number' | 'text' | 'time' | 'location';
  required: boolean;
  options?: Array<{ label: string; value: string | number | boolean }>;
  allow_custom?: boolean;
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
  };
};
```

Supported first-version control kinds:

- `single_select`: radio chips or segmented options.
- `multi_select`: checkbox chips.
- `number`: quick chips plus numeric input when `allow_custom` is true.
- `text`: text input.
- `time`: time input or time chips.
- `location`: text input with location-specific placeholder.

## Backend Runtime Design

`OpenAIAgentsRuntime.start_plan()` should return one of:

```python
PlanRunResult(status="needs_clarification", clarification=question_result)
PlanRunResult(status="approval_required", plan=..., pending_actions=...)
PlanRunResult(status="completed", plan=...)
PlanRunResult(status="validation_failed", validation=...)
```

Add runtime/domain fields:

```python
PlanRunRequest(
    goal: str,
    user_id: str,
    answers: dict[str, Any] = {},
    constraints: dict[str, Any] = {},
)

PlanRunResult(
    status: str,
    plan: dict[str, Any] = {},
    validation: dict[str, Any] = {},
    pending_actions: list[dict[str, Any]] = [],
    clarification: dict[str, Any] | None = None,
)
```

`RunService` owns the durable context:

```text
run_context
  run_id
  answers_json
  constraints_json
  current_question_json
  updated_at
```

The first implementation may store context in the existing `runs` table as JSON columns if that is simpler.

## Resume Flow

1. User creates a run with `POST /api/runs`.
2. Runtime detects missing required information.
3. `RunService` saves `current_question`, partial constraints, and answers gathered so far.
4. `RunService` emits `clarification.required` and sets run status to `needs_clarification`.
5. Frontend renders the question.
6. User submits `POST /api/runs/{run_id}/clarifications`.
7. Backend validates `question_id` matches the current question.
8. Backend stores the answer, clears the current question, sets status to `running`, and restarts the worker.
9. Runtime sees the accumulated answers and either asks another question or completes planning.

## Frontend Design

Add:

```text
components/clarification/ClarificationCard.tsx
features/runs/clarification.ts
```

Extend `features/runs/schemas.ts`:

- `ClarificationQuestionSchema`
- `ClarificationRequiredPayloadSchema`
- `SubmitClarificationRequestSchema`
- add `clarification.required` to `RunEventTypeSchema`

Extend `features/runs/reducer.ts`:

```ts
state.currentQuestion: ClarificationQuestion | null
```

Reducer behavior:

- `clarification.required`: status `needs_clarification`, store `currentQuestion`, keep trace events.
- `run.started` or `agent.started` after an answer: clear `currentQuestion`.
- terminal states: clear `currentQuestion`.

Extend `features/runs/api.ts`:

```ts
submitClarification(runId, { question_id, answer })
```

Extend `useRunController`:

```ts
answerClarification(questionId, answer)
```

`app/page.tsx` should render `ClarificationCard` when `state.status === 'needs_clarification'` and `state.currentQuestion` exists.

## Validation

Backend validation:

- `run_id` must exist.
- status must be `needs_clarification`.
- `question_id` must match the current question.
- `answer` must satisfy question kind and validation.
- answer is stored under `answers[question_id]`.

Frontend validation:

- required questions cannot submit empty answers.
- number controls enforce min/max.
- `single_select` accepts one option or custom value when allowed.
- `multi_select` accepts an array.

## Testing

Backend:

- Runtime dry-run can return `needs_clarification` for missing `party_size`.
- `POST /api/runs/{run_id}/clarifications` accepts the current question answer.
- Wrong `question_id` returns `validation_error`.
- A run can ask multiple questions over multiple answer submissions.
- After enough answers, the same run reaches `approval_required`.

Frontend:

- `RunEventEnvelopeSchema` accepts `clarification.required`.
- reducer stores and clears `currentQuestion`.
- `ClarificationCard` renders number/select/text/time/location controls.
- `useRunController.answerClarification()` posts to the new endpoint.
- App shows a single question and resumes progress after submit.

E2E:

- Submit underspecified goal.
- See first clarification question.
- Answer it.
- See another clarification question or final approval.
- Complete approval flow.

## Acceptance Criteria

- The agent never fabricates required missing values such as party size, start location, or time window.
- The UI asks one question at a time.
- Answers resume the same run and preserve trace/history.
- Multiple clarification rounds are supported.
- `npm run test:all` passes.
- E2E covers at least one clarification round.

