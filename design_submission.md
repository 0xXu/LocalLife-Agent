# WeekendPilot 提交说明

WeekendPilot 是一个本地生活周末规划 Demo。当前版本采用前后端分离架构：

```text
Next.js UI -> FastAPI /api/* -> Python PlanningService -> PlanningPipeline -> backend tools
```

## 核心体验

用户输入一句自然语言目标，例如“今天下午朋友 4 个人出去玩，先活动再吃饭，路线别绕远，预算 500 元以内”，系统会：

1. 解析人群、时间、预算、距离和偏好约束。
2. 检索本地活动、餐厅和饭后散步点。
3. 生成半日行程、路线和预算。
4. 展示 Agent 执行轨迹和工具输入输出。
5. 在用户确认后执行模拟预约、订座、领券、点单、发消息和写日历动作。
6. 支持餐厅无位等失败恢复。

## 运行

```bash
npm run dev:backend
npm run dev
```

打开：

```text
http://127.0.0.1:4174
```

后端文档：

```text
http://127.0.0.1:8787/docs
```

## 验证

```bash
npm run test:all
npm run build
```

后端单测：

```bash
uv run pytest tests/backend -q
```

## Demo 边界

- 后端是唯一 API 服务；旧 Next.js API Routes 和旧 TypeScript backend 已清理。
- 真实美团、支付、商户订座、消息和日历接口由本地工具模拟，便于现场稳定演示。
- 远程 LLM 使用 OpenAI-compatible 配置；失败时后端会自动降级并在 trace 中标记。
