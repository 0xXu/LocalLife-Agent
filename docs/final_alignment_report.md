# WeekendPilot 当前对齐报告

## 结论

当前 Demo 已切换为前后端分离版本：Next.js 只承载前端界面，FastAPI 是唯一后端服务。旧 Next.js API Routes、TypeScript backend workflow、旧 mock agent 和相关 server tests 已清理。

## 当前主链路

```text
app/page.tsx
  -> features/planner/apiClient.ts
  -> lib/api/client.ts
  -> http://127.0.0.1:8787/api/*
  -> backend.services.PlanningService
  -> backend.orchestrator.PlanningPipeline
  -> backend.tools/*
```

## 保留模块

- `backend/`：唯一后端。
- `components/`：产品界面。
- `features/planner/apiClient.ts`：前端 API 客户端。
- `features/planner/uiFixtures.js`：静态展示数据，不参与主规划逻辑。
- `lib/contracts/schemas.ts`、`types/weekendpilot.ts`：前端契约类型。
- `lib/observability/tracing.ts`：前端 trace 归一化。
- `lib/routing/routeProvider.ts`：前端路线展示类型。

## 验证命令

```bash
npm run test:all
npm run build
uv run pytest tests/backend -q
```
