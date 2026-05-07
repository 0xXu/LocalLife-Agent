# 周末管家本地生活演示

周末管家是一个可运行的美团本地生活 Hackathon 演示项目。它展示的是“执行型助手”而不是普通推荐列表：用户输入一句自然语言目标，系统理解约束、生成半日行程、展示规划过程，并在用户确认后返回活动预约、餐厅订座和计划发送回执。

## 运行方式

推荐用本地静态服务运行，便于浏览器按正常页面方式加载模块：

```bash
python3 -m http.server 4173
```

然后打开：

```text
http://127.0.0.1:4173
```

如果端口被占用，可以换成 5173：

```bash
python3 -m http.server 5173
```

停止服务使用 `Ctrl + C`。

这个演示没有前端构建步骤，也可以直接用浏览器打开 [index.html](./index.html)。

自动化行为测试使用 Node.js：

```bash
npm test
```

## 演示脚本

1. 点击 **生成计划**。
2. 展示系统识别到的人群、时长、饮食、半径和交通方式。
3. 展示“规划过程”：理解需求、筛选活动、匹配餐厅、规划路线、确认可订时间。
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
- [tests/agent.test.mjs](./tests/agent.test.mjs)：计划生成、执行回执、失败恢复和工具列表测试。
- [design_submission.md](./design_submission.md)：精简提交文档。

## 当前重点

当前演示已从评审调试面板改为用户可理解的对话式规划界面。普通用户默认看到的是计划、路线、确认动作和结果；评委可以展开“查看规划过程”来检查模拟工具链。
