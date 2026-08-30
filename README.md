# 好办 · Local Life Agent

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js 16](https://img.shields.io/badge/Next.js%2016-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![React 19](https://img.shields.io/badge/React%2019-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev/)
[![Google ADK](https://img.shields.io/badge/Google%20ADK-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://google.github.io/adk-docs/)
[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-111827?style=for-the-badge)](https://modelcontextprotocol.io/)
[![Temporal](https://img.shields.io/badge/Temporal-000000?style=for-the-badge)](https://temporal.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)

> **你说想要，剩下好办。**
>
> 好办是一个面向美团本地生活供给的“意图到履约” Agent。用户描述想达成的生活结果，例如“今晚下班后想和朋友放松，预算 500 元，不想排队，23:00 前到家”；系统澄清关键分歧、核验供给、组合可行路线，并在用户授权后完成预约、购券、购票、下单、导航、叫车和异常恢复。

它不是通用聊天助手，也不是自然语言搜索框。项目把一件跨业务的生活事务，建模为可解释、可编辑、可授权、可履约的任务；聊天只是修改任务状态的一种入口。

## ✨ 核心能力

| 用户问题 | 当前实现 |
| --- | --- |
| “今晚怎么才能真正放松？” | `IntentGovernor` 理解目标、场景与约束，而不是按关键词路由到固定品类。 |
| “预算、时间、地点能同时满足吗？” | `PlanningModule` 使用 OR-Tools 从已核验供给中求解预算、容量、时间窗、路线与依赖。 |
| “为什么推荐这条路线？” | `LifeGoalPlanner` 只在 Pareto 前沿中选择方案，并为每个供给节点给出理由。 |
| “能直接帮我办吗？” | `ExecutionMandate` 先确认代办范围；支付类动作还需要 `TransactionConfirmation`。 |
| “满位、涨价、迟到怎么办？” | 供给观察会优先应用 `FallbackPolicy`，无候补时只生成受影响节点的 `PlanPatch`。 |

## 🗺️ 系统架构设计

项目采用前后端分离、能力目录驱动、任务状态持久化和 Temporal 履约工作流相结合的架构。

![好办系统架构图](docs/assets/system-architecture.png)

### 🖥 前端：Next.js 16 + React 19 任务工作台

- `app/page.tsx` 直接加载 `components/Workbench.tsx`，以移动优先的单列界面承载整个任务过程。
- `frontend/useLifeTask.ts` 负责创建任务、发送消息、编辑目标和计划、提交授权与交易确认。
- `frontend/api.ts` 通过 REST 操作任务，并用 SSE 订阅 `task` 与 `progress` 事件，及时展示后台真实阶段。
- 用户可以锁定目标字段，切换约束的“必须/尽量”，或替换、删除和调整计划中的单个节点。

### ⚙️ 后端：FastAPI + TaskModule

- `backend/api/app.py` 在启动时组装任务、决策、供给、规划、偏好、记忆和履约模块。
- `backend/tasks/module.py` 维护 `TaskSnapshot`、revision、消息、澄清、目标编辑、计划编辑、授权、现实事件和结果回访。
- 创建任务会立即返回 `202` 和初始快照；Agent 在后台推进。新的用户输入会取消未形成外部承诺的旧决策轮。
- 每个任务使用异步锁和 revision 检查，PostgreSQL `DocumentStore` 通过乐观并发控制阻止旧状态覆盖新状态。

### 🧠 智能决策：Google ADK + DeepSeek V4 Flash

- `IntentGovernor` 输出 `IntentFrame`：目标契约、最小能力集合、查询计划、时间约束和可能的单问澄清分支。
- `CapabilityQueryOrchestrator` 从运行时 Capability Catalog 选择工具并并行取得供给证据。
- `LifeGoalPlanner` 只从 OR-Tools 认证的 Pareto 候选中输出 `CandidateSelection`，最多保留两个有实际取舍的备选。
- 模型不负责生成价格、库存、场次、路线、动作或授权。它们由确定性模块根据供给事实物化为 `PlanGraph` 和 `PlanPolicy`。

### 🔌 Supply MCP、Temporal 与 PostgreSQL

- `backend/mcp/server.py` 是独立的 Streamable HTTP MCP 服务，发布餐饮、娱乐、到店服务、即时配送、出行五类能力及统一生命周期工具。
- `backend/mcp/capabilities.json` 定义能力可用工具、所需上下文、规划语义、观察信号、变更动作、补偿动作和完成证据。
- `backend/supply/` 维护供给孪生；本地 `local_catalog.json` 可模拟价格、库存、时段和订单状态变化，让 Demo 稳定复现。
- `backend/fulfillment/temporal.py` 使用 Temporal 运行履约和现场观察工作流；PostgreSQL 保存任务、revision、偏好、供给状态、回执与 ADK Session。

## 🔄 从规划到履约

好办交付的不是一份静态推荐，而是一条能随着现场变化持续推进的任务流。

![好办规划与履约流程图](docs/assets/fulfillment-flow.png)

1. **创建任务**：`POST /api/tasks` 创建任务并进入 `understanding`，前端无需等待模型完成。
2. **理解与澄清**：仅当不同答案会改变能力、可行性、硬约束、目的地或授权时，系统展示一个反事实分支问题。
3. **供给核验**：Capability Query Orchestrator 按目录并行调用 MCP，得到带版本和证据的 `GroundedCandidateSet`。
4. **可行性求解**：OR-Tools 生成 `FeasiblePlanSet` 和 Pareto 候选；无解时给出经验证的最小约束调整。
5. **物化计划**：LifeGoalPlanner 做语义取舍，PlanningModule 生成包含节点、依赖、证据、候补和授权边界的 `PlanPolicy`。
6. **两级确认**：先批准 `ExecutionMandate`，再确认支付类 `TransactionConfirmation`。
7. **履约与恢复**：Temporal 依序执行命令；满位、价格变化、司机取消和用户迟到优先走候补，必要时才局部重规划。

## 📦 核心领域对象

| 对象 | 说明 |
| --- | --- |
| `GoalContract` | 用户与 Agent 对结果、事实、约束、假设、开放问题和锁定字段的共同理解。 |
| `IntentFrame` | 从自然语言意图到供给与规划阶段的强类型交接。 |
| `GroundedCandidateSet` | 某项能力检索到的、带供给证据和版本的候选集合。 |
| `FeasiblePlanSet` | 求解器生成的可行组合、Pareto 前沿及不可行原因。 |
| `PlanGraph` | 包含生活节点、依赖、价格、证据与承诺状态的版本化计划。 |
| `PlanPolicy` | 主计划、候补、触发条件、决策时点和授权影响组成的执行策略。 |
| `FulfillmentCommand` | 已获用户确认、要求外部世界发生变化的强类型命令。 |
| `FulfillmentEvent` | 预约、支付、取消、退款、到达或完成后产生的持久回执。 |

## 🔐 安全与可控设计

- Agent 输出的是决策数据，不具备直接执行权限。
- 每项供给的工具、生命周期、观察信号、变更和补偿边界由 Capability Catalog 发布。
- 供给提交前经过 `verified -> quoted -> held -> committed` 生命周期，并在关键时刻刷新。
- 授权与支付分离；支付、购票、下单和叫车必须经过第二次确认。
- 新输入产生新 revision，已完成或已承诺节点必须保留或显式补偿。
- 接口调用成功不等于现实完成；完成状态需要供给状态、核销、到达或用户确认等完成证据。

## 🔌 API 概览

| 方法 | 端点 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 检查模型、MCP、Temporal 与供给世界状态。 |
| `POST` | `/api/tasks` | 创建异步本地生活任务。 |
| `GET` | `/api/tasks/{task_id}` | 获取最新任务快照。 |
| `POST` | `/api/tasks/{task_id}/messages` | 补充目标并触发新决策轮。 |
| `POST` | `/api/tasks/{task_id}/decisions` | 提交澄清分支选择。 |
| `PATCH` | `/api/tasks/{task_id}/goal` | 编辑目标契约、锁定字段或调整约束强度。 |
| `POST` | `/api/tasks/{task_id}/plan-edits` | 局部编辑、锁定、替换或移除计划节点。 |
| `POST` | `/api/tasks/{task_id}/mandate` | 批准代办范围并执行非交易命令。 |
| `POST` | `/api/tasks/{task_id}/transaction` | 确认交易命令。 |
| `GET` | `/api/tasks/{task_id}/events` | 订阅 `task` 与 `progress` SSE 事件。 |
| `POST` | `/api/tasks/{task_id}/reality-events` | 报告满位、涨价、迟到、到达或完成等现实事件。 |
| `POST` | `/api/tasks/{task_id}/compensations` | 发起取消、退款等补偿操作。 |
| `GET` | `/api/preferences` | 读取结构化偏好事实。 |
| `PATCH` | `/api/preferences/{fact_id}` | 修订或删除一条偏好事实。 |

完整 OpenAPI 文档：`http://127.0.0.1:8787/docs`。

## 🚀 快速开始

### 环境要求

- Docker Compose
- Node.js 22+
- Python 3.11+
- `uv`
- DeepSeek API Key

### 配置

```bash
cp .env.example .env
```

在 `.env` 中设置 `DEEPSEEK_API_KEY`。本地服务默认使用：

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8787
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled
DATABASE_URL=postgresql+asyncpg://locallife:locallife@127.0.0.1:55432/locallife
TEMPORAL_ADDRESS=127.0.0.1:7233
SUPPLY_MCP_URL=http://127.0.0.1:8790/mcp
```

### 一键启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端工作台 | `http://127.0.0.1:4174` |
| 后端健康检查 | `http://127.0.0.1:8787/api/health` |
| 后端 OpenAPI | `http://127.0.0.1:8787/docs` |
| Supply MCP | `http://127.0.0.1:8790/mcp` |

### 分别启动开发服务

```bash
uv sync
npm install
docker compose up postgres temporal supply-mcp
```

在另外两个终端中启动后端和前端：

```bash
uv run uvicorn backend.api.app:app --host 127.0.0.1 --port 8787
npm run dev
```

## 🧪 测试与验收

```bash
npm test
npm run build
npm run test:e2e
uv run python scripts/run_generalization_acceptance.py
```

测试覆盖异步任务与 SSE、单问澄清、MCP 工具面、供给与路线证据、可行性求解、计划编辑、两级授权、Temporal 履约、异常恢复和移动端工作台。

## 📁 项目结构

```text
app/                         Next.js 应用入口和全局样式
components/Workbench.tsx     移动优先的任务工作台
frontend/                    REST 客户端、SSE 订阅与 TypeScript 类型

backend/api/                 FastAPI 应用、任务 API 和 SSE 事件流
backend/agent/               Google ADK 意图理解、追问与规划决策
backend/domain/              强类型领域模型和任务状态
backend/mcp/                 能力目录、MCP 服务、查询编排与资源
backend/supply/              供给孪生、生命周期、外呼与本地供给样本
backend/planning/            OR-Tools 可行性求解、计划物化与恢复
backend/tasks/               任务生命周期、revision、编辑、授权和现场事件
backend/preferences/         结构化偏好事实及其演化
backend/memory/              ADK Memory 服务
backend/fulfillment/         Temporal 履约与实时观测工作流
backend/live/                现场生活伴侣状态
backend/storage/             PostgreSQL 与内存文档存储

docs/assets/                 README 系统架构图与流程图
tests/backend/               Agent、API、MCP、供给、求解和任务测试
tests/e2e/                   Playwright 工作台端到端测试
tests/acceptance/            泛化验收场景
scripts/                     验收脚本
```

## 🧭 本地演示说明

`backend/supply/local_catalog.json` 是供给孪生的本地样本，可通过 `SUPPLY_CATALOG_PATH` 切换为供给方拥有的目录。`/api/world/scenarios/*` 只用于演示，可注入餐厅满位、演出售罄、价格上涨和司机取消；Agent 本身无法调用这些世界控制动作。

Docker Compose 使用 PostgreSQL volume 持久化任务、revision、偏好、供给状态、回执和 ADK Session。开发与测试可设置 `USE_IN_MEMORY_STORE=true`，在不连接 PostgreSQL 的情况下运行内存存储。
