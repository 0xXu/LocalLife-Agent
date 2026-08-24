# 好办 · Local Life Agent

“你说想要，剩下好办。”一个面向美团供给形态的“意图到履约”本地生活 Agent。用户只描述想达成的生活目标，系统负责澄清关键歧义、组合餐饮、活动、到店服务、即时配送和出行供给，解释取舍，并在两级确认后执行预约、购券、购票、下单、导航、叫车和异常恢复。

## 架构

- Google ADK + DeepSeek V4 Flash：`IntentGovernor` 把自然语言目标解释成强类型 `IntentFrame` 并拆出必要的单问澄清，`LifeGoalPlanner` 基于运行时能力目录组合供给，`question_presenter` 与 `constraint_negotiator` 负责追问和恢复的呈现；所有模型调用温度 0 且思考模式关闭。
- 能力目录驱动：可见工具与专业指令按意图从 MCP 供给方发布的能力目录动态生成，不存在关键词路由、固定垂类分支或全量工具暴露。
- Supply MCP：独立 Streamable HTTP 服务，暴露 13 个供给检索工具与 `supply.quote_and_hold`、`supply.observe`、`supply.commit` 生命周期工具、能力目录和供给资源；推荐与定价决策不进入 MCP。
- 约束边界：模型只输出紧凑的 `PlanDecision`；领域 Module 从供给事实物化价格、地点、动作、证据、时长、总价和授权，避免模型复写或篡改事实。
- 上下文：每个 task revision 使用独立 ADK Session，不做跨轮会话复用；任务状态通过去除工具历史的强类型决策上下文传入。
- PlanGraph：版本化计划与最小 `PlanPatch` 是任务的核心状态。
- Temporal：所有外部履约和补偿动作都通过持久工作流执行。
- PostgreSQL：任务、记忆、供给孪生、回执与 ADK 会话的持久层。
- Next.js：移动优先的单列任务界面，在 Web 宽屏中以手机展示壳呈现目标、可执行路线、授权与现场履约。

## 本地运行

需要 Docker Compose 和一个 DeepSeek API Key：

```bash
cp .env.example .env
# 编辑 .env，填写 DEEPSEEK_API_KEY
docker compose up --build
```

打开 `http://127.0.0.1:4174`。后端健康检查位于 `http://127.0.0.1:8787/api/health`，Supply MCP 位于 `http://127.0.0.1:8790/mcp`。

也可以分别启动开发服务：

```bash
uv sync
npm install
uv run python -m backend.mcp.server
uv run uvicorn backend.api.app:app --port 8787
npm run dev
```

## 校验

```bash
npm test
npm run build
npm run test:e2e
uv run python scripts/run_generalization_acceptance.py
```

世界控制面板只用于本地演示，可注入餐厅满位、演出售罄、价格上涨和司机取消；Agent 本身无法调用这些动作。
本地供给样本位于供给侧数据文件中，也可用 `SUPPLY_CATALOG_PATH` 替换；生产决策代码不包含商家、标签或库存种子。
