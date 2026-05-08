# WeekendPilot Backend

这是周末管家 Demo 的分层后端实现，前端保持现有静态 Demo 不变。后端按详细设计文档拆成 `api / models / agents / tools / orchestrator / services`，参考 multi-agent travel planner 的 Pipeline + 专门 Agent 思路，但针对本地生活场景做了确定性 Mock 实现。

## 分层结构

```text
backend/
  api/              HTTP JSON API，基于标准库 http.server
  models/           领域 schema 和 PlanState
  agents/           Intent、Context、Search、Rank、Route、Validate、Execute、Recovery
  tools/            POI、可订性、路线、执行回执、trace store
  orchestrator/     Pipeline、ParallelExecutor 占位、RecoveryLoop
  services/         PlanningService 应用门面
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

## API

```text
GET  /api/health
POST /api/plans/build
POST /api/plans/{plan_id}/execute
POST /api/plans/{plan_id}/recover
GET  /api/traces/{plan_id}
```

示例：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8787/api/plans/build `
  -ContentType 'application/json' `
  -Body '{"goal":"今天下午带 5 岁孩子出门，老婆减脂，别太远"}'
```

## 测试

```powershell
python -m unittest discover -s tests/backend -p "test_*.py"
```

如果 Node.js 可用，也可以继续运行前端行为测试：

```powershell
node --test tests/*.test.mjs
```

