# LocalLife-Agent / WeekendPilot

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js 15](https://img.shields.io/badge/Next.js%2015-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![React 19](https://img.shields.io/badge/React%2019-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev/)
[![OpenAI Agents SDK](https://img.shields.io/badge/OpenAI%20Agents%20SDK-111827?style=for-the-badge)](https://openai.github.io/openai-agents-python/)
[![SQLite](https://img.shields.io/badge/SQLite-074D5B?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org/)

LocalLife-Agent, also called WeekendPilot, is a local-life planning assistant built around a run-centered REST + SSE contract. A user can enter an underspecified goal such as "我想出去玩", the agent asks one key clarification question at a time, validates the completed context once, generates a structured plan, then waits for explicit approval before executing any side-effect action.

The current implementation has fully removed the old LangGraph-centered runtime. The backend uses FastAPI, SQLite, and the OpenAI Agents SDK. The frontend is a Next.js workbench that renders chat clarification, live run events, structured plans, variants, evidence, traces, and an approval ledger.

## Current Principles

- **No synthetic plan**: remote planning must return a valid structured JSON plan. Markdown, plain text, missing itinerary, or empty variants fail with `planner_contract_invalid` instead of producing an empty approval page.
- **One question at a time**: intent extraction identifies missing fields once, stores them in a queue, and the UI asks only the highest-priority question for each round.
- **Final validation is separate**: `FinalValidationTool` runs once after the clarification queue is complete. It is not the intent extractor reused in a loop.
- **Approval before side effects**: planning only creates pending actions. Execution starts only after the user approves selected action ids.
- **Run-centered contract**: all live state flows through `/api/runs`, `/api/runs/{run_id}/events`, `/api/runs/{run_id}/clarifications`, and approval endpoints.

## Architecture

![LocalLife-Agent architecture](docs/assets/locallife-architecture.png)

### Frontend

- `app/` and `components/` implement the Next.js workbench.
- `features/runs/` owns run creation, SSE subscription, clarification submission, approval, rejection, and reducer state.
- `components/chat/` renders the assistant-style clarification flow.
- `components/plan/` renders structured plan results, variants, overview metrics, evidence, trace, and action ledger.

### Backend

- `backend/api/` exposes FastAPI JSON and SSE endpoints.
- `backend/application/run_service.py` owns run lifecycle, persisted answers, current question, plan snapshots, events, and worker execution.
- `backend/agents/openai_runtime.py` wires the OpenAI Agents SDK runtime.
- `backend/agents/intent_extraction_tool.py` extracts intent and the initial missing-field queue.
- `backend/agents/final_validation_tool.py` performs one final completeness check after the queue is exhausted.
- `backend/infrastructure/` persists workflow state and replayable events in SQLite.

## Planning Flow

![LocalLife-Agent planning flow](docs/assets/locallife-planning-flow.png)

1. The frontend calls `POST /api/runs` with the natural-language goal.
2. The frontend subscribes to `GET /api/runs/{run_id}/events` and reduces named `run.event` SSE frames.
3. `IntentExtractionTool` runs once to extract known constraints and an ordered list of missing fields.
4. If fields are missing, the backend emits `clarification.required` and stores the current question. The user answers through `POST /api/runs/{run_id}/clarifications`.
5. When the queue is empty, `FinalValidationTool` runs once. It may request one more missing field or allow planning.
6. `PlannerAgent` must return compact JSON with `title`, `summary`, `overview`, `constraint_fit`, non-empty `itinerary`, and non-empty `variants`.
7. The backend validates the planner contract. Invalid planner output raises `planner_contract_invalid` and the run fails instead of showing a synthetic plan.
8. A valid plan is persisted as an approval-required snapshot with pending actions.
9. The user approves selected actions with `POST /api/runs/{run_id}/actions/approve`.
10. The backend executes approved local adapters idempotently and returns receipts.

## Strict Planner Contract

The planner prompt requires JSON only. The backend rejects outputs that cannot render a real plan.

```json
{
  "title": "下午室内放松计划",
  "summary": "两人从当前位置出发，优先选择安静、低负担的室内放松方案。",
  "overview": {
    "theme": "室内放松",
    "totalDuration": "约 2.5 小时",
    "driveTime": "约 10 分钟",
    "walkingDistance": "约 0.8 公里",
    "estimatedCost": "人均 80-120 元",
    "score": 91
  },
  "constraint_fit": {
    "distance": 0.88,
    "time": 0.96,
    "budget": 0.82
  },
  "itinerary": [
    {
      "start": "14:00",
      "end": "15:30",
      "type": "activity",
      "title": "安静咖啡馆聊天",
      "reason": "室内、轻松，适合两人下午放松。",
      "cost": "人均 80-120 元"
    }
  ],
  "variants": [
    {
      "id": "variant_cafe",
      "kind": "main",
      "title": "咖啡馆聊天",
      "summary": "找一家安静咖啡馆，适合坐下来聊天放松。",
      "score": 91,
      "estimated_budget": 120,
      "itinerary": [
        {
          "start": "14:00",
          "end": "15:30",
          "type": "activity",
          "title": "安静咖啡馆聊天",
          "reason": "室内、轻松，适合两人下午放松。",
          "cost": "人均 80-120 元"
        }
      ]
    }
  ],
  "badges": ["室内", "两人"]
}
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Backend health check |
| `GET` | `/api/llm/status` | LLM configuration and connectivity status |
| `POST` | `/api/runs` | Create a run from a user goal |
| `GET` | `/api/runs/{run_id}` | Read current run status |
| `GET` | `/api/runs/{run_id}/events` | Stream named `run.event` SSE frames |
| `POST` | `/api/runs/{run_id}/clarifications` | Submit the answer for the current question |
| `POST` | `/api/runs/{run_id}/actions/approve` | Execute selected pending actions |
| `POST` | `/api/runs/{run_id}/actions/reject` | Reject the current approval-required run |
| `GET` | `/api/plans` | List persisted plan summaries |
| `GET` | `/api/plans/{plan_id}` | Read the persisted plan snapshot |
| `GET` | `/api/tool-schemas` | Inspect tool/action schemas |

Important run statuses:

- `queued`
- `running`
- `needs_clarification`
- `approval_required`
- `executing`
- `completed`
- `rejected`
- `failed`

Important SSE event types:

- `run.started`
- `run.running`
- `agent.started`
- `agent.completed`
- `clarification.required`
- `approval.required`
- `actions.execution.started`
- `actions.execution.completed`
- `run.completed`
- `run.failed`
- `run.rejected`

## Quick Start

### Requirements

- Node.js 18+
- Python 3.11+
- `uv`

### Install

```bash
npm install
uv sync
```

### Configure LLM

Copy the example environment file and set your OpenAI-compatible model endpoint.

```bash
cp .env.example .env
```

Typical remote configuration:

```env
LLM_PROVIDER=mimo
LLM_API_PROTOCOL=openai
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
LLM_API_KEY=replace-with-your-full-key
LLM_MODEL=MiMo-V2.5-Pro
LLM_TIMEOUT_SECONDS=90
LLM_REMOTE_ENABLED=true
LLM_RESPONSE_FORMAT=json_object
LLM_DISABLE_THINKING=true
LLM_TRUST_ENV_PROXY=false
```

`LLM_REMOTE_ENABLED=true` is the intended product demo mode. If the model returns invalid JSON or an incomplete plan, the run fails by design.

### Run Frontend And Backend

```bash
npm run dev:full
```

Or run them separately:

```bash
npm run dev
npm run dev:backend
```

Frontend:

```text
http://127.0.0.1:4174
```

Backend OpenAPI docs:

```text
http://127.0.0.1:8787/docs
```

## Tests

```bash
npm run test:all
npm run build
npm run test:e2e
```

Focused commands:

```bash
npm run test:contracts
npm run test:frontend
npm run test:backend
uv run pytest tests/backend/test_openai_agents_runtime.py -q
```

The backend runtime tests cover:

- one-question-at-a-time clarification,
- no repeated intent extraction while consuming the clarification queue,
- `FinalValidationTool` running once after the queue is complete,
- structured planner JSON being merged into the plan contract,
- non-structured planner output failing with `planner_contract_invalid`,
- approval and execution identity handling.

## Project Layout

```text
app/                    Next.js app entry
components/             React UI components
components/chat/        Chat and clarification UI
components/plan/        Plan workbench, variants, evidence, ledger
features/runs/          REST/SSE run client, reducer, controller
features/plans/         Plan list/detail API client
lib/contracts/          Zod schemas for frontend/backend contract tests
types/                  Shared TypeScript types

backend/api/            FastAPI app, routes, schemas
backend/application/    Run lifecycle and approval services
backend/agents/         OpenAI Agents SDK runtime and tools
backend/domain/         Run/domain constants and models
backend/infrastructure/ SQLite repositories and event persistence
backend/llm/            OpenAI-compatible LLM config
backend/tools/          Local side-effect adapters and registry

tests/contracts/        API/schema contract tests
tests/frontend/         React/reducer/client tests
tests/backend/          Pytest backend tests
tests/e2e/              Playwright browser flows
```

## Data And Persistence

Local workflow state is written under:

```text
.weekendpilot/workflow.sqlite
.weekendpilot/profiles.sqlite
```

These SQLite files store runs, events, plan snapshots, approvals, receipts, and user profile data for local demo use.

## Safety Model

- Planner output is data, not executable authority.
- Pending actions are inert until approval.
- `approve` requires explicit selected action ids.
- Execution uses idempotency-aware local adapters.
- Receipts are persisted and shown back to the user.
- Invalid planner output fails loudly instead of silently producing an empty or misleading plan.
