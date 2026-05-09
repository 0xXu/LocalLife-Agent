# 后端对照 detailed_design 验收报告

验收日期：2026-05-09  
验收范围：`backend/`、`tests/backend/`、后端 `.env` LLM 接入、后端 API 与数据能力  
对照文档：`detailed_design.md`  
验收口径：只验收后端能力；前端 UI 是否接入后端不计入本报告，但会在“前后端交付风险”中标注影响。

## 0. 总结论

后端当前达到“可运行 Demo 后端 / 本地确定性 Agent 管线”的水平，但未达到 `detailed_design.md` 中“最终完整作品后端”的目标架构。

整体判定：

- 基础闭环：通过。后端支持构建计划、查询计划、修改约束、候选方案、确认、执行、恢复、trace 查询。
- 数据数量：通过。当前有 90 条 POI、24 条团购券、81 条菜单项、5 类异常脚本。
- 工具 schema：通过。15 个工具名与设计文档一致。
- 确认后执行：部分通过。API 有确认门，副作用动作可返回 ID；但真实副作用、价格/退款/消息内容确认、幂等防重不完整。
- LLM 接入：部分通过。`.env` 已接入 OpenAI-compatible chat/completions，基础请求可用；但 pipeline 的约束解析 prompt 仍会超时或回退，不具备稳定 structured output 保障。
- 状态机与可恢复工作流：部分通过。存在状态字段、trace、内存 checkpoint 和餐厅恢复；没有 LangGraph durable execution，也没有持久化恢复。
- 真实技术栈：不通过。未接 OpenAI Responses API、OpenAI Agents SDK、LangGraph、PostGIS/pgvector、真实地图路线、Redis、OpenTelemetry、Browser fallback。

## 1. 验收证据

本轮执行结果：

| 验证项 | 命令/方式 | 结果 |
|---|---|---|
| 后端单元/API 测试 | `$env:LLM_REMOTE_ENABLED='false'; python -m unittest discover -s tests/backend -p "test_*.py"` | 22 tests OK |
| LLM 基础连通 | `LLMClient(...).chat([Return {"ok": true}])` | 返回 fenced JSON：`{"ok": true}` |
| LLM 安全状态 | `LLMConfig.from_env_file().safe_status()` | `api_key=configured`、`model=mimo-v2.5-pro`、`remote_enabled=True` |
| 数据规模 | `LocalDataCatalog()` | POI 90、coupons 24、menus 81、failure_scenarios 5 |
| live pipeline 抽样 | `PlanningService().build_plan("下午想和对象约会...")` | 可返回 plan；本轮出现 `llm_fallback=True`，说明 LLM schema parse 不稳定 |
| 安全修复验证 | `tests.backend.test_llm_client` | curl 超时异常不再暴露 API key |

注意：后端测试为保证稳定，显式设置 `LLM_REMOTE_ENABLED=false`，因此测试证明本地确定性 fallback 管线可靠；LLM live 能力单独验证。

## 2. 后端文件结构验收

| 设计中后端职责 | 当前文件 | 验收 |
|---|---|---|
| API 层 | `backend/api/app.py` | 部分通过：HTTP API 可用，但使用 `http.server`，不是 Next.js Route Handlers / Agent worker |
| Service 层 | `backend/services/planning_service.py` | 通过：封装 plan 生命周期和内存状态 |
| Orchestrator | `backend/orchestrator/pipeline.py` | 部分通过：手写中心编排器可运行；不是 LangGraph |
| Agents | `backend/agents/*.py` | 部分通过：有类定义，但主 service 不调用这些 Agent 类，多数是旧路径/占位 |
| Models/Schemas | `backend/models/schemas.py` | 部分通过：覆盖核心数据结构，但缺少部分设计字段 |
| Tools | `backend/tools/registry.py` 等 | 部分通过：主路径使用 `LocalToolRegistry`；其他 tool 文件多为旧路径 |
| Data | `backend/data/catalog.py` | 通过数量，部分通过质量：数据量达标，但模板生成、真实密度不足 |
| LLM | `backend/llm/config.py`、`backend/llm/client.py` | 部分通过：OpenAI-compatible chat 接入；非 Responses API structured output |
| Tests | `tests/backend/*.py` | 通过：覆盖 API、pipeline、LLM config/client、完整产品后端 |

## 3. detailed_design 第 1 章：一句话结论 / 评审标准

要求：

- 用户一句自然语言表达目标。
- 系统理解时间、人群、偏好、预算、距离、天气、可订性。
- 生成 4 到 6 小时可执行半日方案。
- 用户确认后完成订座、购票、点单、导航、发送计划等动作。
- 展示从推荐到执行闭环，而不是攻略文本。

当前实现：

- `PlanningService.build_plan(goal)` 支持自然语言输入。
- `PlanningPipeline.parse_constraints()` 支持 LLM 解析和确定性 fallback。
- `PlanningPipeline.build()` 生成活动、餐厅、饭后散步和 pending actions。
- `PlanningService.confirm_plan()` 和 `execute_plan()` 有确认门。
- `LocalToolRegistry.execute_action()` 返回 `TKT/RES/CPN/ORD/MSG/CAL` 风格 ID。

差距：

- 计划没有明确“回程”节点，严格不满足“出发、活动、餐厅、饭后安排、回程”完整时间轴。
- “导航”没有后端 action/tool，只在路线摘要中体现。
- 购票/点单/团购/日历都是本地 receipt 模拟，没有真实业务适配器。
- LLM 只负责约束解析，不是完整 Agent 工具调用。

验收：部分通过。

## 4. detailed_design 第 2 章：外部趋势与设计原则

要求：

- 对话式地图入口。
- AI 从问答转向执行。
- 工具协议标准化，MCP-ready。
- 人在环和可恢复工作流。
- 地点内容 AI 摘要化。

当前实现：

- 有 `tool_schemas()` 返回 MCP-ready 风格工具列表。
- 副作用工具均标记 `requires_confirmation=true`。
- `TraceStep` 和 `ToolCall` 保存工具调用摘要。
- `recover_plan()` 支持餐厅无位恢复。

差距：

- 没有地图服务接口，也没有真实路线服务 adapter。
- 没有远程 MCP 协议服务，只是 schema 风格描述。
- 没有 durable execution，状态存在进程内存。
- 没有 AI place summaries；POI reason 是本地模板。

验收：部分通过。

## 5. detailed_design 第 3 章：产品定位 / 不做什么

要求：

- 本地生活半日规划与执行 Agent。
- 不做长途旅行、不做纯攻略社区、不做无确认支付。
- 所有 POI 必须来自本地数据或真实 API，禁止模型编造地点。

当前实现：

- 后端只从 `LocalDataCatalog` 检索 POI。
- LLM 输出只进入约束结构，不直接生成地点。
- 没有真实支付。
- 副作用执行需要 `confirmed=True`。

差距：

- 缺少 Guardrail 层显式校验“LLM 不得生成 POI”。
- `execute_plan()` 允许状态为 `pending_confirmation` 时直接带 `confirmed=True` 执行，未强制先调用 `/confirm`。

验收：大部分通过，但确认流程严格性不足。

## 6. detailed_design 第 4 章：目标用户与核心场景

要求覆盖四类场景：

1. 家庭半日。
2. 朋友聚会。
3. 雨天室内。
4. 交易异常。
5. 文档其他部分还要求约会场景。

当前实现：

- `detect_scenario()` 支持 `family/friends/date/rainy_indoor`。
- `LocalDataCatalog` 的 POI 支持四类场景。
- 测试覆盖家庭、朋友、约会、雨天室内、餐厅无位恢复。

差距：

- 交易异常只实现餐厅替换。
- 活动满员、雨天运行中切换、路线超时、预算超限没有完整恢复实现。
- LLM 返回关系可能是 `partner` 等非标准值，已做部分归一化但未限制枚举。

验收：场景识别部分通过；异常场景不完整。

## 7. detailed_design 第 5 章：成功标准

| 成功标准 | 当前实现 | 验收 |
|---|---|---|
| 10 秒内展示首个可执行方案 | 本地 fallback 通常很快；LLM live 可能 30 秒超时 | 部分通过 |
| 包含出发、活动、餐厅、饭后、回程 | 有出发、活动、餐厅、饭后；无回程 | 不通过 |
| 核心脚本关键约束 100% 识别 | 测试覆盖有限脚本；LLM 不稳定 | 部分通过 |
| 用户确认后动作 100% 有回执或恢复 | 本地执行动作有回执；失败恢复不覆盖所有动作 | 部分通过 |
| 异常恢复可见 | 餐厅无位可见 diff | 部分通过 |
| 每个计划关联至少一个美团交易/履约动作 | actions 包含 reservation/coupon/order/message/calendar | 后端模拟通过 |

## 8. detailed_design 第 6-8 章：信息架构与交互对后端支撑

后端应支撑：

- Agent trace。
- 约束卡片可编辑。
- 计划画布。
- 地图与路线。
- 确认执行面板。
- 回执。
- 工具展开输入/输出。

当前实现：

- `/api/traces/{plan_id}` 返回 trace。
- `PATCH /api/plans/{plan_id}/constraints` 支持 `radius_km`、`budget_level`、`start`。
- `state_response()` 返回 constraints、progress、trace、tool_calls、itinerary、pending_actions、plan。
- receipt 支持 action ID 和状态。

差距：

- 约束 PATCH 字段很少，不支持人群、儿童年龄、饮食、交通、天气、预算数值等完整编辑。
- 路线只有本地 route matrix 摘要，没有地图 polyline/坐标序列/ETA。
- 工具输入/输出是摘要，不是完整工具 schema input/output 审计。
- 回执 detail 不包含手机号尾号、价格、退款规则、消息全文、日历参与人等安全确认详情。

验收：后端支撑部分通过。

## 9. detailed_design 第 9 章：Agent 产品架构

要求：

- 中心编排器。
- 确定性状态机。
- LLM 工具调用。
- 可恢复工作流。
- 模块：Planner Orchestrator、Intent Parser、Context Builder、Candidate Search、Constraint Ranker、Route Scheduler、Execution Agent、Recovery Agent、Trace Store。

当前实现：

- `PlanningPipeline` 是中心编排器。
- 状态字段覆盖 `input_received`、`constraints_parsed`、`context_ready`、`candidates_ready`、`ranked`、`itinerary_built`、`pending_confirmation`、`confirmed`、`completed`、`recovering`、`recovered_pending_confirmation`。
- trace 中使用了设计里的 Agent 名称。
- `TraceStore` 保存 trace。
- `PlanningService` 保存 `_checkpoints`。

差距：

- 状态机没有显式 transition table，也没有 `NEED_CLARIFICATION`、`EXECUTION_FAILED`、`SEND_SUMMARY`。
- LLM 不执行工具调用，只生成约束 JSON。
- `backend/agents/*.py` 没有接入主 pipeline。
- checkpoint 是内存快照，不 durable。
- Execution failure 没有统一异常捕获和恢复。

验收：架构概念部分通过；最终 Agent 架构不通过。

## 10. detailed_design 第 10 章：技术方案

| 设计技术 | 当前后端 | 验收 |
|---|---|---|
| Next.js Route Handlers + Agent worker | Python `http.server` | 不通过 |
| OpenAI Responses API structured output | OpenAI-compatible chat/completions + 手动 JSON prompt | 不通过 |
| OpenAI Agents SDK | 未使用 | 不通过 |
| LangGraph durable execution | 未使用 | 不通过 |
| MCP-ready function tools | schema 风格工具表 | 部分通过 |
| PostgreSQL/PostGIS/pgvector | 内存列表 | 不通过 |
| Redis/本地缓存层 | 无缓存层 | 不通过 |
| Mapbox/高德/Google Routes | 本地 route matrix | 部分通过 |
| OpenTelemetry/Agents tracing | 自定义 TraceStep | 部分通过 |
| Browserbase Stagehand/Playwright fallback | 未实现 | 不通过 |
| Guardrails | 确认门 + 本地 POI 来源；无独立 guardrail 模块 | 部分通过 |

## 11. detailed_design 第 11 章：数据结构设计

### ParsedConstraints

设计字段：

- `scenario`
- `origin`
- `time_window`
- `people`
- `preferences`
- `constraints`
- `required_actions`

当前实现：

- `ParsedConstraints` dataclass 完整包含上述 top-level 字段。
- LLM 输出有 `constraints_from_dict()` 和 normalize 逻辑。

差距：

- 字段内部没有强类型模型，都是 dict；无法强制枚举和必填。
- `time_window.date` 常用 `"today"`，不是明确日期。
- `people.relationship` 可能来自模型原文，不稳定。

验收：结构通过，类型严谨性不足。

### POI

设计字段大多包含：

- id/name/category/lat/lng/distance/open_hours/rating/review_count/avg_price/tags/wait_minutes/booking_supported/availability/source。

当前实现：

- `POI` dataclass 与 `LocalDataCatalog` 基本覆盖。

差距：

- 缺少结构化 `适合人群`、菜单摘要、商圈、评论摘要。
- `source` 固定为 `local_seed_catalog`，没有真实 API 来源。
- `id` 格式是 `poi_001`，不是按业务类型如 `r_014`、`a_021`。

验收：大部分通过。

### Itinerary

设计字段：

- id、summary、score、estimated_budget、total_travel_minutes、constraint_fit、steps、actions。

当前实现：

- `PlanState.plan_dict()` 输出 id/status/title/summary/constraints/itinerary/overview/actions/variants。
- step 有 start/end/type/title/place_id/reason/cost/travel/score/risk。

差距：

- 缺少 `constraint_fit`。
- `estimated_budget` 在 variant 和 overview 中有，但 plan 根对象没有完整设计形态。
- 缺少 `total_travel_minutes` 根字段。
- actions 在 plan 顶层，不在 itinerary JSON 内。

验收：部分通过。

## 12. detailed_design 第 12 章：打分与排序逻辑

要求：

- 硬过滤营业时间、半径、年龄、人数、排队。
- 软打分公式：distance/rating/constraint_fit/availability/route_efficiency/budget/novelty。
- 解释必须基于打分因子生成 top_reasons/tradeoffs。

当前实现：

- `LocalDataCatalog.search_pois()` 过滤 category、scenario、radius。
- `rank_items()` 按标签命中、rating、distance、wait 排序。
- `validate_plan()` 检查可订、路线总时长、预算上限。
- step reason 来自 POI 模板，risk 来自 risk_tags。

差距：

- 没有营业时间硬过滤。
- 没有年龄适配硬过滤。
- 人数容量只在 `check_availability` 层检查，不在候选过滤层。
- 没有按设计权重公式计算。
- 没有 `constraint_fit_score`、`availability_score`、`route_efficiency_score`、`novelty_or_vibe_score`。
- 没有结构化 `top_reasons/tradeoffs/rejected_reasons`。

验收：不通过，仅有简化排序。

## 13. detailed_design 第 13 章：工具与业务适配器

设计工具 15 个：

1. `parse_user_goal`
2. `get_weather`
3. `search_places`
4. `search_restaurants`
5. `check_availability`
6. `optimize_route`
7. `build_itinerary`
8. `validate_plan`
9. `compare_alternatives`
10. `reserve_activity`
11. `create_reservation`
12. `claim_coupon`
13. `create_order`
14. `send_plan_message`
15. `create_calendar_event`

当前实现：

- `LocalToolRegistry.schemas()` 覆盖全部 15 个工具。
- 本地实现覆盖 weather/search/check/route/build/validate/compare/execute_action。
- side-effect 工具均标记确认。
- 执行返回 ID 和 status。

差距：

- `parse_user_goal` 是 pipeline 方法，不是 tool registry 可调用函数。
- `reserve_activity/create_reservation/claim_coupon/create_order/send_plan_message/create_calendar_event` 统一走 `execute_action()`，没有独立业务 adapter。
- `claim_coupon` 未展示价格、有效期、退款规则。
- `create_order` payload 没有 items/pickup_time。
- `send_plan_message` payload 没有 message 全文。
- `create_calendar_event` payload 没有 itinerary/participants 详情。
- 工具失败没有重试/fallback。

验收：schema 通过，业务适配器部分通过。

## 14. detailed_design 第 14 章：异常与恢复策略

要求覆盖：

- 餐厅无位。
- 活动满员。
- 天气下雨。
- 路线超时。
- 预算超限。
- 约束冲突。
- 工具失败 timeout retry fallback。

当前实现：

- `PlanningPipeline.recover()` 支持餐厅替换。
- `LocalDataCatalog.failure_scenarios` 声明了 5 类异常。
- `validate_plan()` 能产生 `restaurant_unavailable/route_timeout/budget_overrun` issues。
- `RecoveryDiff` 可表达替换差异。

差距：

- `recover()` 不按 reason 分支，任何 reason 都实际替换餐厅。
- `activity_full`、`rain`、`route_timeout`、`budget_overrun` 没有完整恢复动作。
- 约束冲突没有检测。
- 工具 timeout retry fallback 没有通用策略。
- `ExecutionAgent` / `execute_action` 不模拟失败场景。

验收：餐厅无位部分通过，其余不通过。

## 15. detailed_design 第 15 章：隐私、安全与信任

要求：

- 隐私最小化。
- 不保存真实手机号、支付信息、精确家庭住址、未确认联系人消息。
- 地点展示 place_id/source。
- 副作用动作必须确认。
- 显示分数、原因、被筛掉项。
- 计划可执行性校验。

当前实现：

- `.env` safe_status 不回显 API key。
- POI 有 `id/source`。
- 执行 API 需要 `confirmed=True`。
- trace/tool_calls 提供可检查记录。
- 本轮已修复 curl timeout 异常不再暴露 API key。

差距：

- 后端异常处理中一般错误会返回 `detail=str(exc)`，仍可能暴露内部实现或外部服务错误；虽然已修 LLM timeout 泄密，但通用脱敏层缺失。
- 真实手机号/联系人虽然未保存，但消息发送对象和内容也未完整确认。
- 没有被筛掉项输出。
- 没有独立 hallucination guardrail。

验收：部分通过。

## 16. detailed_design 第 16 章：Demo 三幕式后端支撑

第一幕：一句话到计划。

- 当前：通过。`POST /api/plans/build` 支持。
- 差距：LLM 解析不稳定；缺少流式进度。

第二幕：计划到执行。

- 当前：部分通过。`confirm`、`execute` 返回回执。
- 差距：真实执行工具和详细安全确认不足。

第三幕：失败恢复。

- 当前：部分通过。`recover` 返回餐厅替换 diff。
- 差距：只覆盖餐厅，不覆盖雨天/活动/路线/预算。

验收：部分通过。

## 17. detailed_design 第 17 章：一步到位功能范围

### 用户能力对应的后端支撑

| 用户能力 | 后端支撑 | 验收 |
|---|---|---|
| 一句话输入复杂目标 | `build_plan(goal)` | 部分通过，LLM 不稳定 |
| 自动解析时间/人群/预算/距离/饮食/天气/交通 | 部分解析，天气根据场景补全 | 部分通过 |
| 编辑约束后局部重排 | PATCH 支持少数字段，重建整计划 | 部分通过 |
| 主方案/备选/省钱/舒适/孩子优先 | `build_variants()` | 部分通过，variant 内容复制主方案 |
| 时间轴/路线/预算/耗时/推荐理由 | 有时间轴、route summary、预算、reason | 部分通过 |
| 确认后订座/预约/团购/点单/消息/日历 | pending actions + receipts | 后端模拟通过 |
| 失败原因/替代方案/diff/重新确认 | 餐厅 diff | 部分通过 |

### Agent 能力

| Agent 能力 | 当前实现 | 验收 |
|---|---|---|
| Structured output 解析 | chat prompt + JSON 提取 + normalize | 部分通过，不稳定 |
| Context Builder | 天气/profile/privacy 上下文 | 部分通过 |
| Candidate Search | 本地 POI 搜索 | 通过 Demo 级 |
| Constraint Ranker | 简化排序 | 部分通过 |
| Route Scheduler | 本地矩阵摘要 | 部分通过 |
| Plan Validator | 可订/路线/预算 | 部分通过 |
| Human-in-the-loop | confirmed gate | 部分通过 |
| Execution Agent | 模拟 receipts | 部分通过 |
| Recovery Agent | 餐厅恢复 | 部分通过 |
| Trace Store | 内存 trace | 部分通过 |

### 数据能力

| 数据要求 | 当前实现 | 验收 |
|---|---|---|
| 80-120 POI | 90 | 通过 |
| 覆盖餐厅/亲子/展览/citywalk/甜品/商场/室内活动 | 覆盖 restaurant/family/social/date/indoor/dessert_walk；citywalk/商场为弱表达 | 部分通过 |
| POI 包含评分/评论/价格/营业/标签/坐标/排队/可订/适合人群/风险 | 大多包含；适合人群为 supported_scenarios，风险为 risk_tags | 部分通过 |
| 20 团购/套餐 | 24 coupons | 通过 |
| 至少 4 异常数据 | 5 | 通过 |
| place_id/source | id/source | 通过 |

## 18. detailed_design 第 18 章：交付里程碑

| 里程碑 | 后端当前状态 | 验收 |
|---|---|---|
| 工具 schema、评分对齐清单 | 工具 schema 有；评分未对齐公式 | 部分通过 |
| POI/团购/可订/天气/路线种子数据和校验脚本 | 数据有；校验靠测试，无单独脚本 | 部分通过 |
| Agent 状态机、LangGraph checkpoint、核心工具调用、trace store | 手写 pipeline、内存 checkpoint、trace store | 部分通过 |
| 执行工具、回执、失败恢复、方案 diff、四类核心场景 | 执行回执和餐厅 diff 有；恢复不全 | 部分通过 |
| 稳定性和兜底数据 | 本地 fallback 稳定；LLM live 不稳定 | 部分通过 |

## 19. detailed_design 第 19 章：已确定决策

后端相关：

- 固定区域高质量种子数据：数量达标，质量模板化。
- 地图使用可视化底图和路线矩阵，真实 API 不作为稳定唯一依赖：后端有本地 route matrix，但地图底图不属于后端。
- 支付不做真实扣款，只展示团购券、订单和订座回执：后端符合模拟方向。

验收：部分通过。

## 20. 关键缺陷清单

### P0 / 阻塞最终验收

1. LLM structured output 不稳定：基础请求通，但 pipeline 长 prompt 可超时并 fallback，不能证明“按 `.env` 接入 LLM 后稳定解析约束”。
2. 未实现 LangGraph durable execution，checkpoint 仅内存保存，服务重启丢失。
3. 未实现 OpenAI Responses API / Agents SDK / function tools 的真实工具调用 loop。
4. 恢复策略只做餐厅替换，未覆盖活动满员、雨天动态切换、路线超时、预算超限、工具 timeout retry。

### P1 / 影响完整性和评审说服力

1. 计划缺少回程节点。
2. 打分公式未按设计实现，缺少 constraint_fit 和 rejected reasons。
3. 副作用工具没有独立 adapter，团购/点单/日历/消息确认信息不足。
4. API 错误响应缺少通用脱敏和结构化错误码。
5. 状态机缺少 `NEED_CLARIFICATION`、`EXECUTION_FAILED`、`SEND_SUMMARY`。
6. 主 service 不使用 `backend/agents/*`，实现结构与设计里的多能力节点展示存在偏差。

### P2 / Demo 质量问题

1. POI 数据模板重复，真实供给密度和差异化不足。
2. variants 只是复制主方案，省钱/舒适/孩子优先没有真实差异重排。
3. trace/tool_calls 是摘要，不是完整工具输入输出审计。
4. PATCH constraints 支持字段太少。

## 21. 验收建议

若目标是 Hackathon Demo 后端可演示：

- 当前后端可以验收为“Demo 可运行，基础闭环可展示”。
- 需要在讲解中明确：真实业务接口、LangGraph、Responses API、PostGIS 等是目标架构，不是当前落地实现。

若目标是按 `detailed_design.md` 最终方案验收：

- 当前不通过。
- 建议优先补齐：
  1. 使用稳定 structured output：最好换 Responses API / JSON schema；或降低 prompt 长度、增加 retry、失败原因 trace。
  2. 实现显式状态机和持久 checkpoint。
  3. 补齐五类恢复策略。
  4. 实现设计权重公式和结构化解释。
  5. 为 6 类副作用动作拆独立 adapter，并补齐确认信息和失败回滚。
