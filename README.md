# LocalLife-Agent / WeekendPilot

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js 15](https://img.shields.io/badge/Next.js%2015-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![React 19](https://img.shields.io/badge/React%2019-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev/)
[![OpenAI Agents SDK](https://img.shields.io/badge/OpenAI%20Agents%20SDK-111827?style=for-the-badge)](https://openai.github.io/openai-agents-python/)
[![SQLite](https://img.shields.io/badge/SQLite-074D5B?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org/)

LocalLife-Agent，也叫 WeekendPilot，是一个围绕 run-centered REST + SSE 契约构建的本地生活规划助手。用户可以输入类似“我想出去玩”这样信息不完整的目标，Agent 会一次只追问一个关键澄清问题，在上下文补全后执行一次最终校验，生成结构化计划，并在执行任何有副作用的动作前等待用户明确批准。

当前实现已经完全移除了旧的 LangGraph 中心化运行时。后端使用 FastAPI、SQLite 和 OpenAI Agents SDK；前端是一个 Next.js 工作台，用于展示聊天式澄清、实时 run 事件、结构化计划、备选方案、证据、追踪信息和审批台账。

## 当前原则

- **不生成兜底假计划**：远程规划必须返回合法的结构化 JSON 计划。Markdown、纯文本、缺失行程或空备选方案都会以 `planner_contract_invalid` 失败，而不是生成空的审批页面。
- **一次只问一个问题**：意图抽取只识别一次缺失字段，并将它们存入队列；UI 每轮只提出优先级最高的一个问题。
- **最终校验独立执行**：`FinalValidationTool` 在澄清队列完成后只运行一次，它不是被循环复用的意图抽取器。
- **先审批，后执行副作用**：规划阶段只创建待审批动作。只有用户批准选中的 action id 后，执行才会开始。
- **以 run 为中心的契约**：所有实时状态都通过 `/api/runs`、`/api/runs/{run_id}/events`、`/api/runs/{run_id}/clarifications` 和审批端点流转。

## 架构

![LocalLife-Agent architecture](docs/assets/locallife-architecture.png)

### 前端

- `app/` 和 `components/` 实现 Next.js 工作台。
- `features/runs/` 负责创建 run、订阅 SSE、提交澄清答案、审批、拒绝以及 reducer 状态。
- `components/chat/` 渲染助手风格的澄清流程。
- `components/plan/` 渲染结构化计划结果、备选方案、概览指标、证据、追踪信息和动作台账。

### 后端

- `backend/api/` 暴露 FastAPI JSON 和 SSE 端点。
- `backend/application/run_service.py` 负责 run 生命周期、持久化答案、当前问题、计划快照、事件和 worker 执行。
- `backend/agents/openai_runtime.py` 连接 OpenAI Agents SDK 运行时。
- `backend/agents/intent_extraction_tool.py` 抽取意图和初始缺失字段队列。
- `backend/agents/final_validation_tool.py` 在队列耗尽后执行一次最终完整性检查。
- `backend/infrastructure/` 使用 SQLite 持久化工作流状态和可回放事件。

## 规划流程

![LocalLife-Agent planning flow](docs/assets/locallife-planning-flow.png)

1. 前端用自然语言目标调用 `POST /api/runs`。
2. 前端订阅 `GET /api/runs/{run_id}/events`，并归约命名的 `run.event` SSE 帧。
3. `IntentExtractionTool` 运行一次，抽取已知约束和有序缺失字段列表。
4. 如果仍有缺失字段，后端会发出 `clarification.required`，并保存当前问题。用户通过 `POST /api/runs/{run_id}/clarifications` 提交答案。
5. 当队列为空时，`FinalValidationTool` 运行一次。它可能要求补充一个额外缺失字段，也可能允许进入规划。
6. `PlannerAgent` 必须返回紧凑 JSON，包含 `title`、`summary`、`overview`、`constraint_fit`、非空 `itinerary` 和非空 `variants`。
7. 后端校验 planner 契约。无效 planner 输出会抛出 `planner_contract_invalid` 并让 run 失败，而不是显示合成计划。
8. 合法计划会以“需要审批”的快照形式持久化，并包含待处理动作。
9. 用户通过 `POST /api/runs/{run_id}/actions/approve` 批准选中的动作。
10. 后端以幂等方式执行已批准的本地适配器，并返回回执。

## 严格 Planner 契约

planner 提示词要求只返回 JSON。后端会拒绝任何无法渲染为真实计划的输出。

```json
{
  "title": "下午室内放松计划",
  "summary": "两人从当前位置出发，优先选择安静、低负担的室内放松方案。",
  "overview": {
    "theme": "室内放松",
    "totalDuration": "约 2.5 小时",
    "driveTime": "约 10 分钟",
    "walkingDistance": "约 0.8 公里",
    "estimatedCost": "人均 80-120 元",
    "score": 91
  },
  "constraint_fit": {
    "distance": 0.88,
    "time": 0.96,
    "budget": 0.82
  },
  "itinerary": [
    {
      "start": "14:00",
      "end": "15:30",
      "type": "activity",
      "title": "安静咖啡馆聊天",
      "reason": "室内、轻松，适合两人下午放松。",
      "cost": "人均 80-120 元"
    }
  ],
  "variants": [
    {
      "id": "variant_cafe",
      "kind": "main",
      "title": "咖啡馆聊天",
      "summary": "找一家安静咖啡馆，适合坐下来聊天放松。",
      "score": 91,
      "estimated_budget": 120,
      "itinerary": [
        {
          "start": "14:00",
          "end": "15:30",
          "type": "activity",
          "title": "安静咖啡馆聊天",
          "reason": "室内、轻松，适合两人下午放松。",
          "cost": "人均 80-120 元"
        }
      ]
    }
  ],
  "badges": ["室内", "两人"]
}
```

## API

| 方法 | 端点 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 后端健康检查 |
| `GET` | `/api/llm/status` | LLM 配置和连通性状态 |
| `POST` | `/api/runs` | 根据用户目标创建 run |
| `GET` | `/api/runs/{run_id}` | 读取当前 run 状态 |
| `GET` | `/api/runs/{run_id}/events` | 流式传输命名的 `run.event` SSE 帧 |
| `POST` | `/api/runs/{run_id}/clarifications` | 提交当前问题的答案 |
| `POST` | `/api/runs/{run_id}/actions/approve` | 执行选中的待处理动作 |
| `POST` | `/api/runs/{run_id}/actions/reject` | 拒绝当前需要审批的 run |
| `GET` | `/api/plans` | 列出已持久化的计划摘要 |
| `GET` | `/api/plans/{plan_id}` | 读取已持久化的计划快照 |
| `GET` | `/api/tool-schemas` | 查看工具和动作 schema |

重要 run 状态：

- `queued`
- `running`
- `needs_clarification`
- `approval_required`
- `executing`
- `completed`
- `rejected`
- `failed`

重要 SSE 事件类型：

- `run.started`
- `run.running`
- `agent.started`
- `agent.completed`
- `clarification.required`
- `approval.required`
- `actions.execution.started`
- `actions.execution.completed`
- `run.completed`
- `run.failed`
- `run.rejected`

## 快速开始

### 环境要求

- Node.js 18+
- Python 3.11+
- `uv`

### 安装

```bash
npm install
uv sync
```

### 配置 LLM

复制示例环境变量文件，并设置 OpenAI 兼容模型端点。

```bash
cp .env.example .env
```

典型远程配置：

```env
LLM_PROVIDER=mimo
LLM_API_PROTOCOL=openai
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
LLM_API_KEY=replace-with-your-full-key
LLM_MODEL=MiMo-V2.5-Pro
LLM_TIMEOUT_SECONDS=90
LLM_REMOTE_ENABLED=true
LLM_RESPONSE_FORMAT=json_object
LLM_DISABLE_THINKING=true
LLM_TRUST_ENV_PROXY=false
```

`LLM_REMOTE_ENABLED=true` 是预期的产品演示模式。如果模型返回无效 JSON 或不完整计划，run 会按设计失败。

### 运行前端和后端

```bash
npm run dev:full
```

也可以分别运行：

```bash
npm run dev
npm run dev:backend
```

前端：

```text
http://127.0.0.1:4174
```

后端 OpenAPI 文档：

```text
http://127.0.0.1:8787/docs
```

## 测试

```bash
npm run test:all
npm run build
npm run test:e2e
```

按范围执行：

```bash
npm run test:contracts
npm run test:frontend
npm run test:backend
uv run pytest tests/backend/test_openai_agents_runtime.py -q
```

后端运行时测试覆盖：

- 一次只问一个澄清问题；
- 消费澄清队列时不会重复执行意图抽取；
- `FinalValidationTool` 在队列完成后只运行一次；
- 结构化 planner JSON 会合并进计划契约；
- 非结构化 planner 输出会以 `planner_contract_invalid` 失败；
- 审批与执行身份处理。

## 项目结构

```text
app/                    Next.js 应用入口
components/             React UI 组件
components/chat/        聊天与澄清 UI
components/plan/        计划工作台、备选方案、证据、台账
features/runs/          REST/SSE run 客户端、reducer、controller
features/plans/         计划列表/详情 API 客户端
lib/contracts/          前后端契约测试用 Zod schema
types/                  共享 TypeScript 类型

backend/api/            FastAPI 应用、路由、schema
backend/application/    Run 生命周期与审批服务
backend/agents/         OpenAI Agents SDK 运行时与工具
backend/domain/         Run/领域常量与模型
backend/infrastructure/ SQLite 仓储与事件持久化
backend/llm/            OpenAI 兼容 LLM 配置
backend/tools/          本地副作用适配器与注册表

tests/contracts/        API/schema 契约测试
tests/frontend/         React/reducer/client 测试
tests/backend/          Pytest 后端测试
tests/e2e/              Playwright 浏览器流程
```

## 数据与持久化

本地工作流状态会写入：

```text
.weekendpilot/workflow.sqlite
.weekendpilot/profiles.sqlite
```

这些 SQLite 文件会保存 run、事件、计划快照、审批、回执和本地演示用的用户画像数据。

## 安全模型

- Planner 输出是数据，不具备可执行权限。
- 待处理动作在审批前不会生效。
- `approve` 要求显式传入选中的 action id。
- 执行使用具备幂等意识的本地适配器。
- 回执会被持久化，并展示给用户。
- 无效 planner 输出会明确失败，而不是静默生成空计划或误导性计划。
