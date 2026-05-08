# LocalLife-Agent 与 detailed_design 全量差异比对

检查时间：2026-05-08  
比较对象：`detailed_design.md` 与当前 `LocalLife-Agent` 代码实现  
结论：当前项目已经具备可演示的本地生活 Agent 骨架、后端 pipeline、15 个工具 schema、90 条 POI、24 条团购数据、确认执行与餐厅无位恢复。但前端仍主要使用本地 mock，后端并未真正采用设计文档目标技术栈中的 LangGraph、OpenAI Responses API、Agents SDK、数据库/地图/流式 UI 等能力。LLM 接入已补齐为按 `.env` 自动启用，但真实接口当前返回模型/密钥相关错误，详见“LLM 接入状态”。

## 1. LLM 接入状态

已修改：

- `backend/llm/config.py`：`.env` 中只要 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 配置完整，即默认 `remote_enabled=True`；如需关闭，可显式设置 `LLM_REMOTE_ENABLED=false`。
- `backend/llm/client.py`：仍优先使用 Python 标准库请求 OpenAI-compatible `/chat/completions`；当前 Windows/Python 环境 TLS 握手失败时，自动用 `curl.exe` 兜底请求同一接口。
- `backend/orchestrator/pipeline.py`：LLM 返回 fenced JSON（如 ```json 包裹）时会提取 JSON 对象再解析，避免静默回退到规则解析。
- 新增/更新测试：`tests/backend/test_llm_client.py`、`tests/backend/test_llm_config.py`、`tests/backend/test_pipeline.py`。

验证结果：

- `.env` 安全状态：`provider=mimo`、`protocol=openai`、`base_url=https://token-plan-sgp.xiaomimimo.com/v1`、`model=MiMo-V2.5-Pro`、`api_key=configured`、`configured=True`、`remote_enabled=True`。
- 真实 live 请求已到达接口，但当前 `.env` 的 `LLM_MODEL=MiMo-V2.5-Pro` 返回：`Not supported model MiMo-V2.5-Pro`。
- 临时测试常见模型名时，`mimo-v2.5-pro`、`mimo-v2-pro`、`mimo-v2.5` 返回 `Invalid API Key`；`mimo-v2-flash`、`xiaomi/mimo-v2-flash` 返回 `Not supported model ...`。
- 因此：代码接入已经完成；真实调用还需要确认当前 token-plan 账号有效 API Key 与该账号支持的模型名。

## 2. 总体完成度

| 模块 | detailed_design 要求 | 当前实现 | 差异 |
|---|---|---|---|
| 产品定位 | 本地生活执行型 Agent，一句话生成 4-6 小时可执行半日方案，确认后订座/预约/点单/发计划 | 前端可演示一句话到时间轴；后端可构建计划、确认、执行并返回回执 | 定位接近，但前端未接真实后端，真实业务执行均为模拟 |
| 完整链路 | 输入、解析、检索、排序、路线、可订、确认、执行、失败恢复闭环 | 后端闭环较完整；前端闭环只接 `src/agent.mjs` mock | 前后端链路断开，无法在 UI 中体现真实后端和 LLM |
| Agent 技术深度 | 中心编排器 + 状态机 + LLM 工具调用 + durable execution | Python `PlanningPipeline` 手写确定性流程；内存 checkpoint | 没有 LangGraph durable execution、没有真正工具调用协议执行循环 |
| 数据能力 | 80-120 POI、20 团购、4 异常数据 | 90 POI、24 coupon、81 menu、5 failure scenarios | 数量达标，但都是程序生成模板数据，真实丰富度有限 |
| UI 信息架构 | 一屏工作台，输入、trace、约束、时间轴、地图、底部执行面板 | Planner 页面有左侧对话/trace、中间时间轴、右侧地图和执行面板 | 地图为 CSS 假底图；执行区在右侧卡片，不是底部固定；约束不可编辑 |
| 商业闭环 | 订座、预约、团购券、点单、消息、日历/分享 | 后端 6 类回执都有；前端只展示活动、餐厅、消息 3 类 | 前端商业闭环少于设计；真实交易适配器缺失 |

## 3. 按设计文档章节逐项差异

### 1. 一句话结论 / 1.1 评审标准对齐

已实现：

- 当前项目主题、文案、后端状态流都围绕“周末半日活动管家”。
- 后端有从解析到执行回执的演示链路。
- 后端工具回执可返回 `TKT-*`、`RES-*`、`CPN-*`、`ORD-*`、`MSG-*`、`CAL-*`。

差异：

- UI 目前没有调用后端真实 pipeline，也没有 LLM 输出参与体验。
- “打开 5 到 8 个 App 才能完成的任务”在产品表达上有，但没有真实跨服务/网页执行能力。
- 商业价值在后端模拟，前端展示不足，尤其团购、点单、日历未完整呈现。

### 2. 外部趋势判断

已实现：

- 工具 schema 有 MCP-ready 的雏形。
- 有 Agent trace、确认执行、失败恢复概念。

差异：

- 没有 OpenAI Responses API、OpenAI Agents SDK、远程 MCP、后台任务。
- 没有 Google Places AI 摘要、真实地图问答、真实 Browser fallback。
- LangGraph durable execution 只在文档中，代码未接入。

### 3. 产品定位

已实现：

- 不做长途旅行，核心 demo 聚焦本地半日。
- POI 均来自本地 seed catalog，避免模型编造地点。
- 真实支付没有执行，仅模拟回执。

差异：

- 前端 Saved Plans / Activity 中仍有“海边短途”“山间休整”等偏旅行化示例，与“不做长途旅行规划”不完全一致。
- 真实 API 替换层仍停留在本地适配器设计，没有业务接口边界实现。

### 4. 目标用户与核心场景

已实现：

- 后端支持 `family`、`friends`、`date`、`rainy_indoor` 四类场景。
- 测试覆盖家庭、朋友、约会、雨天、餐厅恢复。

差异：

- 前端入口只有家庭、朋友、雨天 3 个场景按钮，缺少“约会”入口。
- 前端 mock 的 `buildPlan` 几乎只生成家庭方案，朋友/雨天 prompt 没有真实分支计划。
- 交易异常只覆盖“换一家餐厅”，活动满员、雨天动态恢复、路线超时没有前端演示。

### 5. 成功标准

已实现：

- 后端主方案构建很快，测试可稳定执行。
- 后端计划包含活动、餐厅、饭后散步、执行动作。
- 后端关键脚本约束识别有测试。
- 后端执行动作都有模拟回执或恢复路径。

差异：

- 没有真实 10 秒内流式生成体验，前端是同步 mock。
- “出发、活动、餐厅、饭后安排、回程”中当前后端 itinerary 没有明确回程 step。
- 约束识别 100% 只对少量测试脚本成立，不是完整自然语言能力。
- 异常恢复可见性只对餐厅无位完整。

### 6. 信息架构

已实现：

- 有桌面大屏优先布局：侧边栏、顶部栏、Planner 主工作区。
- Planner 页面包含输入原话、约束卡、Agent steps、时间轴、路线预览、执行动作。

差异：

- 设计要求“一屏主工作台而不是传统多页跳转”，当前 App 有 Home、Planner、Saved、Activity、Settings 多页导航。
- 地图区为静态 CSS/图形，不是真地图、不可交互路线。
- 移动端三段式与底部固定确认栏未验证和专项实现。

### 7. 核心用户流程

已实现：

- 后端家庭流程：解析、天气、检索、排序、路线、可订、确认、执行。
- 后端恢复流程：餐厅替换、保留活动和饭后安排、返回 diff。

差异：

- `NEED_CLARIFICATION` 状态没有实现；遇到信息不足不会追问。
- 前端确认执行没有二次确认弹窗，只是按钮直接模拟执行。
- 恢复后重新确认的 UI 文案存在，但没有真正阻断执行或二次确认流程。

### 8. 交互设计细节

已实现：

- 文本输入、语音按钮图标、场景按钮。
- 约束卡展示人群、时长、饮食、半径。
- Agent steps 展示用户可理解的状态。
- 时间轴卡片展示时间、地点、原因、花费、交通。
- 推荐理由和风险字段在后端模型里存在，前端展示 `reason`。
- 执行回执展示机器 ID。

差异：

- 语音输入按钮无功能。
- 示例任务只有 3 个，缺少约会。
- 约束卡不可编辑；半径/预算/时间修改只存在后端 PATCH API，前端没接。
- Agent trace 不可展开查看工具输入/输出 JSON。
- 被筛掉原因没有 UI 展示。
- 确认文案不够具体，没有手机号尾号、联系人、价格规则等敏感信息确认。
- 前端回执只有 TKT/RES/MSG，缺 CPN/ORD/CAL。

### 9. Agent 产品架构

已实现：

- 有 `PlanningPipeline` 中心编排器。
- 有确定性状态字段：`constraints_parsed`、`context_ready`、`pending_confirmation`、`completed` 等。
- 有工具注册表、trace store、checkpoint 数据结构。

差异：

- `backend/agents/*` 存在多个 Agent 类，但主链路实际使用 `PlanningPipeline` 手写流程，没有组合运行这些 Agent 类。
- checkpoint 是内存字典，不持久化，不支持服务重启恢复。
- LLM 仅用于约束解析，不是“LLM 工具调用 + 状态机”的完整 Agent loop。
- 没有 guardrails 模块，只靠 `confirmed` 参数做粗粒度确认。

### 10. 技术方案

已实现：

- Next.js + React 19。
- Python 后端 HTTP API。
- OpenAI-compatible chat/completions 客户端。
- MCP-ready schema 风格的工具列表。
- 本地 route matrix、trace 面板数据、确认执行。

差异：

- 未使用 OpenAI Responses API，当前是 OpenAI-compatible Chat Completions。
- 未使用 OpenAI Agents SDK。
- 未使用 LangGraph durable execution。
- 未使用 shadcn/ui、Radix、Tailwind CSS v4、Motion for React。
- 未使用 Mapbox GL JS、高德/Google Routes 真实路线。
- 未使用 PostgreSQL/PostGIS/pgvector，POI 全部内存生成。
- 未使用 Redis/本地缓存层。
- 后端不是 Next.js Route Handlers + Agent worker，而是 Python `http.server`。
- 未使用 OpenTelemetry 或 Agents tracing。
- 未实现 Browserbase Stagehand / Playwright fallback。
- `ParallelExecutor` 只是顺序执行占位。

### 11. 数据结构设计

已实现：

- `ParsedConstraints`、`POI`、`ItineraryStep`、`PlanAction`、`Receipt` 等 dataclass 基本覆盖设计对象。
- POI 包含 id、name、category、lat/lng、distance、open_hours、rating、review_count、avg_price、tags、wait_minutes、booking_supported、availability、source。

差异：

- 前端 mock 使用 `placeId`，后端使用 `place_id` / `id`，字段风格不一致。
- Itinerary 中没有完整 `constraint_fit` 输出到前端。
- Itinerary 缺少回程节点和明确 `actions` 嵌入结构，actions 在 plan 顶层。
- POI 缺少菜单摘要、商圈、真实评价摘要、适合人群的结构化字段。

### 12. 打分与排序逻辑

已实现：

- 有半径、场景、标签匹配、评分、等待、距离的排序。
- 有基于 POI reason/risk 的解释文本。

差异：

- 没有按文档权重公式实现：`distance_score/rating_score/constraint_fit_score/availability_score/route_efficiency_score/budget_score/novelty_or_vibe_score`。
- 硬过滤未完整执行营业时间、年龄适配、人数容量、排队阈值。
- 解释不是严格由打分因子生成，也没有 `top_reasons` / `tradeoffs` 结构。

### 13. 工具与业务适配器

已实现：

- 后端工具 schema 覆盖 15 个设计工具：`parse_user_goal`、`get_weather`、`search_places`、`search_restaurants`、`check_availability`、`optimize_route`、`build_itinerary`、`validate_plan`、`compare_alternatives`、`reserve_activity`、`create_reservation`、`claim_coupon`、`create_order`、`send_plan_message`、`create_calendar_event`。
- 所有 side-effect 工具 schema 标记 `requires_confirmation=true`。

差异：

- 前端 mock 只列 8 个工具。
- `claim_coupon` 没有展示有效期、退款规则等安全要求。
- `create_order` 没有展示 items、pickup_time。
- `send_plan_message` 没有展示具体发送对象和完整消息内容确认。
- `create_calendar_event` 前端不可见。
- 工具失败没有重试一次再 fallback 的通用框架。

### 14. 异常与恢复策略

已实现：

- 餐厅无位：可替换同类备选并展示 diff。
- 雨天：可作为初始场景生成室内方案。
- failure_scenarios 数据中有 restaurant_unavailable、activity_full、rain、route_timeout、budget_overrun。

差异：

- 活动满员恢复未实现。
- 天气变化后的动态重排未实现。
- 路线超时删除低优先级点未实现。
- 预算超限省钱版替换未真实驱动主方案。
- 约束冲突没有健康版/放松版对比。
- API timeout 重试和 fallback 没有通用机制。

### 15. 隐私、安全与信任

已实现：

- `.env` 密钥不进入 safe status。
- POI 都有 source。
- Demo 不保存真实支付信息。
- side-effect 执行要求 confirmed。

差异：

- Settings 页面有固定邮箱示例，不是隐私最小化的真实用户资料管理。
- 没有联系人权限、消息内容确认、手机号尾号等敏感动作确认。
- 没有专门 guardrails：禁止虚构地点、禁止无确认执行、隐私泄露防护仍靠流程约定。

### 16. Demo 设计

已实现：

- 第一幕：一句话到计划，前后端都能演示。
- 第二幕：后端执行回执完整；前端部分回执。
- 第三幕：餐厅无位恢复可演示。

差异：

- Agent 状态不是流式更新。
- 前端没有展示完整工具输入/输出链。
- 前端没有团购券、点单、日历回执。
- 失败恢复只覆盖餐厅，不覆盖雨天切换或活动满员。
- 四项评分展示点没有专门评审模式/讲解视图。

### 17. 一步到位功能范围

已实现：

- 后端支持复杂目标解析、4 类场景、候选检索、多目标排序、时间轴、验证、确认、执行、恢复、trace。
- 数据数量满足：90 POI、24 coupons、5 failure scenarios。

差异：

- 用户无法编辑约束卡并在 UI 中局部重排。
- UI 中主方案/省钱版/舒适版/孩子优先版未完整切换展示。
- 创建日历、点单、团购券只在后端 action/receipt 层可见。
- 历史偏好、用户画像不真实。
- 80-120 条 POI 虽达标，但不是手工高质量真实密度数据，内容重复度较高。

### 18. 交付里程碑

已实现：

- 有设计文档、工具 schema、数据、后端 pipeline、前端演示页、测试。

差异：

- 第 2 天目标中的 LangGraph checkpoint 未完成。
- 第 3 天目标中的真实一屏工作台部分完成，但地图、约束编辑、底部执行未完整。
- 第 4 天目标中的方案 diff 与失败恢复只覆盖餐厅。
- 第 5 天目标中的演示脚本、性能优化、兜底数据、评审讲稿未见完整实现。

### 19. 已确定决策

已实现：

- 桌面评审大屏优先。
- 固定区域种子数据。
- 支付不真实扣款。

差异：

- 移动端响应式未专项验证。
- 地图只是可视化 mock，不是真实底图或路线矩阵可视化。
- 讲解顺序没有在产品内形成评审模式。

### 20. 参考资料

已实现：

- 文档保留参考资料链接。

差异：

- 参考资料中的 OpenAI Agents SDK、LangGraph、Places summaries、Browser fallback 等没有落地到实现。

## 4. 优先补齐建议

1. 前端接后端 `/api/plans/build`、`confirm`、`execute`、`recover`，替换 `features/planner/mockAgent.js` 主路径。
2. 确认 `.env` 中 token-plan 的有效模型名和 API key，使 live LLM 请求返回 200。
3. 在 Planner UI 展开完整 tool_calls，展示工具输入摘要、输出摘要、耗时、side_effect。
4. 补齐前端 6 类执行动作和回执：活动预约、订座、团购券、点单、消息、日历。
5. 做约束卡编辑：半径、时间、预算、饮食，调用 PATCH 后局部重排。
6. 增加约会入口，并让前端使用后端四类场景，而不是家庭 mock。
7. 扩展恢复策略：活动满员、雨天动态重排、路线超时、预算超限、工具超时重试。
8. 若时间允许，再替换技术底座：LangGraph checkpoint、真实地图 SDK、PostGIS/pgvector、OpenAI Responses/Agents SDK。
