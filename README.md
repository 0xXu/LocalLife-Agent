# 好办 · Local Life Agent

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js 16](https://img.shields.io/badge/Next.js%2016-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![React 19](https://img.shields.io/badge/React%2019-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev/)
[![Google ADK](https://img.shields.io/badge/Google%20ADK-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://google.github.io/adk-docs/)
[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-111827?style=for-the-badge)](https://modelcontextprotocol.io/)
[![Temporal](https://img.shields.io/badge/Temporal-000000?style=for-the-badge)](https://temporal.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)

“你说想要，剩下好办。”好办是一个面向美团本地生活供给形态的“意图到履约” Agent。用户只需描述想达成的生活结果，例如“今晚下班后想和朋友放松，预算 500 元，不想排队，23:00 前到家”；系统会澄清真正影响方案的歧义，组合餐饮、休闲娱乐、到店服务、即时配送和出行供给，解释关键取舍，并在两级确认后完成预约、购券、购票、下单、导航、叫车与异常恢复。

它不是通用聊天助手，也不是自然语言搜索框，而是围绕复杂本地生活目标进行跨业务编排和动态履约的任务型 Agent。任务、目标契约、计划、授权、供给证据和履约事件才是持久状态；聊天只是修改这些状态的一种输入方式。

## 当前原则

- **结果优先，而非品类优先**：先理解用户希望现实中发生什么，再判断需要哪些最小供给能力；不按关键词把请求硬路由到固定垂类。
- **一次只问一个高杠杆问题**：只有答案会改变能力集合、可行性、硬约束、目的地或授权范围时才追问；其余信息以可编辑假设继续推进。
- **模型负责语义，确定性模块负责事实**：Google ADK Agent 处理语义、偏好和取舍；供给、价格、库存、时间、路线、金额与履约动作由 MCP、领域模块和求解器提供或物化。
- **先求可行，再做推荐**：OR-Tools 先验证预算、时段、容量、依赖与移动等硬约束，并生成 Pareto 前沿；模型只能在已认证的候选中做语义选择。
- **候选不是义务**：供给检索结果只是证据。Planner 只选择实现目标所需的最小承诺，不因某类供给存在就扩张用户目标。
- **先授权，后交易**：规划不会直接产生真实副作用。用户先确认可代办范围，涉及支付、购票、下单和叫车时再逐项确认交易。
- **修改优先于重做**：现实变化后保留已完成或已承诺节点，优先应用已核验候补；无法恢复时仅生成受影响范围的 `PlanPatch`。

## 架构

```text
Next.js 移动优先工作台
  | REST: 创建任务、编辑目标/计划、授权、确认交易
  | SSE: 任务快照与可验证进度
  v
FastAPI Task API
  |
  +--> Google ADK / DeepSeek V4 Flash
  |      IntentGovernor -> IntentFrame
  |      LifeGoalPlanner -> CandidateSelection
  |
  +--> Capability Query Orchestrator
  |      |
  |      v
  |   Supply MCP (Streamable HTTP)
  |      餐饮 / 娱乐 / 到店服务 / 配送 / 出行
  |
  +--> PlanningModule + OR-Tools
  |      FeasiblePlanSet -> PlanGraph -> PlanPolicy
  |
  +--> Temporal
  |      履约、重试、观测、取消与补偿
  |
  v
PostgreSQL
任务、任务版本、偏好记忆、供给孪生、回执与 ADK Session
```

### 前端

- `app/` 提供 Next.js 页面入口；首页直接挂载移动优先的任务工作台。
- `components/Workbench.tsx` 统一渲染目标输入、澄清、计划、授权、交易确认、现场状态和世界控制面板。
- `frontend/useLifeTask.ts` 管理任务交互，并订阅 `task` 与 `progress` 两类 SSE 事件。
- `frontend/api.ts` 维护前端对 FastAPI 的任务、偏好、履约、现实事件和本地演示场景 API 调用。

### 后端

- `backend/api/` 暴露 FastAPI JSON API 和 SSE 任务事件流，并在应用启动时组装所有模块。
- `backend/tasks/` 维护任务生命周期、版本冲突保护、目标和计划编辑、授权、现实事件与结果回访。
- `backend/agent/` 使用 Google ADK 驱动 `IntentGovernor`、问题呈现和 `LifeGoalPlanner`，所有模型调用均使用温度 0、关闭思考模式并施加强类型输出 schema。
- `backend/domain/` 定义 `GoalContract`、`IntentFrame`、`FeasiblePlanSet`、`PlanGraph`、`PlanPolicy`、`TaskSnapshot`、`FulfillmentCommand` 等领域模型。
- `backend/planning/` 使用 OR-Tools 求解可行组合、筛选 Pareto 备选、物化计划策略并给出最小约束恢复建议。
- `backend/storage/` 提供 PostgreSQL 文档存储与乐观版本冲突检测；开发/测试可切换为内存实现。
- `backend/memory/` 将结构化偏好和 ADK Session 持久化，而不把历史聊天原文当作长期用户画像。

### Supply MCP 与供给孪生

- `backend/mcp/server.py` 是独立的 Streamable HTTP MCP 服务，发布能力目录、供给资源、分域检索工具和统一生命周期工具。
- `backend/mcp/capabilities.json` 描述每项能力的工具、需要的上下文、规划语义、可观测信号、可变更动作、补偿动作和完成证据。
- `backend/supply/` 维护供给孪生及其 `verified -> quoted -> held -> committed` 生命周期；本地 `local_catalog.json` 让 Demo 能稳定复现。
- 推荐和定价决策不放进 MCP。MCP 提供供给事实，领域模块负责将事实物化为计划、授权对象和履约命令。

## 规划与履约流程

1. 前端调用 `POST /api/tasks` 创建任务；服务立即返回 `202` 和初始任务快照，Agent 在后台推进。
2. `IntentGovernor` 将自然语言目标解析为强类型 `IntentFrame`，提取结果、地点、人数、预算、时间、偏好、假设、约束与最小能力集合。
3. 如果关键不确定性会实质改变方案，系统构造 2–4 个反事实分支，只向用户展示一个澄清问题；用户选择后直接继续该分支，不再把选项文案重新理解一遍。
4. `CapabilityQueryOrchestrator` 根据运行时 Capability Catalog 并行调用相关 MCP 检索工具，得到带版本和证据的 `GroundedCandidateSet`。
5. `FeasibilitySolver` 使用 OR-Tools 验证时间窗口、容量、预算、节点依赖、移动时间和完成期限，生成 `FeasiblePlanSet` 及 Pareto 候选。
6. `LifeGoalPlanner` 只从 Pareto 前沿选择一条主方案和至多两条存在实际取舍的备选；它不能发明供给、价格、场次、路线或库存。
7. `PlanningModule` 从已验证供给物化 `PlanGraph`，生成节点依赖、推荐理由、总价、执行授权边界、候补和现场决策点。
8. 用户可直接修改 `GoalContract`，锁定已确认字段，切换约束的“必须/尽量”，或对计划执行锁定、替换、移除和调整等局部编辑；每次修改都会产生新 revision。
9. 用户批准 `ExecutionMandate` 后，系统只执行免费或非交易动作；支付类命令进入第二级 `TransactionConfirmation`。
10. 已确认的外部履约命令交由 Temporal Workflow 顺序执行，生成可持久化回执；失败会停止后续命令，并支持按能力目录声明的取消、退款或变更动作。
11. 供给状态、用户迟到或现场反馈会触发 `supply.observe`。系统优先采用授权范围内的候补；必要时仅重规划受影响节点，并在任务结束后记录真实完成情况和目标回访。

## 核心 Agent 契约

模型的输出不是完整行程 JSON，也不包含可执行权限。系统使用两段严格的强类型交接：

1. `IntentGovernor` 输出 `IntentFrame`：目标契约、最小能力集合、时间约束、查询计划、澄清分支与是否继续。
2. `LifeGoalPlanner` 输出 `CandidateSelection`：仅从已认证 Pareto 候选中选择主方案，并解释选择的供给节点。

`PlanningModule` 随后依据 MCP 供给事实物化价格、地点、动作、证据、时长、总价与授权，形成完整 `PlanPolicy`。示意如下：

```json
{
  "title": "下班后的轻松聚会",
  "candidate_id": "candidate_2",
  "alternative_candidate_ids": ["candidate_5"],
  "selection_reasons": {
    "food_sushi_guomao": "无需排队且与后续活动的步行衔接最短。",
    "activity_cinema": "在预算内保留了充足的返程余量。"
  },
  "preference_evidence": []
}
```

后端会拒绝以下行为：选择非 Pareto 候选、复写供给事实、伪造价格/库存/证据、修改用户锁定节点、在未授权前发起外部交易，或将假设与未采用备选写入长期偏好。

## API

| 方法 | 端点 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 检查后端、当前模型、MCP、Temporal 和供给世界版本 |
| `POST` | `/api/tasks` | 创建异步本地生活任务 |
| `GET` | `/api/tasks` | 列出指定用户的任务 |
| `GET` | `/api/tasks/{task_id}` | 获取当前任务快照 |
| `POST` | `/api/tasks/{task_id}/messages` | 在任务运行中补充自然语言要求 |
| `POST` | `/api/tasks/{task_id}/decisions` | 提交澄清分支选择 |
| `PATCH` | `/api/tasks/{task_id}/goal` | 编辑目标契约、锁定字段或调整约束强度 |
| `POST` | `/api/tasks/{task_id}/plan-edits` | 对计划节点执行局部编辑 |
| `POST` | `/api/tasks/{task_id}/mandate` | 批准代办范围，执行非交易命令 |
| `POST` | `/api/tasks/{task_id}/transaction` | 确认交易命令 |
| `POST` | `/api/tasks/{task_id}/compensations` | 发起取消、退款等补偿动作 |
| `POST` | `/api/tasks/{task_id}/supply-actions` | 执行能力发布的变更或售后动作 |
| `GET` | `/api/tasks/{task_id}/events` | 流式传输 `task` 与 `progress` SSE 事件 |
| `POST` | `/api/tasks/{task_id}/reality-events` | 报告现场供给或用户状态变化 |
| `POST` | `/api/tasks/{task_id}/outcome-check-in` | 记录用户对现实结果的回访 |
| `GET` / `PATCH` | `/api/preferences` | 读取或修改结构化偏好事实 |
| `GET` / `POST` | `/api/world`、`/api/world/scenarios/{scenario}` | 仅用于本地演示的供给孪生查看与异常注入 |

任务的重要状态包括：

- `understanding`
- `clarifying`
- `retrieving`
- `composing`
- `awaiting_mandate`
- `awaiting_transaction`
- `executing`
- `needs_replan`
- `completed`
- `unsupported`
- `failed`
- `cancelled`

## 快速开始

### 环境要求

- Docker Compose
- Node.js 22+（Docker 前端镜像使用 Node 22）
- Python 3.11+（项目 Docker 后端使用 Python 3.12）
- `uv`
- DeepSeek API Key

### 配置

复制示例环境变量文件，并填入 DeepSeek Key：

```bash
cp .env.example .env
```

典型配置：

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8787
DEEPSEEK_API_KEY=replace-with-your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled

DATABASE_URL=postgresql+asyncpg://locallife:locallife@127.0.0.1:55432/locallife
TEMPORAL_ADDRESS=127.0.0.1:7233
SUPPLY_MCP_URL=http://127.0.0.1:8790/mcp
```

### 使用 Docker Compose 运行全部服务

```bash
docker compose up --build
```

服务地址：

```text
前端工作台： http://127.0.0.1:4174
后端健康检查： http://127.0.0.1:8787/api/health
后端 OpenAPI： http://127.0.0.1:8787/docs
Supply MCP： http://127.0.0.1:8790/mcp
```

### 分别启动开发服务

先安装依赖，并启动 PostgreSQL、Temporal 与 Supply MCP：

```bash
uv sync
npm install
docker compose up postgres temporal supply-mcp
```

然后在另外两个终端中启动后端和前端：

```bash
uv run uvicorn backend.api.app:app --host 127.0.0.1 --port 8787
npm run dev
```

## 测试

```bash
# TypeScript 类型检查 + 后端单元测试
npm test

# 构建前端
npm run build

# Playwright 端到端测试
npm run test:e2e

# 场景泛化验收
uv run python scripts/run_generalization_acceptance.py
```

测试覆盖的重点包括：

- 异步创建任务、SSE 事件流、revision 一致性和新输入取消旧决策轮；
- 单问澄清、反事实分支、能力目录驱动的工具暴露；
- 供给事实、路线与配送窗口、求解器可行性与 Pareto 边界；
- 计划编辑、锁定节点、最小重规划、用户迟到和现场异常恢复；
- 两级授权、Temporal 履约、回执、变更与补偿；
- 供给世界控制面板以及移动优先工作台的端到端交互。

## 项目结构

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

tests/backend/               Agent、API、MCP、供给、求解和任务测试
tests/e2e/                   Playwright 工作台端到端测试
tests/acceptance/            泛化验收场景
scripts/                     验收脚本
```

## 数据与持久化

生产式本地运行通过 PostgreSQL 保存任务、任务 revision、偏好事实、供给孪生状态、履约回执与 ADK Session。Docker Compose 使用 `locallife-postgres` volume 持久化数据库；开发和测试可设置 `USE_IN_MEMORY_STORE=true` 运行内存存储。

供给样本由 `backend/supply/local_catalog.json` 提供，也可通过 `SUPPLY_CATALOG_PATH` 指向供给方拥有的目录。`/api/world/scenarios/*` 只能用于本地演示，能够注入满位、售罄、涨价、司机取消等变化；Agent 本身没有调用这些“世界控制”动作的能力。

## 安全与履约模型

- Agent 输出是决策数据，不具备直接执行权限。
- Capability Catalog 限定每种供给允许的工具、上下文、生命周期、观察信号、变更和补偿动作。
- 每个任务 revision 独立使用 ADK Session；传入模型的是去除了工具历史的强类型决策上下文。
- 目标、计划和供给的修改均有 revision 校验，旧决策不能覆盖新输入。
- 供给提交前会按目录刷新，并经历核验、报价、占位和承诺等生命周期阶段。
- 代办授权和支付确认分离；只有确认后的命令才会进入 Temporal Workflow。
- 履约事件、完成证据与用户回访被显式记录；“接口调用成功”不等同于现实世界已经完成。
