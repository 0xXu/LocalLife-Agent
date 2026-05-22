# LocalLife-Agent Design Description

## 1. 设计目标与边界

LocalLife-Agent（WeekendPilot）将用户的本地生活自然语言目标转成可查看、可确认、可执行的计划。当前实现同时追求三点：让 LLM 支撑开放域需求理解，让本地供给数据保证比赛演示稳定，让预约、领券、点单等有副作用动作保持可控。前端负责输入、状态流转和进度展示；FastAPI 后端负责工作流状态、LangGraph 编排、持久化和执行回执。

规划链路使用远程 OpenAI-compatible LLM 做意图解析与 Agent 推理；POI、天气、菜单、优惠券、路线矩阵和动作结果由本地适配器提供，以保证推荐和执行过程可重复。规划阶段不会直接执行预约、订座、领券、点单、消息、日历等动作，而是先沉淀为待确认 action。

## 2. Planning 策略

核心图由 `backend/orchestrator/pipeline.py` 定义，`backend/services/workflow_service.py` 负责运行、落库和对外返回。

```text
parse_intent -> context -> parallel search -> rank -> itinerary -> validate -> confirm
validation issue -> recovery -> rank/build loop
```

1. **意图结构化。** `parse_intent` 将目标转成 `ParsedConstraints`，包含场景、起点、时间窗、同行人、偏好、硬约束和所需动作。必填信息不足时返回 `needs_clarification`；远程 LLM 未配置或意图解析失败时直接终止 run，避免伪造计划。
2. **上下文与检索。** `build_context` 补全天气和画像上下文；活动、餐厅、散步点由三个并行节点检索，再按标签、天气安全性、距离和偏好信号合并候选。
3. **排序与排程。** `RankerAgent` 做多目标候选选择，可调用 POI 详情、可用性和比较工具；排序 Agent 失败时回退到确定性排序。随后 itinerary builder 选取头部候选，优化路线、生成时间轴、概览指标和 variants。
4. **校验与恢复。** `ValidatorAgent` 检查天气适配、营业时间、可订性和路线效率。阻塞问题进入 `RecoveryAgent`，只替换或调整冲突节点，再回到排序/构建链路。图内恢复次数有上限；服务层的业务校验仍会决定 revision 最终是 `pending_approval`、`ready` 还是 `validation_failed`。

## 3. 工具调用链路

请求链路刻意拆成只读 planning 工具和需人工确认的 action 工具。

| 阶段 | 调用路径 | 主要输出 |
| --- | --- | --- |
| 创建 run | `usePlanMachine` -> `POST /api/plans/runs` -> `WorkflowService.start_run_background` | 创建 `run_id`、`thread_id`、`plan_id`，启动后台 graph worker。 |
| 流式进度 | `GET /api/plans/runs/{run_id}/stream` -> per-run SSE queue | 推送阶段进度和一个终态事件，前端再拉取 plan snapshot。 |
| 只读规划 | `PlanningPipeline` -> Agent tool adapters -> `LocalToolRegistry` | 天气、地点检索、POI 详情、营业时间、可用性、路线、估价和备选比较。 |
| 动作准备 | `build_executable_actions` -> durable action ledger | 生成 grounded、幂等、需确认的 pending actions。 |
| 人工确认 | `POST /api/plans/{plan_id}/resume` + selected action ids | 只领取被选中的 pending actions，记录执行状态并返回 receipts。 |

`LocalToolRegistry.schemas()` 标记工具是否有副作用及是否需要确认。副作用 payload 必须由选中 itinerary 和 candidate lookup 落地；没有 grounding 或身份不匹配的候选不会转成可执行 action。

## 4. 异常处理机制

| 风险类别 | 当前机制 |
| --- | --- |
| 入口与运行失败 | 空目标、非法 JSON、decision/phase 错误和未知 plan/run 映射为稳定 API 错误；LLM 意图解析 fail-fast；worker 抛错发送终态 SSE `failed`，缺少必需候选也终止构建。 |
| 可行性与 Agent 不确定性 | 排序、校验、恢复分别有确定性、规则、启发式 fallback；Validator 触发有界 recovery；持久化前业务校验可把不可审批计划落成 `validation_failed`。 |
| 执行与流式安全 | 敏感工具需确认，selected pending action ids 原子领取，idempotency key、receipts 和 phase transitions 支持审计；per-run queue 用 sentinel 关闭，SSE 有 timeout/cancel，完成 run 可回退 repository-backed events。 |

因此系统把表达力留给 Planning，把控制点放在图边界：先结构化约束再检索，先校验再审批，先 durable action state 再暴露副作用结果。
