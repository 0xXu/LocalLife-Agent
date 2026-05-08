# WeekendPilot Backend

这是周末管家 Demo 的分层后端实现。前端保持现有静态 Demo 不变，后端按 `api / models / agents / tools / orchestrator / services / llm` 拆分，使用确定性 Mock tools 完成规划、确认执行、回执生成和失败恢复。

## 分层结构

```text
backend/
  api/              HTTP JSON API，基于标准库 http.server
  models/           领域 schema、PlanState、前端响应转换
  agents/           Intent、Context、Search、Rank、Route、Validate、Execute、Recovery
  tools/            POI、可订性、路线、执行回执、trace store
  orchestrator/     Pipeline、ParallelExecutor 占位、RecoveryLoop
  services/         PlanningService 应用门面
  llm/              OpenAI-compatible LLM 配置和客户端
  data/             本地生活 POI 种子数据
```

## 运行后端

PowerShell / Windows:

```powershell
python -m backend.api.app
```

Bash:

```bash
python -m backend.api.app
```

默认地址：

```text
http://127.0.0.1:8787
```

## 环境变量

复制 `.env.example` 为 `.env`，填入你的完整 key：

```env
LLM_PROVIDER=mimo
LLM_API_PROTOCOL=openai
LLM_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1
LLM_API_KEY=replace-with-your-full-dedicated-api-key
LLM_MODEL=MiMo-V2.5-Pro
```

`.env` 已被 git 忽略。API 只会返回 `configured/missing`，不会返回真实 key。

## API

```text
GET  /api/health
GET  /api/llm/status
POST /api/plans/build
POST /api/plans/{plan_id}/execute
POST /api/plans/{plan_id}/recover
GET  /api/traces/{plan_id}
```

PowerShell 示例：

```powershell
$body = @{
  goal = "今天下午想和老婆孩子出去玩几个小时，孩子5岁，老婆减脂，别太远"
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8787/api/plans/build `
  -ContentType 'application/json' `
  -Body $body
```

朋友场景示例：

```powershell
$body = @{
  goal = "今天下午朋友4个人出去玩，2男2女，别太远"
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8787/api/plans/build `
  -ContentType 'application/json' `
  -Body $body
```

## 测试

```powershell
python -m unittest discover -s tests/backend -p "test_*.py"
node --test tests/*.test.mjs
python -m compileall backend
```
