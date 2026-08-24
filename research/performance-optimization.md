# LocalLife-Agent 性能优化调研

日期：2026-08-20

## 结论

当前复杂任务约 76 秒的主要问题不是 CP-SAT、Temporal、前端或“没有并行”，而是关键路径中存在过多模型往返：

```text
Intent LLM
  -> N 个并行 Scout（每个仍是 LLM -> MCP tool -> LLM）
  -> CP-SAT
  -> Constraint Questioner LLM / Planner LLM
```

Scout 虽然互相并行，但每个 Scout 内部仍需至少两次模型生成；整个阶段等待最慢 Scout。冲突任务还要在 Scout 之后再串行调用问题生成模型。成熟做法是将链路压缩成：

```text
1 次结构化目标理解（同时产出 capability query plan）
  -> 按 capability_ids 并行调用只读 MCP 查询
  -> 确定性证据归一化 + CP-SAT
  -> 0–1 次短的追问表达或计划取舍
```

这不是“减少 AI”，而是把 AI 留在语义理解、偏好权衡和解释这些真正需要模型判断的地方；供给查询、事实校验、路线时序和预算计算由工具与求解器完成。Google ADK 的 Graph Workflow 明确支持 Agent、Tool 和普通函数混排，普通函数节点无需调用生成模型，正是这一模式的官方实现路径。[Google ADK Graph Workflows](https://adk.dev/graphs/)

基于现有链路和官方能力，建议把冲突追问目标定为 15–20 秒，正常成案目标定为 12–18 秒，已验证分支成案目标定为 8–15 秒。这些是本项目的工程目标，不是供应商承诺；需要用真实 trace 验证。

## 已观察到的事实

### 1. Scout 的并行是有效的

当前 `_build_scout_workflow()` 使用 ADK Workflow fan-out，并把 `max_concurrency` 设为选中能力数；这是正确实现。ADK 官方说明 Parallel Workflow 会近似同时启动所有独立子 Agent，总耗时趋近最慢分支而不是各分支之和。[Google ADK Parallel Workflow](https://adk.dev/agents/workflow-agents/parallel-agents/)

历史真实冲突任务 `task_cad574f78f52` 也能看到 appointments 与 mobility 两个 Scout 在相同时间点完成，因此“Scout 完全串行”不是事实。

### 2. 历史冲突任务曾执行两轮完整 Scout

该任务从 `09:48:48` 创建，到 `09:50:11` 进入澄清，共约 82.5 秒。存储的 trace 出现两组 appointments/mobility Scout：

| 波次 | appointments | mobility | 完成时间 |
|---|---:|---:|---|
| 第一波 | 25.645s | 14.579s | 09:49:19 |
| 第二波 | 39.596s | 11.786s | 09:49:58 |

这说明历史版本里“冲突后再完整重查一次”贡献了最大的可避免延迟。当前工作树已经改成同一证据集直接进入 constraint negotiator，并在选择结构化 Decision Branch 后复用 verified candidate evidence；这一方向正确，下一轮基准必须确认真实 trace 只剩一波 Scout。

最新任务 `task_3ebfe16f2c78` 已经只剩一波 Scout，但仍约 76 秒：Intent
约 5.7 秒，两个并行 Scout 的最慢分支约 34 秒，CP-SAT 约 0.1 秒，随后
constraint negotiator 又约 35–40 秒。它证明“取消第二波 Scout”是必要但不充分的；
剩余主因就是 Scout 内的模型循环和后置问题生成。

### 3. MCP 连接复用已经基本正确

当前每个 Scout 的 `McpToolset` 在 DecisionEngine 构造期创建，而不是在单次请求里创建；还设置了 60 秒 `tools/list` 缓存。Google ADK 2.7.1 的 `MCPSessionManager` 会按连接参数和 headers 对 session 池化，只在断连、后台 transport 死亡或 event loop 改变时重建。[Google ADK MCPSessionManager 源码](https://github.com/google/adk-python/blob/v2.7.1/src/google/adk/tools/mcp_tool/mcp_session_manager.py) MCP Streamable HTTP 规范也定义了初始化后通过 `Mcp-Session-Id` 复用逻辑会话。[MCP Streamable HTTP Session Management](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#session-management)

因此，MCP 握手不是当前几十秒延迟的首要嫌疑。应用启动时预热 tool list/session 可以消除首请求的小抖动，但不会把 76 秒降到 15 秒。

### 4. Temporal 不在首轮规划关键路径上

本项目只在用户授权后的履约/观察阶段进入 Temporal；首轮 Intent、Scout、CP-SAT 和追问发生在此之前。Temporal 的价值是可靠恢复、重试和长事务，不是加速外部模型推理。[Temporal 官方文档](https://docs.temporal.io/)

把规划模型调用迁入 Temporal 不会减少模型或 MCP 网络时间，反而增加 Activity 调度边界。Temporal 继续只负责确认后的履约是正确的。

## 按收益与风险排序的方案

### P0-1：把 LLM Scout 改成“AI 路由 + 确定性 MCP Scout”

**预计收益：最高；风险：中。**

Intent Agent 继续输出 `GoalContract`、`capability_ids`、时间约束，并新增精简的
`CapabilityQueryPlan`：每个被选能力只包含语义检索意图和 provider tool schema
需要的动态参数。随后不再为每个 capability 启动一个 LLM Agent，而是由普通异步
节点根据 provider-published capability catalog 调用对应只读 MCP 查询，并直接产出
`ScoutReport`。

推荐的目标接口不是在 orchestrator 中写餐饮、按摩、出行的条件分支，而是让 capability catalog 为每个能力发布：

- 入口查询工具；
- 查询参数到 GoalContract 字段的声明式映射；
- 可选的 availability/quote enrichment 工具；
- 结果归一化 schema 与 required evidence fields。

orchestrator 只解释这个 provider-owned 协议并并发执行，所以仍满足“Scout 按意图动态选择”和“无业务关键词硬编码”。

这一步会移除每个 Scout 的“模型选择工具”和“模型把工具结果重新抄成 JSON”两次生成。事实过滤仍由 Pydantic 和 `_ground_scout_report` 的不可变供给校验承担，CP-SAT 仍是可行性的最终裁判。

ADK 官方建议独立 I/O 工具使用 `async def`，Python 1.10+ 可以并行执行同一轮中的多个异步工具；只要混入同步工具，其他工具也会被阻塞。[Google ADK Tool Performance](https://adk.dev/tools-custom/performance/)

预计复杂冲突链路可以从：

```text
Intent + max(Scout LLM loops) + Questioner
```

缩短为：

```text
Intent + max(MCP reads) + Questioner
```

其中本地 MCP/数据库读通常应远小于一次模型生成。

### P0-2：把追问和 Planner 改成窄输出，而不是生成完整领域对象

**预计收益：高；风险：中低。**

当前静态 schema 大小已经说明了问题：`IntentFrame` 约 7.0k 字符、
`ClarificationQuestion` 约 5.1k 字符、`PlanDecision` 约 7.0k 字符；其中
`QuestionPresentation` 只有约 0.3k 字符。这里还未计入完整 task、候选和 evidence。

冲突追问不应再让模型生成 2–4 份完整 `DecisionBranch + GoalContract`。CP-SAT 已经
返回冲突 core，可以对 core 中每个用户约束做一次 sensitivity solve，确定“最小放宽量”
和对应可行候选，由代码生成 typed `GoalPatch/DecisionBranch`；模型只负责在这 2–4 个
已证明分支之间生成 `prompt/why_now/labels`。这可以直接复用现有的
`QuestionPresentation` 窄 schema，同时保留 AI 对生活语义的表达。

正常成案也应把 `PlanDecision` 拆成只用于可行路径的 `CandidateSelection`：
`candidate_id`、最多两个 alternative id、简短 reasons。不要再包含本路径不会返回的
完整 `ClarificationQuestion`。Planner 输入只投影目标偏好、Pareto 候选摘要和相关
evidence；当前 `current_task` 已含 goal/question/feasible set，随后又单独发送
`intent_frame` 和 `feasible_plan_set`，属于可删除的重复上下文。完整计划继续由
`materialize_plan_decision()` 确定性物化。

### P0-3：限制每个角色的模型轮次和输出预算

**预计收益：高；风险：低。**

当前所有 Agent 共用 `GenerateContentConfig(temperature=0)`，没有按角色设置输出上限或调用预算。应改为：

- Intent：一次模型调用；无效 JSON 最多修复一次；
- QuestionPresenter：一次、只返回已证明分支的 prompt、why_now 和 labels；
- Planner：一次、只选择/解释 solver 已给出的候选；
- 单角色设置明确的 `max_output_tokens`；
- 整个 turn 设置 `max_llm_calls` 和 wall-clock deadline。

DeepSeek 官方说明 JSON Output 应同时在 prompt 中明确要求 JSON，并合理设置 `max_tokens`，否则可能截断，甚至在缺少 JSON 指令时持续输出空白直到 token 上限。[DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/) [DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)

这里不建议立即切换 DeepSeek `strict` tool calling：它能减少 schema 格式错误，但目前是 beta 且要求 beta base URL，不能解决语义错误或供给不可行问题。[DeepSeek Tool Calls strict mode](https://api-docs.deepseek.com/guides/tool_calls/)

### P0-4：建立真正的关键路径 trace，而不是只记录 Scout 总时长

**预计收益：间接但必要；风险：低。**

现有 trace 能看到 Scout 阶段总耗时，但 Intent、LLM 首 token、每一轮模型调用、MCP 初始化、`tools/list`、单次 `tools/call`、repair 和 questioner/planner 没有组成完整 waterfall。应接入 ADK OpenTelemetry trace，并补充以下字段：

- `generate_content`: model、TTFT、总时长、输入/输出 token；
- DeepSeek `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`；
- `execute_tool`: MCP tool、session reused、新建连接、工具耗时；
- solver 耗时、候选规模；
- repair 次数、取消/超时原因；
- 整个 turn 的 deadline 与实际耗时。

ADK 官方 trace 会把 agent run、workflow、model generation 和 tool execution 组织成层次化 span，正好能展示关键路径。[Google ADK Agent Activity Traces](https://adk.dev/observability/traces/)

验收不看平均值，至少分别看正常成案、供给冲突、模糊追问和分支复用四类任务的 P50/P95 waterfall。这里的目的不是搭建测评系统，而是避免再次凭总耗时猜瓶颈。

### P1-1：保留任务内会话复用，但复用“角色上下文 + 证据”，不复用过期供给

**预计收益：中；风险：低。**

当前稳定的 task-scoped session id 是正确方向：

- `{task}-intent`
- `{task}-scouts-main`
- `{task}-constraint-negotiation`
- `{task}-plan`

ADK Session 保存同一对话线程的事件与临时 state，并允许 Runner 在下一轮恢复这些上下文。[Google ADK Sessions](https://adk.dev/sessions/session/)

DeepSeek Chat Completions 本身是无状态 API，多轮会话仍需客户端重新发送历史；但 DeepSeek 默认启用磁盘前缀缓存，只要后续请求从第 0 token 开始复用完全相同的前缀，就能命中缓存，响应中提供 hit/miss token 指标。[DeepSeek Multi-round Conversation](https://api-docs.deepseek.com/guides/multi_round_chat) [DeepSeek Context Caching](https://api-docs.deepseek.com/guides/kv_cache)

具体做法：

- system instruction、角色协议、JSON schema 和稳定工具说明固定在最前面；
- 当前任务、世界版本、最新消息等动态信息放在尾部；
- 不动态重排 schema、tools 或 instruction；
- 分支选择直接复用该分支绑定的 verified candidate ids 和世界版本；
- 供给超过其 freshness/hold 语义后重新查询，不把 ADK 会话历史当供给缓存。

不要跨 task 复用完整聊天历史；跨任务继续只读取结构化 PreferenceFact。任务内会话解决上下文连续性和 DeepSeek 前缀命中，Decision Branch evidence 才真正消除 MCP/Scout 重查。

### P1-2：为阶段设置 soft deadline，并允许“证据够用即收敛”

**预计收益：中到高；风险：中。**

建议的初始预算：

| 阶段 | soft budget | 到期动作 |
|---|---:|---|
| Intent | 5–8s | 一次短修复或返回最小澄清 |
| 并行 MCP Scout | 4–6s | 取消非关键慢分支；关键证据缺失则说明仍在核验 |
| CP-SAT | <1s | 超出即记录候选规模并诊断模型，不盲目重试 |
| Questioner / Planner | 5–8s | 使用 solver 产生的结构化事实生成短输出 |
| 整个冲突追问 | 15–20s | 返回已证明的冲突和最小可选边界 |

“证据够用”由领域关系判断，不是固定超时后的随意降级。例如精确预约时间没有任何可用 slot 时，已经足以证明当前目标不可行；无需等待返程报价才能先问用户是否愿意改时间。反之，若问题是“能否在 23:00 前到家”，mobility 是关键域，不能提前跳过。

这应由 capability dependency/constraint graph 计算，不能写成“按摩先查、出行后查”的业务硬编码。

### P1-3：应用级预热并继续复用 MCP session

**预计收益：低到中；风险：低。**

保持现有长寿命 `McpToolset`，在 FastAPI lifespan 启动时完成：

- capability resource discovery；
- 各 capability toolset 的第一次 `get_tools()`；
- Streamable HTTP session 初始化；
- shutdown 时统一 `close()`。

不要在请求处理函数中重新构造 toolset，不要跨 event loop 使用 `asyncio.run()`。ADK 官方 MCP 指南建议远程 MCP 考虑 connection pooling，并监控连接建立/关闭与工具执行时间。[Google ADK MCP Tools](https://adk.dev/tools-custom/mcp-tools/)

需要说明：当前工程已经在 DecisionEngine 初始化时构造 Scout/toolset，并启用了 `tools/list` TTL，因此这是收尾优化，不是主解。

### P1-4：流式只用于真实进度和已确定事实

**预计收益：主要改善感知延迟；风险：低。**

DeepSeek 支持 SSE 增量 token，ADK Runner 也会产生事件流。[DeepSeek Chat Completions streaming](https://api-docs.deepseek.com/api/create-chat-completion/)

但结构化 IntentFrame、Decision Branch 和 Plan 在完整 JSON 通过校验前不能安全提交，因此流式不会直接减少 76 秒的 wall-clock。适合立即展示的内容是：

- 已理解的目标摘要；
- 动态选择了哪些供给域；
- 每个 MCP 域的完成事件；
- solver 已证明的冲突；
- 正在生成解释，而不是笼统的“AI 思考中”。

MCP 长工具还可以通过 `McpToolset.progress_callback` 发送 provider 进度。[Google ADK MCP Tools](https://adk.dev/tools-custom/mcp-tools/)

### P2：仅在长任务中做 context compaction

**预计收益：首轮几乎无；多轮任务中等；风险：低。**

ADK 官方指出 session context 会随着指令、工具响应和生成内容累积，context 增长通常会增加处理时间；可通过 token threshold 或 sliding window 压缩旧事件。[Google ADK Context Compaction](https://adk.dev/context/compaction/)

本项目首轮 76 秒不是 compaction 能解决的，因为首轮还没有长历史。只有在多次改计划、异常恢复和长期 Live 任务中，才应限制每个角色最近事件或压缩旧历史。已验证供给、GoalContract 和授权边界应保存在结构化 task state，而不是依赖被压缩的自然语言事件。

## 不建议作为主解的方案

### 增加更多 Agent

并行只压缩彼此独立的分支；它不能压缩 `Intent -> supply -> solver -> question` 的数据依赖。继续拆 Agent 会增加 system prompt、模型请求和合并成本。当前应减少 model-mediated stages，而不是扩大 Agent 数量。

### 依赖 ADK Gemini ContextCacheConfig

ADK 的 ContextCacheConfig 文档针对 Gemini 2.0+；本项目只使用 DeepSeek，不能直接套用。应利用 DeepSeek 默认前缀缓存并观测 hit/miss。[Google ADK Context Caching](https://adk.dev/context/caching/) [DeepSeek Context Caching](https://api-docs.deepseek.com/guides/kv_cache)

### 把所有规划迁入 Temporal

Temporal 解决的是可靠执行，不会加快 DeepSeek 或 MCP。继续把它用于确认后的预约、购券、下单、导航和异常恢复即可。

### 仅打开 token streaming

它能改善首 token 和等待感受，但不能减少 MCP、solver 或结构化 JSON 完成时间。没有轮次压缩时，只会让 76 秒看起来稍微没那么安静。

### 切换 DeepSeek V4 Pro

当前已使用 `deepseek-v4-flash` 且关闭思考，这对延迟方向是正确的。官方将 Flash 定位为更快、更经济的模型，且并发上限高于 Pro。[DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/) 现在切 Pro 不会解决多轮往返，反而更可能增加时延。

## 推荐目标架构

```text
User goal
  |
  v
IntentGovernor LLM
  - GoalContract
  - capability_ids
  - temporal constraints
  - CapabilityQueryPlan
  - clarify / inform / execute
  |
  +-- semantic ambiguity --> short grounded clarification
  |
  v
CapabilityQueryOrchestrator (ordinary async code)
  - reads provider-published retrieval protocol
  - fans out MCP queries concurrently
  - returns normalized immutable evidence
  |
  v
EvidenceGrounder + CP-SAT + Recovery Enumerator (deterministic)
  |
  +-- infeasible --> proven GoalPatch branches --> QuestionPresenter LLM
  |
  +-- feasible --> Pareto candidates --> short DecisionExplainer LLM
  |
  v
Authorization -> Temporal fulfillment
```

关键路径上的模型调用数量应满足：

- 语义不明确：1 次 Intent，必要时 1 次 question presentation；不 Scout；
- 明确但供给冲突：1 次 Intent + 1 次 question presentation；
- 正常成案：1 次 Intent + 1 次 plan selection/explanation；
- 已验证分支：不重新 Intent，不重新 Scout；最多 1 次 plan explanation；
- JSON/schema repair 不属于正常路径，发生率必须可观测。

## 落地顺序

### 第一阶段：先得到可靠基线

1. 接入 ADK OTel waterfall。
2. 记录 DeepSeek cache hit/miss、input/output tokens、TTFT、总生成时长。
3. 用当前 20–30 条高差异问题重跑四类路径，确认每次只有一波 Scout。
4. 单独记录 CP-SAT 耗时，验证它是否确实不是瓶颈。

### 第二阶段：移除 LLM Scout

1. 在 capability catalog 增加 provider-owned retrieval protocol。
2. 新建一个 `CapabilityQueryOrchestrator` 深模块，接收 Intent 产出的
   `CapabilityQueryPlan`，封装 fan-out、MCP 调用、evidence grounding 和 deadline。
3. 保留现有 LLM Scout 仅作为实现期间的测试 oracle，不保留运行时兼容层。
4. 对比结果候选、可行性和端到端耗时；一致后删除旧 Scout runtime。

### 第三阶段：收紧模型预算

1. 为 Intent、Questioner、Planner 分别设置 output token 与 LLM-call budget。
2. 用 solver sensitivity 生成 typed recovery branches，QuestionPresenter 只写文案；
   Planner 改用窄 `CandidateSelection`，不重复完整 task snapshot。
3. 稳定 prompt 前缀，并持续观测 DeepSeek cache hit ratio。

### 第四阶段：deadline、预热和长会话治理

1. 加 capability dependency-aware short-circuit。
2. lifespan 预热 MCP session/tool list。
3. 长任务才启用 recent-event 限制或 compaction。
4. 前端持续展示真实阶段事件，完整结构化结果校验后原子更新。

## 最终判断

最成熟、最适合当前产品的方案不是换框架：Google ADK、MCP、CP-SAT 和 Temporal 的职责划分本身成立。需要调整的是 Agent 粒度和关键路径。

应把当前的“多个 LLM Scout 组成的检索层”改造成“一个 AI IntentGovernor 驱动的异步、声明式 MCP 检索层”。这既保留 AI-native 的目标理解与动态组合，也移除了模型在事实搬运上的高延迟。会话复用值得保留，但主要用于同一 task 的角色上下文和 DeepSeek 前缀缓存；真正能把 76 秒降下来的，是减少模型轮次、复用结构化证据、异步直接调用 MCP，以及给每个阶段明确的时间预算。
