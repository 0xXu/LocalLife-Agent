# WeekendPilot 当前差距记录

## 已完成

- Python 后端升级为 FastAPI，并提供 OpenAPI 文档。
- 前端通过 `NEXT_PUBLIC_API_URL` 访问 Python 后端。
- 旧 Next.js API Routes 已删除。
- 旧 TypeScript backend workflow、tool adapters、PostGIS-ready TS data layer 和迁移前 mock agent 已删除。
- 前端交互补齐：生成计划、语音反馈、全局搜索、最近执行、保存计划、偏好设置、移动端布局。
- 远程 LLM 可通过 OpenAI-compatible 配置启用，异常时后端 trace 会标记 deterministic fallback。

## 当前仍是 Demo 边界

- 美团、地图、订座、点单、消息和日历仍由本地工具模拟，不调用真实外部商户系统。
- 地图展示在未配置 Mapbox token 时使用 SVG fallback。
- 保存计划和最近执行是前端静态展示数据。

## 回归范围

```bash
npm run test:frontend
npm run test:contracts
npm run test:backend
npm run build
```
