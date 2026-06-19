# LocalLife-Agent 设计文档（Hackathon 评审版）

## 1. 产品定位

LocalLife-Agent（WeekendPilot）是一个面向本地生活场景的“规划到执行”智能体 Demo。它把用户一句自然语言目标，例如亲子半日游、雨天约会、朋友运动后聚餐，转成可解释的行程、可比较的备选方案、可审计的工具调用轨迹，以及需要用户确认后才执行的预约、领券、点单、发消息和日历动作。

系统的设计重点不是做一个静态推荐列表，而是展示一个完整的 agentic workflow：开放域需求理解、约束结构化、本地供给检索、多目标排序、可行性校验、异常恢复、人工确认、幂等执行和回执沉淀。为了保证黑客松现场稳定性，当前版本采用“远程 LLM + 本地可复现供给”的混合架构：LLM 负责理解和推理，本地 seed catalog 负责 POI、天气、菜单、优惠券、路线、可用性和执行回执模拟，不连接真实支付或生产预约系统。

## 2. 系统架构

![LocalLife-Agent 系统架构图](docs/assets/locallife-architecture.png)

前端是 Next.js 15 + React 19 的单页工作台。Run Controller 管理 `idle -> queued/running -> approval_required/results -> executing -> completed` 的交互状态；结果页同时展示时间轴、路线、variants、候选证据、Trace 和 Action Ledger。后端是 FastAPI + OpenAI Agents SDK 服务，应用层统一管理 run、plan、approval、SSE 事件、SQLite 持久化、用户画像和 action ledger。

主要接口围绕一次 Run 组织：`POST /api/runs` 创建规划任务并返回 `run_id`、`plan_id` 和 `events_url`，`GET /api/runs/{run_id}/events` 返回实时 `run.event` SSE，`GET /api/runs/{run_id}` 读取运行状态，`GET /api/plans/{plan_id}` 读取最终快照，`POST /api/runs/{run_id}/actions/approve` 根据用户选择执行 pending actions，`POST /api/runs/{run_id}/actions/reject` 终止等待审批的 run。`/api/tool-schemas` 暴露工具清单，`/api/llm/status` 用于演示前健康检查。

## 3. 规划策略

后端规划由 OpenAI Agents SDK runtime 和应用服务共同完成：

![LocalLife-Agent 规划执行流程图](docs/assets/locallife-planning-flow.png)

OpenAI Agents SDK runtime 要求远程 OpenAI-compatible LLM 输出结构化 `ParsedConstraints`，包含场景、起点、时间窗、同行人、偏好、硬约束和 required actions。目标过于模糊时返回 `needs_clarification`，LLM 未配置、超时或返回非法 JSON 时 fail-fast，避免伪造计划。应用服务补全天气和画像上下文；活动、餐厅、散步点检索工具读取本地 catalog，并按天气安全性、半径、标签和偏好过滤。

排序、校验、恢复由三个专用 Agent 分工。`RankerAgent` 对候选做多目标选择，可查看 POI 详情和可用性；`ValidatorAgent` 检查营业时间、餐厅容量、天气风险、路线效率和约束匹配；`RecoveryAgent` 在阻塞问题出现时只替换冲突节点，再回到排序与排程链路。Agent 推理失败时系统保留规则 fallback，恢复循环最多 3 次，最终由业务校验决定 revision 是 `ready`、`pending_approval` 还是 `validation_failed`。

## 4. 执行安全与可观测性

系统明确区分只读 planning 工具和有副作用 action 工具。天气、搜索、路线、估价、营业时间和校验工具只读；`reserve_activity`、`create_reservation`、`claim_coupon`、`create_order`、`send_plan_message`、`create_calendar_event` 全部标记为 `side_effect=true` 且 `requires_confirmation=true`。规划阶段只生成 pending actions，不执行任何副作用。

`build_executable_actions` 只允许从已选 itinerary 和 grounded candidate lookup 生成动作；缺少 place/shop grounding、时间不一致、人数不匹配、payload 缺字段或候选身份不一致时，业务校验会阻断审批。执行通过 `/api/runs/{run_id}/actions/approve` 原子领取用户勾选的 `action_id`，SQLite `begin immediate`、稳定 idempotency key、action attempts 和 receipts 共同保证重复点击、部分完成和审计追踪可控。

可观测性贯穿前后端。OpenAI Agents SDK runtime 和应用服务将每个阶段写入 trace span、tool call summary 与 SQLite-backed run event；SSE 优先使用 per-run queue 推送实时进度，队列不存在时回放 repository-backed event，刷新页面仍可恢复最终状态。前端 Evidence 和 Trace 面板让评审能看到“为什么推荐、调用了什么、哪里被校验、哪些动作等待确认”。

## 5. 价值与验证

本项目的核心亮点是把 LLM 的开放表达能力收束到可验证的业务边界内：先结构化约束，再检索排序；先校验落库，再人工确认；先幂等领取，再返回回执。它既能展示自然语言智能体的灵活性，也能展示真实产品所需的安全、可解释和可恢复能力。

测试覆盖按产品闭环设计：契约测试固定前后端数据结构；后端测试覆盖 API、SSE、Run 状态迁移、OpenAI Agents SDK runtime、Agent 工具、业务校验、action policy、durable ledger、用户画像和本地供给；前端测试覆盖状态机、结果页、澄清页、Action Ledger、Trace、地图和响应式体验。整体实现适合现场演示，也保留了后续替换真实地图、真实美团供给、真实消息/日历/预约适配器的清晰边界。
