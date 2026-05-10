# 周末管家本地生活演示

## Frontend / Backend Separation

The app now runs as two services:

- Backend: FastAPI on `http://127.0.0.1:8787`
- Frontend: Next.js on `http://127.0.0.1:4173`

Start the backend:

```bash
uvicorn backend.api.app:app --host 127.0.0.1 --port 8787
```

Start the frontend:

```bash
npm run dev
```

Or start both in one terminal:

```bash
npm run dev:full
```

Frontend API calls use `NEXT_PUBLIC_API_URL`; `.env.example` defaults it to `http://127.0.0.1:8787`. FastAPI docs are available at `http://127.0.0.1:8787/docs` and OpenAPI JSON at `http://127.0.0.1:8787/openapi.json`.

周末管家是一个可运行的本地生活 Hackathon 演示项目。它不是普通推荐列表，而是一个执行型助手：用户输入一句自然语言目标，系统理解约束、生成半日行程、展示规划过程，并在用户确认后返回活动预约、餐厅订座和计划发送回执。

## 快速运行

前端使用 Next.js。先安装 Node 依赖：

```bash
npm install
```

安装完成后，在项目根目录启动开发服务：

```bash
npm run dev
```

然后打开：

```text
http://127.0.0.1:4173
```

如果端口被占用，请在 `package.json` 中调整 `dev` 脚本端口。停止服务使用 `Ctrl + C`。

## 测试

```bash
npm test
```

后端 pytest：

```bash
uv run pytest tests/backend
```

## 后端服务

当前仓库额外提供了分层 Python 后端。后端参考多 Agent travel planner 的 `api / models / agents / tools / orchestrator / services` 分层，并按本项目详细设计文档实现本地生活规划 Pipeline。

主体验通过 Next.js API + LangGraph workflow + MCP-ready tools 运行。Python backend 是迁移前的参考实现，不是主演示路径。

启动后端：

```bash
python -m backend.api.app
```

默认地址：

```text
http://127.0.0.1:8787
```

后端接口：

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

后端测试：

```bash
python -m unittest discover -s tests/backend -p "test_*.py"
```

## 演示脚本

1. 在首页输入周末目标或选择场景卡片，然后点击 **生成计划**。
2. 展示系统识别到的人群、时长、饮食、半径和交通方式。
3. 在规划页查看理解需求、筛选活动、匹配餐厅、规划路线和确认可订时间。
4. 展示今日下午行程和右侧计划概览。
5. 点击 **确认执行**，展示 `TKT-*`、`RES-*`、`MSG-*` 模拟回执。
6. 点击 **模拟餐厅无位**，展示餐厅无位后的局部替换方案。

## MCP-ready 工具

主演示路径保留详细设计定义的 15 个 MCP-ready 工具能力，界面中以中文标签展示规划、路线、优惠、订单、日历、分享和恢复过程：

- `parse_user_goal`
- `get_weather`
- `search_places`
- `search_restaurants`
- `check_availability`
- `optimize_route`
- `build_itinerary`
- `validate_plan`
- `compare_alternatives`
- `reserve_activity`
- `create_reservation`
- `claim_coupon`
- `create_order`
- `send_plan_message`
- `create_calendar_event`

这些工具通过 TypeScript 适配器和确定性本地 Provider 运行，副作用工具必须经过确认快照后执行，后续可以替换成真实美团、地图、订座、订单和消息适配器。

## 项目结构

- [app/page.tsx](./app/page.tsx)：Next.js 前端入口。
- [app/api](./app/api)：Next.js API 主路径，连接 planner workflow、工具 Schema、执行和恢复接口。
- [app/globals.css](./app/globals.css)：中文产品化界面样式。
- [components](./components)：前端页面、导航、规划、保存计划、最近执行和设置组件。
- [features/planner/mockAgent.js](./features/planner/mockAgent.js)：首页场景、保存计划和最近执行的展示数据，不再承载主规划 Agent。
- [lib/agent](./lib/agent)：LangGraph 风格 workflow、状态节点、计划构建、执行和恢复编排。
- [lib/tools](./lib/tools)：MCP-ready 工具注册、适配器、幂等回执和副作用边界。
- [lib/data](./lib/data)：PostGIS-ready 数据模型、迁移、种子数据和 repository。
- [src/agent.mjs](./src/agent.mjs)：迁移前确定性 mock，仅供历史测试 fixture 使用。
- [data/poi.json](./data/poi.json)：中文种子地点数据。
- [tests/agent.test.mjs](./tests/agent.test.mjs)：行为测试。
- [tests/fixtures/legacyMockAgent.mjs](./tests/fixtures/legacyMockAgent.mjs)：旧 mock Agent 的历史测试入口。
- [tests/backend](./tests/backend)：后端 pytest 测试。
- [pyproject.toml](./pyproject.toml)：`uv` 项目配置。
- [uv.lock](./uv.lock)：`uv` 锁定文件。
- [design_submission.md](./design_submission.md)：精简提交文档。

## 当前状态

当前版本是稳定的中文产品化 Demo。普通用户默认通过 Next.js API 触发 LangGraph workflow，看到约束、计划、路线、确认动作、商业回执和失败恢复；评委可以展开“Agent 执行轨迹”检查 MCP-ready 工具链。
