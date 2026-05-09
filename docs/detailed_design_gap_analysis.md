# Detailed Design Alignment Closure Report

检查时间：2026-05-09  
范围：`detailed_design.md` 全 20 节与当前 WeekendPilot 实现

## Closure Matrix

| Area | Status | Evidence | Verification command |
|---|---|---|---|
| 本地生活执行型定位 | closed | Next.js 主路径、半日场景入口、执行回执、恢复流程 | `npm run test:e2e` |
| 四类核心场景 | closed | `family`、`friends`、`date`、`rainy_indoor` prompt、seed、ranking、recovery 覆盖 | `npm run test:frontend && npm run test:server` |
| Next.js API 主路径 | closed | `/api/plans/*`、`/api/tool-schemas`、`/api/traces/*` 连接前端 | `npm run test:server` |
| LangGraph workflow 与 checkpoint 边界 | closed | `lib/agent/graph.ts`、`lib/data/repositories/checkpointRepository.ts` | `npm run test:server -- tests/server/observability-persistence.test.ts` |
| OpenAI Responses / Agents 边界 | closed | `lib/agent/openai/*`、`lib/agent/agents.ts`，带确定性 fallback | `npm run test:server -- tests/server/openai-agent-integration.test.ts` |
| MCP-ready 工具 | closed | 15 个工具注册、schema、side-effect metadata、回执 | `npm run test:server -- tests/server/tool-registry.test.ts` |
| PostGIS-ready 数据平台 | closed | migrations、JSON seed、repositories、seed tests | `npm run test:server -- tests/server/data-platform.test.ts` |
| 多目标排序与过滤 | closed | 权重公式、硬过滤、grounded explanation、variants | `npm run test:server -- tests/server/ranking-filtering.test.ts` |
| 一屏 Planner UI | closed | 输入、约束、trace、时间轴、地图、variants、底部执行 | `npm run test:frontend && npm run test:e2e` |
| 地图与路线 | closed | local route provider、Mapbox-ready fallback map、mobile summary | `npm run test:frontend -- tests/frontend/route-map.test.tsx` |
| 七类失败恢复 | closed | restaurant/activity/rain/route/budget/conflict/timeout policies | `npm run test:server -- tests/server/recovery-matrix.test.ts` |
| 商业执行闭环 | closed | TKT/RES/CPN/ORD/MSG/CAL 六类回执 | `npm run test:frontend -- tests/frontend/commercial-loop.test.tsx` |
| Guardrails 与隐私 | closed | 已确认快照、禁止未知 place id、trace 隐私脱敏 | `npm run test:server -- tests/server/guardrails.test.ts` |
| Observability persistence | closed | OTEL no-op 边界、trace/checkpoint repositories | `npm run test:server -- tests/server/observability-persistence.test.ts` |
| Desktop/mobile/performance E2E | closed | Playwright desktop、mobile、10 秒性能测试 | `npm run test:e2e` |
| Legacy mock drift | closed | 产品主路径不再导入 `src/agent.mjs`，旧 mock 仅在 fixture | `npm run test:frontend -- tests/frontend/no-main-path-mock.test.ts` |

## Partially Closed

| Area | Status | Accepted remaining risk | Verification command |
|---|---|---|---|
| 真实外部 API 接入 | partially closed | 作品稳定性优先，真实美团/地图/支付/消息接口由 MCP-ready adapters 和本地 provider 代表；替换真实 provider 不改变 workflow/UI contract | `npm run test:server -- tests/server/tool-registry.test.ts` |
| OpenTelemetry export | partially closed | 当前实现为 env-controlled no-op 边界，未配置 OTLP endpoint 时不发外部数据；真实 collector 接入保留在 `lib/observability/otel.ts` 边界 | `npm run test:server -- tests/server/observability-persistence.test.ts` |
| Python backend | partially closed | Python backend 保留为迁移前参考实现，不是主演示路径；继续保证 legacy tests 通过 | `uv run pytest tests/backend` |
| Browser fallback | partially closed | 当前通过 Playwright/Chrome 验证演示链路；真实商家网页自动操作未作为稳定主路径 | `npm run test:e2e` |

## Accepted Remaining Risk

| Risk | Decision | Mitigation |
|---|---|---|
| 真实交易不可在评审现场稳定执行 | 接受 | 所有副作用动作返回机器可验证模拟回执，并强制确认 |
| 外部 LLM/API 可能不可用 | 接受 | OpenAI/Responses 边界提供 deterministic fallback，测试默认不依赖网络 |
| 地图真实路况与本地矩阵可能不同 | 接受 | route provider 抽象保留真实服务替换点，UI 展示来源 |
| Dev-route 运行态状态仍为本地 cache | 接受至 Task 18 repository 边界 | checkpoint/trace repository 已建立，后续可接 PostgreSQL runtime |

## Final Verification Commands

```bash
npm run test:all
uv run pytest tests/backend
npm run build
git status --short
```
