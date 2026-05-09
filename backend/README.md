# WeekendPilot Complete Local Backend

This Python backend is retained as a legacy reference for the earlier local demo. The production demo path is the Next.js TypeScript API and LangGraph workflow.

This backend implements the complete local product flow described in `detailed_design.md` as a migration reference.

## Architecture

```text
api/              stdlib HTTP JSON API
services/         plan lifecycle facade
orchestrator/     central state-machine planner
models/           dataclass domain models and API DTO helpers
tools/            MCP-ready local tool adapters
data/             deterministic local catalog generator
llm/              OpenAI-compatible config/client with deterministic fallback
```

The backend is intentionally local-first for competition stability. Meituan, map, booking, ordering, messaging, and calendar actions are represented by replaceable local adapters that return realistic IDs and receipts.

## LLM Configuration

Copy `.env.example` to `.env` and fill the full key:

```env
LLM_PROVIDER=mimo
LLM_API_PROTOCOL=openai
LLM_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1
LLM_API_KEY=replace-with-your-full-dedicated-api-key
LLM_MODEL=MiMo-V2.5-Pro
LLM_REMOTE_ENABLED=false
```

`LLM_REMOTE_ENABLED=false` keeps demos deterministic and avoids accidental token usage. Set it to `true` to let the intent parser try the remote model first; invalid responses or network failures automatically fall back to deterministic parsing and are marked in trace.

## API

```text
GET   /api/health
GET   /api/llm/status
GET   /api/tool-schemas
POST  /api/plans/build
GET   /api/plans/{plan_id}
PATCH /api/plans/{plan_id}/constraints
POST  /api/plans/{plan_id}/alternatives
POST  /api/plans/{plan_id}/confirm
POST  /api/plans/{plan_id}/execute
POST  /api/plans/{plan_id}/recover
GET   /api/traces/{plan_id}
```

Sensitive tools always require confirmation. `execute` with `confirmed=false` returns `confirmation_required`.

## Run

```powershell
python -m backend.api.app
```

Default URL:

```text
http://127.0.0.1:8787
```

## Smoke Examples

```powershell
$body = @{
  goal = "今天下午想和老婆孩子出去玩几个小时，孩子5岁，老婆减脂，别太远"
} | ConvertTo-Json -Depth 10

$plan = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8787/api/plans/build `
  -ContentType 'application/json' `
  -Body $body

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8787/api/plans/$($plan.plan.id)/confirm" `
  -ContentType 'application/json' `
  -Body '{"confirmed":true}'

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8787/api/plans/$($plan.plan.id)/execute" `
  -ContentType 'application/json' `
  -Body '{"confirmed":true}'
```

## Test

```powershell
python -m unittest discover -s tests/backend -p "test_*.py"
node --test tests/*.test.mjs
python -m compileall backend
```
