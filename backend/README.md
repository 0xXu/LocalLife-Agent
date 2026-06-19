# WeekendPilot OpenAI Agents SDK Backend

This Python backend is the single backend service for the separated WeekendPilot app. The Next.js app is frontend-only and calls these `/api/*` endpoints through `NEXT_PUBLIC_API_URL`.

This backend is the production API path for the current demo.

## Architecture

```text
api/              FastAPI JSON/SSE API with OpenAPI docs
application/      run, approval, and plan lifecycle services
agents/           OpenAI Agents SDK runtime, guardrails, memory, and local tool bridge
domain/           run and event domain models
infrastructure/   SQLite-backed run event store
models/           dataclass domain models and API DTO helpers
tools/            local tool adapters with side-effect metadata
data/             deterministic local catalog generator
llm/              OpenAI-compatible config/client for remote model access
```

The backend is intentionally local-first for competition stability. The OpenAI Agents SDK runtime owns model/tool execution, while application services persist run state, plan snapshots, action approvals, receipts, and normalized SSE events in SQLite. Meituan, map, booking, ordering, messaging, and calendar actions are represented by replaceable local adapters that return realistic IDs and receipts.

## LLM Configuration

Copy `.env.example` to `.env` and fill the full key:

```env
LLM_PROVIDER=mimo
LLM_API_PROTOCOL=openai
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
LLM_API_KEY=replace-with-your-full-dedicated-api-key
LLM_MODEL=MiMo-V2.5-Pro
LLM_TIMEOUT_SECONDS=90
LLM_REMOTE_ENABLED=true
LLM_RESPONSE_FORMAT=json_object
LLM_DISABLE_THINKING=true
LLM_TRUST_ENV_PROXY=false
```

The product demo should run with `LLM_REMOTE_ENABLED=true`. For MiMo Token Plan, use the exact regional Base URL shown on your subscription page, such as `token-plan-cn`, `token-plan-sgp`, or `token-plan-ams`; a valid `tp-` key returns `401 Invalid API Key` when sent to the wrong regional cluster. For the MiMo reasoning model, keep `LLM_RESPONSE_FORMAT=json_object` and `LLM_DISABLE_THINKING=true` so intent parsing receives JSON in `message.content` instead of exhausting the token budget in `reasoning_content`. If the remote model times out, returns invalid JSON, or is misconfigured, plan building stops with an error response instead of falling back to a deterministic template.
By default, LLM requests ignore system `http_proxy`/`https_proxy` variables because a broken local proxy can surface as a generic `Connection error`. Set `LLM_TRUST_ENV_PROXY=true` only when the MiMo endpoint must be reached through that proxy.

## API

```text
GET   /api/health
GET   /api/llm/status
GET   /api/tool-schemas
POST  /api/runs
GET   /api/runs/{run_id}
GET   /api/runs/{run_id}/events
POST  /api/runs/{run_id}/actions/approve
POST  /api/runs/{run_id}/actions/reject
GET   /api/plans/{plan_id}
```

`GET /api/runs/{run_id}/events` streams named `run.event` SSE frames. Event payloads use stable types such as `run.started`, `agent.started`, `tool.called`, `plan.draft.created`, `approval.required`, `actions.execution.completed`, `run.completed`, `run.failed`, and `run.rejected`.

Sensitive tools always require confirmation. The planning run emits `approval.required` with pending action ids, and execution only starts after `POST /api/runs/{run_id}/actions/approve`.

## Run

```powershell
uv run uvicorn backend.api.app:app --host 127.0.0.1 --port 8787
```

Default URL:

```text
http://127.0.0.1:8787
```

OpenAPI docs:

```text
http://127.0.0.1:8787/docs
http://127.0.0.1:8787/openapi.json
```

## Smoke Examples

```powershell
$body = @{
  goal = "今天下午想和老婆孩子出去玩几个小时，孩子5岁，老婆减脂，别太远"
} | ConvertTo-Json -Depth 10

$run = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8787/api/runs `
  -ContentType 'application/json' `
  -Body $body

$events = Invoke-WebRequest `
  -Uri "http://127.0.0.1:8787/api/runs/$($run.run_id)/events"

$plan = Invoke-RestMethod `
  -Method Get `
  -Uri "http://127.0.0.1:8787/api/plans/$($run.plan_id)"

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8787/api/runs/$($run.run_id)/actions/approve" `
  -ContentType 'application/json' `
  -Body (@{ action_ids = $plan.actions.action_id } | ConvertTo-Json -Depth 10)
```

## Test

```powershell
uv run pytest tests/backend
python -m compileall backend
```
