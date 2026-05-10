# WeekendPilot 本地生活 Demo

WeekendPilot 是一个前后端分离的本地生活规划 Demo。前端只负责 Next.js 页面渲染，后端由 FastAPI 提供唯一 API 服务，并保留 Python 侧的 services、orchestrator、agents、tools、models 逻辑。

## 运行方式

后端：

```bash
npm run dev:backend
```

默认地址：

```text
http://127.0.0.1:8787
```

前端：

```bash
npm run dev
```

默认地址：

```text
http://127.0.0.1:4174
```

同时启动：

```bash
npm run dev:full
```

前端通过 `NEXT_PUBLIC_API_URL` 调用后端；默认后端地址为 `http://127.0.0.1:8787`。FastAPI 文档在 `http://127.0.0.1:8787/docs`。

## API

Python FastAPI 后端提供以下接口：

```text
GET  /api/health
GET  /api/llm/status
GET  /api/tool-schemas
POST /api/plans/build
GET  /api/plans/{plan_id}
PATCH /api/plans/{plan_id}/constraints
POST /api/plans/{plan_id}/alternatives
POST /api/plans/{plan_id}/confirm
POST /api/plans/{plan_id}/execute
POST /api/plans/{plan_id}/recover
GET  /api/traces/{plan_id}
```

## 测试

```bash
npm run test:frontend
npm run test:contracts
npm run test:backend
npm run build
```

完整快速回归：

```bash
npm run test:all
```

## 项目结构

- `app/page.tsx`：Next.js 前端入口。
- `app/globals.css`：产品界面样式与响应式布局。
- `components/`：首页、计划工作台、保存计划、最近执行、偏好设置和 trace 展示组件。
- `features/planner/apiClient.ts`：统一调用 Python 后端的前端 API 客户端。
- `features/planner/uiFixtures.js`：仅用于首页场景、保存计划和最近执行的静态展示数据。
- `lib/api/client.ts`：`NEXT_PUBLIC_API_URL` 封装。
- `lib/contracts/schemas.ts` 与 `types/weekendpilot.ts`：前端共享的响应类型与契约。
- `backend/`：FastAPI 后端和 Python 规划 pipeline。
- `tests/backend/`：Python 后端回归测试。
- `tests/frontend/`：前端组件和交互测试。
- `tests/contracts/`：前后端响应契约测试。

## 当前架构边界

旧版 Next.js API Routes 和 TypeScript 后端 workflow 已清理。当前主链路是：

```text
Next.js UI -> lib/api/client.ts -> FastAPI /api/* -> backend.services.PlanningService -> backend.orchestrator.PlanningPipeline -> backend.tools/*
```

当 `LLM_REMOTE_ENABLED=true` 时，`LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_MODEL` 必须可用。远程 LLM 超时、返回非 JSON 或请求失败都会中断 `/api/plans/build` 并返回错误，不再降级到确定性模板。
