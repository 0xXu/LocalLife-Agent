# 本地探索：周末闲时活动规划 Agent

**竞品 / 开源项目调研与 Demo 设计建议**

适用场景：AI Hackathon / 产品 Demo / 设计文档前期调研

调研日期：2026-05-03

> **一句话结论**
>
> 这个赛题的关键不是“帮用户搜索附近有什么”，而是做一个本地生活执行型 Agent：理解一句自然语言里的时间、人群、偏好和约束，生成 4–6 小时半日方案，并在用户确认后调用订座、点单、购票、导航、发送计划等工具。

**建议定位**

- 产品形态：周末半日活动管家 / Local Mini-plan Agent。

- 核心演示：从一句话到可执行计划，再到 Mock API 完成关键动作。

- 差异化：家庭/朋友场景、多约束、多候选打分、饭前饭后活动编排、失败重试和人工确认。

# 目录

1. 赛题理解与判断

2. 调研范围与方法

3. 相似产品与项目总览

4. 竞品/项目对比矩阵

5. 关键能力拆解

6. 推荐 Demo 产品方案

7. Agent 架构与工具调用链

8. 数据结构与 Mock API 设计

9. Demo 场景脚本

10. 风险、异常与评分点

11. 两页设计文档提纲

12. 参考资料

# 1. 赛题理解与判断

题目描述里的关键句是：“这不是搜索推荐，这是帮你把事情做完”。因此，Demo 的重心不应该放在“搜索结果多丰富”，而应该放在“端到端闭环是否成立”：理解目标 → 调用工具 → 生成完整方案 → 用户确认 → 自动执行关键订购/预订/发送动作。

用户给出的原始任务同时包含多个隐含约束：下午 4–6 小时、不离家太远、家庭/朋友两种人群、孩子 5 岁、妻子减肥、朋友 4 人且男女各 2 人、餐厅需要适合人群、吃饭前后还要安排活动。一个普通搜索系统很难一次性处理这些约束，但 Agent 可以把问题拆成多步任务并调用不同工具。

> **本题最重要的产品判断**
>
> 用户不是在问“附近有什么好玩的”，而是在把一个复杂、琐碎、需要决策和执行的本地生活任务外包给 Agent。Demo 必须体现“代办能力”，否则容易沦为普通旅游攻略生成器。

| **维度**  | **普通搜索推荐**               | **本赛题需要的 Agent**                                     |
|-----------|--------------------------------|------------------------------------------------------------|
| 输入      | 关键词，如“附近餐厅”“亲子乐园” | 一句自然语言，包含时间、人群、偏好、距离、预算等隐含约束   |
| 输出      | 地点列表或攻略文本             | 时间轴、路线、餐厅、活动、预算、备选方案、执行确认         |
| 能力重点  | 检索与排序                     | 任务拆解、工具调用、约束满足、计划编排、执行与异常处理     |
| 是否闭环  | 通常停留在“看结果”             | 用户确认后完成订座/点餐/买票/发送计划等动作                |
| Demo 亮点 | 地图和推荐列表                 | 可追踪的 Agent 状态、Mock API 执行记录、失败重试和替代方案 |

# 2. 调研范围与方法

本次调研覆盖三类对象：第一类是已经面向用户的 AI 本地生活/旅行规划产品；第二类是开源 Agent、MCP Server、Agent Skill 项目；第三类是可参考的 Agent 编排框架与工具协议。调研目标不是简单列举产品，而是判断它们对本赛题的“可复用能力”。

- 产品类：美团“小美”、Google Ask Maps、OpenAI Operator + OpenTable、Mindtrip、Wanderlog。

- 开源/开发者项目类：Event Planner Agent Skill、Restaurant Booking MCP、Local Places Skill、Weekend Planner Agent、Food Tour Planner Agent、OpenAI Agents Travel Graph、通义灵码 + 高德 MCP 案例。

- 框架/协议类：LangGraph、CrewAI、Model Context Protocol。

- 评价维度：自然语言理解、人群/偏好约束、餐厅/活动搜索、路线规划、订购/预订动作、协同分享、异常处理、Demo 复用价值。

# 3. 相似产品与项目总览

## 3.1 面向用户的产品 / 平台

| **产品**                    | **类型**                      | **主要能力**                                                                            | **对本赛题的借鉴**                                     | **资料**   |
|-----------------------------|-------------------------------|-----------------------------------------------------------------------------------------|--------------------------------------------------------|------------|
| 美团“小美”                  | 本地生活 AI Agent             | 自然语言交互、内部接口调用、外卖下单、餐厅推荐等本地生活服务；被报道为独立 C 端智能体。 | 直接对标“帮你想、代你办”的产品形态，适合参考执行闭环。 | [4][5] |
| Google Ask Maps             | 对话式地图与本地推荐          | 用户可向 Google Maps 提复杂真实世界问题，获得基于地图与个性化信息的推荐。               | 适合参考“自然语言 + 地图 + 个性化地点推荐”的体验。     | [1]      |
| OpenAI Operator + OpenTable | 网页执行型 Agent + 餐厅订座   | Operator 可使用浏览器执行任务；OpenTable 合作场景强调用 AI 搜索并预订餐厅。             | 适合参考“确认后订座”的人机协作链路。                   | [2][3] |
| Mindtrip                    | AI 旅行规划                   | 支持聊天式规划、个性化推荐、地图与评论、邀请朋友和家人一起规划。                        | 适合参考多人协作、偏好收集、旅行灵感转 itinerary。     | [6]      |
| Wanderlog                   | 旅行 itinerary + 地图路线工具 | 提供行程、地图视图、路线优化、预订管理、AI Assistant、多人协作等功能。                  | 适合参考地图化时间轴和路线优化。                       | [7]      |

## 3.2 开源 / 开发者项目

| **项目**                        | **类型**                  | **主要能力**                                                                                                         | **可复用点**                                           | **资料** |
|---------------------------------|---------------------------|----------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------|----------|
| Event Planner Agent Skill       | Agent Skill               | 通过 Google Places API 搜索餐厅、酒吧、活动，按地点、预算、人数、偏好自动选择并生成带 Google Maps 链接的 itinerary。 | 最贴近“周末夜晚/半日活动规划”的工具形态。              | [8]    |
| Restaurant Booking MCP          | MCP Server                | 整合 Google Maps Places API，按位置、菜系、mood、event type 推荐餐厅，并提供 booking assistance / mock booking。     | 可以直接借鉴餐厅推荐打分和 Mock 预订设计。             | [9]    |
| Local Places Skill              | Agent Skill               | 通过 Google Places API proxy 搜索餐厅、咖啡馆等附近地点；强调先 resolve location，再 search。                        | 适合作为 Demo 的地点搜索工具模板。                     | [10]   |
| Weekend Planner Agent / TimeOut | Agent 示例                | 面向周末规划，输出 Events、Activities、Dining Options。                                                              | 适合参考回答结构和活动/餐饮分层。                      | [11]   |
| Food Tour Planner Agent         | LangChain DeepAgents 项目 | 使用 Google Maps API 与 Tavily 研究工具做美食路线规划，强调多 Agent 协调。                                           | 适合参考饭前饭后的美食/街区路线编排。                  | [12]   |
| 通义灵码 + 高德 MCP 案例        | MCP + 地图案例            | 通过高德 MCP 生成旅行攻略 HTML，并导入高德地图满足探店、导航、打车、购票。                                           | 适合参考地图工具链和“生成页面 + 地图动作”的演示方式。  | [16]   |
| OpenAI Agents Travel Graph      | 多 Agent 旅行规划系统     | 用 OpenAI Agents SDK、LangGraph、浏览器自动化、Supabase 等做旅行研究、预算优化与计划生成。                           | 适合参考“多个专门 Agent + 状态图 + 自动化”的工程架构。 | [17]   |

# 4. 竞品 / 项目对比矩阵

下面这张矩阵把相似产品和项目放在同一张表中比较。评分不是绝对优劣，而是看它们对本赛题 Demo 的贴合程度。

| **对象**                    | **NLU** | **约束** | **规划** | **执行** | **地图** | **判断**                                                        |
|-----------------------------|---------|----------|----------|----------|----------|-----------------------------------------------------------------|
| 美团“小美”                  | 5       | 4        | 5        | 5        | 4        | 业务形态最像，但真实生态不可复制；Demo 可用 Mock 美团接口模拟。 |
| Google Ask Maps             | 5       | 5        | 4        | 3        | 5        | 地点理解和地图推荐很强；执行动作相对弱，适合借鉴推荐体验。      |
| OpenAI Operator + OpenTable | 4       | 3        | 3        | 5        | 3        | 订座执行链路非常有参考价值；本赛题可复制“用户确认后操作”。      |
| Mindtrip                    | 4       | 5        | 5        | 3        | 4        | 偏旅行和协同规划；适合参考多人规划和 itinerary 体验。           |
| Wanderlog                   | 3       | 4        | 5        | 3        | 5        | 路线和地图视图成熟；不是本地生活代办型 Agent。                  |
| Event Planner Skill         | 4       | 4        | 4        | 3        | 4        | 最适合借鉴成 MVP 工具链。                                       |
| Restaurant Booking MCP      | 3       | 4        | 2        | 4        | 3        | 餐厅推荐与 Mock booking 很有价值，但缺饭前饭后活动。            |
| Weekend Planner Agent       | 4       | 3        | 4        | 2        | 2        | 结构参考价值高，执行能力不足。                                  |
| Food Tour Planner Agent     | 4       | 4        | 4        | 2        | 4        | 适合美食/街区路线，但不是家庭/朋友泛场景。                      |

> **综合判断**
>
> 最值得参考的组合是：美团“小美”的本地生活闭环 + Google Ask Maps 的对话式地图推荐 + OpenTable/Operator 的确认后订座 + Restaurant Booking MCP 的推荐/Mock booking + Event Planner Skill 的短时活动 itinerary。

# 5. 关键能力拆解

| **能力**     | **说明**                                                                     | **Demo 表现方式**                                                                          |
|--------------|------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| 自然语言解析 | 从“小明发来一句话”中抽取时间、地点、人群、关系、约束、偏好和目标。           | 输出结构化 JSON：duration=4-6h, scenario=family/friends, childAge=5, diet=weight_loss 等。 |
| 约束补全     | 用户没说预算、交通方式、具体出发地时，系统应用默认值或进行最少追问。         | Demo 可默认“从当前位置出发，半径 5km，预算中等，步行/打车混合”。                           |
| 地点搜索     | 搜索餐厅、亲子活动、展览、citywalk、小吃街、室内备选。                       | 真实 API 可用 Google Places / 高德；Demo 可用 JSON 数据库。                                |
| 多目标打分   | 同时考虑距离、评分、营业时间、儿童友好、减脂友好、排队、预算、路线顺路程度。 | 给每个候选点显示分数和推荐理由，增加可信度。                                               |
| 时间轴编排   | 把餐厅和活动排成 4–6 小时可执行计划。                                        | 输出 14:00 出发、14:30 亲子公园、16:30 健康餐厅、18:00 甜品/散步。                         |
| 执行动作     | 订座、下单、购票、导航、发送计划。                                           | 用 Mock API 展示 reservation_id、order_id、ticket_id、message_sent。                       |
| 异常处理     | 餐厅无位、活动满员、下雨、路程过远、预算超限。                               | 自动切换备选并把原因展示给用户。                                                           |

# 6. 推荐 Demo 产品方案

建议把 Demo 命名为“周末半日活动管家”。核心卖点是：输入一句话，系统在几分钟内给出可执行的下午方案，并可在用户确认后完成关键动作。

## 6.1 MVP 范围

- 支持两个场景：家庭场景、朋友场景。

- 支持一个固定城市或区域；真实 Demo 中可以预置 30–50 个 POI。

- 支持餐厅、亲子活动、展览/citywalk、小吃/甜品四类地点。

- 支持用户确认后 Mock 订座、Mock 点甜品/饮品、Mock 发送计划。

- 支持餐厅无位或天气下雨时自动替换方案。

## 6.2 页面结构

| **页面模块**     | **要展示什么**                                                 | **为什么重要**                               |
|------------------|----------------------------------------------------------------|----------------------------------------------|
| 自然语言输入区   | 用户原话 + 一键生成计划按钮                                    | 体现“接受一句自然语言目标”。                 |
| Agent 执行状态区 | 正在解析需求、搜索餐厅、检查位置、优化路线、生成计划、等待确认 | 让评委看到工具调用链，而不是只看到最终文本。 |
| 约束卡片区       | 人群、时间、半径、饮食、孩子年龄、预算、天气                   | 证明系统理解了复杂约束。                     |
| 推荐方案区       | 主方案 + 备选方案，含理由、评分、预算、距离                    | 体现规划和决策。                             |
| 时间轴/地图区    | 14:00—18:30 的活动安排、路线顺序、交通方式                     | 体现可执行性。                               |
| 确认执行区       | 订座、买票/预约、点甜品、发送给朋友/家人                       | 体现“帮你把事情做完”。                       |
| 执行结果区       | reservation_id、order_id、message_sent、失败重试记录           | 体现真实系统闭环。                           |

## 6.3 功能优先级

| **优先级** | **功能**                                                             | **原因**                               |
|------------|----------------------------------------------------------------------|----------------------------------------|
| P0         | 自然语言解析、结构化约束、候选地点搜索、方案时间轴、确认后 Mock 执行 | 这是赛题核心闭环。                     |
| P1         | 地图路线、评分解释、备选方案、餐厅无位重试、分享消息生成             | 能显著提升 Demo 完整度。               |
| P2         | 真实 Google/Amap API、真实订座平台、多人投票、日历写入、支付         | 时间不够时不要硬做，容易增加不稳定性。 |

# 7. Agent 架构与工具调用链

工程上不一定要真的做复杂多 Agent。为了 Demo 稳定，建议采用“状态机 + 工具调用”的实现方式；如果想体现 Agent 技术，可以用 LangGraph 或 CrewAI 组织节点。LangGraph 的 supervisor/swarm 文档强调由中心调度或动态 handoff 来协调多个专门 Agent；CrewAI 则强调定义 agents、tasks、tools、memory 与 collaboration。 资料来源：[13]、[14]

| **Agent / 节点**     | **职责**                         | **输入**            | **输出**              |
|----------------------|----------------------------------|---------------------|-----------------------|
| Planner Orchestrator | 整体调度，决定下一步调用哪个工具 | 用户目标、当前状态  | 下一步 action         |
| Intent Parser        | 解析自然语言和隐含约束           | 用户原话            | constraints.json      |
| Search Agent         | 搜索餐厅和活动候选               | constraints         | candidate_places[]  |
| Ranking Agent        | 按多目标打分与过滤               | 候选地点、约束      | ranked_candidates[] |
| Route/Schedule Agent | 生成 4–6 小时时间轴和路线顺序    | ranked_candidates   | itinerary             |
| Execution Agent      | 订座、点单、买票、发送消息       | confirmed_itinerary | execution_results     |
| Recovery Agent       | 处理失败重试与替代方案           | error + state       | fallback_plan         |

推荐状态流：

> **Agent 状态机**
>
> INPUT → PARSE_CONSTRAINTS → SEARCH_CANDIDATES → RANK_AND_FILTER → BUILD_ITINERARY → USER_CONFIRMATION → EXECUTE_ACTIONS → SEND_SUMMARY → DONE

| **工具名**         | **用途**                     | **参数示例**                             | **返回示例**                                |
|--------------------|------------------------------|------------------------------------------|---------------------------------------------|
| parse_user_goal    | 把用户自然语言转成结构化约束 | { text }                                 | { scenario, duration, people, constraints } |
| search_places      | 搜索活动地点                 | { category, radius_km, child_friendly }  | places[]                                  |
| search_restaurants | 搜索餐厅                     | { cuisine, diet, party_size, radius_km } | restaurants[]                             |
| check_availability | 检查餐厅/活动是否可订        | { place_id, time, party_size }           | { available, slots }                        |
| optimize_route     | 计算路线与顺序               | { origin, waypoints }                    | { route, travel_minutes }                   |
| create_reservation | Mock 订座                    | { restaurant_id, time, party_size }      | { reservation_id, status }                  |
| create_order       | Mock 点蛋糕/鲜花/饮品        | { shop_id, items, delivery_time }        | { order_id, status }                        |
| send_plan_message  | 发送给朋友/家人              | { recipient, message }                   | { message_id, sent }                        |

# 8. 数据结构与 Mock API 设计

为了 Demo 稳定，建议第一版先不用真实地图/订座 API，而是准备本地 JSON 数据和 Mock API。真实 API 可以作为 P2 增强项。MCP 的工具规范强调工具可以暴露给模型自动调用，用于查询外部系统或执行计算；本 Demo 的 Mock API 可设计成类 MCP 工具，方便以后替换成真实服务。 资料来源：[15]

## 8.1 约束解析 JSON

```json
{  
"scenario": "family",  
"time_window": {"date": "Saturday", "start": "14:00", "duration_hours": 4.5},  
"people": {"adults": 2, "children": [{"age": 5}]},  
"preferences": ["not too far", "child-friendly", "wife is losing weight"],  
"constraints": {"radius_km": 5, "budget_level": "medium", "avoid": ["heavy oil", "long queue"]},  
"actions_required": ["restaurant_reservation", "dessert_order", "send_plan"]  
}
```

## 8.2 地点数据字段

| **字段**            | **说明**                | **例子**                               |
|---------------------|-------------------------|----------------------------------------|
| id/name/category    | 地点唯一 ID、名称、类型 | p_001 / 榉树林亲子公园 / park          |
| lat/lng/distance_km | 坐标和距离              | 38.26, 140.88, 2.1km                   |
| open_hours          | 营业时间                | 10:00–20:00                            |
| rating/reviews      | 评分和评论数            | 4.5 / 1260                             |
| tags                | 标签                    | child_friendly, indoor, healthy, quiet |
| avg_price           | 人均价格                | 1500 JPY                               |
| wait_minutes        | 预计等待                | 10                                     |
| booking_supported   | 是否可预订              | true                                   |

# 9. Demo 场景脚本

建议 Demo 至少准备 3 条脚本，覆盖主流程、朋友场景和异常恢复。现场演示时，先展示自然语言输入，再展示 Agent 执行日志，最后展示确认后的 Mock 执行结果。

| **场景**   | **用户输入**                                                                                        | **演示重点**                                                                                     |
|------------|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| 家庭主流程 | “今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远。孩子 5 岁，老婆最近在减肥，帮我安排一下。” | 解析出孩子/减脂/距离/时间约束；推荐亲子公园 + 健康餐厅 + 饭后散步/甜品；确认后订座并发送给老婆。 |
| 朋友聚会   | “下午 4 个朋友出去玩，2 男 2 女，别太远，先玩再吃饭，最后可以找个小吃街逛一下。”                    | 推荐展览/citywalk + 氛围餐厅 + 小吃街；考虑男女混合、拍照、聊天、预算。                          |
| 异常恢复   | 用户确认主方案后，系统发现餐厅 18:00 无位。                                                         | 自动调用备选餐厅；解释原因；保留前后活动不变；重新确认订座。                                     |
| 天气变化   | 户外活动因下雨不合适。                                                                              | 切换到室内儿童乐园/商场展览；路线和时间轴重新计算。                                              |

# 10. 风险、异常与评分点

| **风险**            | **表现**                               | **解决方式**                                                  |
|---------------------|----------------------------------------|---------------------------------------------------------------|
| 地点幻觉            | 生成不存在的餐厅/活动                  | 所有地点必须来自 POI 数据库或搜索 API；输出 place_id 和来源。 |
| 真实订座/支付不可控 | Demo 可能失败或涉及敏感操作            | 全部用 Mock API；真实执行前必须用户确认。                     |
| 计划不可执行        | 路线太远、时间不够、餐厅关门           | 加入 opening_hours、travel_time、duration 校验。              |
| 约束冲突            | 孩子友好与朋友夜生活、减脂与小吃街冲突 | 显式展示取舍理由，提供备选方案。                              |
| 隐私与安全          | 位置、联系人、支付信息敏感             | 最小化存储，敏感动作二次确认。                                |
| API 成本/限流       | 真实地图接口调用频繁                   | 本地缓存 + Mock 数据 + 结果复用。                             |

评分点建议：

- 计划完整度：是否包含出发、活动、餐厅、饭后安排、回程。

- 约束满足度：是否处理孩子、减脂、朋友人数、距离、时间。

- 执行闭环：是否真的调用了订座/下单/发送计划的工具。

- 可解释性：是否展示为什么推荐、为什么排序、为什么替换。

- 异常处理：餐厅无位、天气变化、预算超限时是否能恢复。

- Demo 稳定性：Mock API 是否可控，避免现场依赖真实服务。

# 11. 两页设计文档提纲

赛题要求设计文档 ≤2 页，因此最终提交版需要高度压缩。建议结构如下：

| **页码** | **模块**   | **内容**                                                                                                                |
|----------|------------|-------------------------------------------------------------------------------------------------------------------------|
| 第 1 页  | 问题定义   | 周末短时活动安排需要同时考虑时间、人群、距离、餐厅、活动、订购/预订，用户不想自己反复搜索比较。                         |
| 第 1 页  | 产品目标   | 一句自然语言 → 生成 4–6 小时可执行方案 → 用户确认 → 自动完成关键动作。                                                  |
| 第 1 页  | 核心用户流 | 输入目标、解析约束、搜索候选、方案打分、生成时间轴、确认执行、发送计划。                                                |
| 第 2 页  | Agent 架构 | Planner Orchestrator + Parser + Search + Rank + Route + Executor + Recovery。                                           |
| 第 2 页  | 工具调用链 | search_places、search_restaurants、check_availability、optimize_route、create_reservation、create_order、send_message。 |
| 第 2 页  | 异常机制   | 无位/超时/下雨/预算超限时自动换备选，敏感动作需用户确认。                                                               |

> **最终提交建议**
>
> 不要把文档写成“旅游推荐系统”。要反复强调：这是“本地生活场景的规划与执行 Agent”，评委看到的价值应该是：用户一句话把麻烦事交给系统，系统替用户完成从决策到执行的闭环。

# 12. 参考资料

[1] Google：Ask Maps and Immersive Navigation. [https://blog.google/products-and-platforms/products/maps/ask-maps-immersive-navigation/](https://blog.google/products-and-platforms/products/maps/ask-maps-immersive-navigation/)

[2] OpenAI：Introducing Operator. [https://openai.com/index/introducing-operator/](https://openai.com/index/introducing-operator/)

[3] OpenTable：OpenAI Operator research preview. [https://www.opentable.com/restaurant-solutions/resources/openai/](https://www.opentable.com/restaurant-solutions/resources/openai/)

[4] 科技日报：美团首款 AI Agent 产品“小美”公测. [https://www.stdaily.com/web/gdxw/2025-09/12/content_399908.html](https://www.stdaily.com/web/gdxw/2025-09/12/content_399908.html)

[5] 美团技术团队：LongCat-Flash-Chat 开源. [https://tech.meituan.com/2025/09/01/longcat-flash-chat.html](https://tech.meituan.com/2025/09/01/longcat-flash-chat.html)

[6] Mindtrip 官方网站. [https://mindtrip.ai/](https://mindtrip.ai/)

[7] Wanderlog 官方网站. [https://wanderlog.com/](https://wanderlog.com/)

[8] OpenClaw / AGNXI：Event Planner Agent Skill. [https://agnxi.com/openclaw/skills/event-planner](https://agnxi.com/openclaw/skills/event-planner)

[9] Restaurant Booking MCP Server. [https://playbooks.com/mcp/restaurant-booking-google-maps](https://playbooks.com/mcp/restaurant-booking-google-maps)

[10] Agent Skills：Local Places. [https://agent-skills.md/skills/openclaw/openclaw/local-places](https://agent-skills.md/skills/openclaw/openclaw/local-places)

[11] Phidata：Weekend Planner Agent. [https://docs.phidata.com/examples/agents/timeout-agent](https://docs.phidata.com/examples/agents/timeout-agent)

[12] GitHub：Food-tour-planner-agent. [https://github.com/muratcankoylan/Food-tour-planner-agent](https://github.com/muratcankoylan/Food-tour-planner-agent)

[13] LangGraph Supervisor / Swarm 多智能体架构参考. [https://reference.langchain.com/javascript/modules/\_langchain_langgraph-supervisor.html](https://reference.langchain.com/javascript/modules/_langchain_langgraph-supervisor.html)

[14] CrewAI：Open-source multi-agent orchestration framework. [https://www.crewai.com/open-source](https://www.crewai.com/open-source)

[15] Model Context Protocol：Tools specification. [https://modelcontextprotocol.io/specification/2025-06-18/server/tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

[16] 阿里云帮助中心：千问灵码 + 高德 MCP 定制出游攻略网页. [https://help.aliyun.com/zh/lingma/use-cases/use-lingma-amap-mcp-to-custom-travel-tips-in-30-minutes](https://help.aliyun.com/zh/lingma/use-cases/use-lingma-amap-mcp-to-custom-travel-tips-in-30-minutes)

[17] GitHub：OpenAI Agents Travel Graph. [https://github.com/BjornMelin/openai-agents-travel-graph](https://github.com/BjornMelin/openai-agents-travel-graph)
