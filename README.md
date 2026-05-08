# 周末管家本地生活演示

周末管家是一个可运行的本地生活 Hackathon 演示项目。它不是普通推荐列表，而是一个执行型助手：用户输入一句自然语言目标，系统理解约束、生成半日行程、展示规划过程，并在用户确认后返回活动预约、餐厅订座和计划发送回执。

## 快速运行

项目使用 `uv` 管理运行环境。先安装 `uv`：

```bash
pip install uv
```

安装完成后，在项目根目录启动静态服务：

```bash
uv run python -m http.server 4173 --bind 127.0.0.1
```

然后打开：

```text
http://127.0.0.1:4173
```

如果端口被占用，把 `4173` 换成其他端口即可。停止服务使用 `Ctrl + C`。

## 测试

```bash
uv run node --test tests/*.test.mjs
```

如果当前环境没有安装 `uv`，可以直接运行：

```bash
node --test tests/*.test.mjs
```

## 后端服务

当前仓库额外提供了分层 Python 后端，前端静态 Demo 保持不变。后端参考多 Agent travel planner 的 `api / models / agents / tools / orchestrator / services` 分层，并按本项目详细设计文档实现本地生活规划 Pipeline。

启动后端：

```bash
python -m backend.api.app
```

默认地址：

```text
http://127.0.0.1:8787
```

后端接口：

```text
GET  /api/health
GET  /api/llm/status
GET  /api/tool-schemas
POST /api/plans/build
GET  /api/plans/{plan_id}
PATCH /api/plans/{plan_id}/constraints
POST /api/plans/{plan_id}/alternatives
POST /api/plans/{plan_id}/confirm
POST /api/plans/{plan_id}/execute
POST /api/plans/{plan_id}/recover
GET  /api/traces/{plan_id}
```

后端测试：

```bash
python -m unittest discover -s tests/backend -p "test_*.py"
```

## 演示脚本

1. 点击 **生成计划**。
2. 展示系统识别到的人群、时长、饮食、半径和交通方式。
3. 点击 **查看规划过程**，展示理解需求、筛选活动、匹配餐厅、规划路线和确认可订时间。
4. 展示今日下午行程和右侧计划概览。
5. 点击 **确认执行**，展示 `TKT-*`、`RES-*`、`MSG-*` 模拟回执。
6. 点击 **换一家餐厅**，展示餐厅无位后的局部替换方案。

## 模拟工具

演示保留 8 个 P0 工具能力，界面中以中文标签展示：

- `parse_user_goal`
- `search_places`
- `search_restaurants`
- `rank_candidates`
- `optimize_route`
- `check_availability`
- `create_reservation`
- `send_plan_message`

这些工具都是确定性模拟实现，后续可以替换成真实美团、地图、订座、订单和消息适配器。

## 项目结构

- [index.html](./index.html)：静态演示页面。
- [src/agent.mjs](./src/agent.mjs)：确定性模拟助手和工具契约。
- [src/app.mjs](./src/app.mjs)：浏览器交互和渲染逻辑。
- [src/styles.css](./src/styles.css)：中文产品化界面样式。
- [data/poi.json](./data/poi.json)：中文种子地点数据。
- [tests/agent.test.mjs](./tests/agent.test.mjs)：行为测试。
- [pyproject.toml](./pyproject.toml)：`uv` 项目配置。
- [uv.lock](./uv.lock)：`uv` 锁定文件。
- [design_submission.md](./design_submission.md)：精简提交文档。

## 当前状态

当前版本是稳定的中文产品化 Demo。普通用户默认看到计划、路线、确认动作和结果；评委可以展开“查看规划过程”检查模拟工具链。
