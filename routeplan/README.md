# 路线助手 · 前端原型

本地生活路线规划助手的高保真原型。无需构建工具,直接打开 `index.html` 即可在浏览器运行(用 React + Babel CDN 在客户端转译 JSX)。

## 运行

```bash
# 任意静态服务器,例如:
npx serve .
# 然后访问 http://localhost:3000/index.html
```

直接 `file://` 也能跑,但 Babel 在 file 协议下偶尔会报跨域,推荐用 serve。

## 文件结构

```
index.html           — 入口,挂载 React,按依赖顺序引入下面的 JSX
ios-frame.jsx        — iOS 设备外框(状态栏 + 圆角 + Dynamic Island)
components.jsx       — 共享原子组件:Icon / Btn / Chip / Toast / Avatar + Mock 数据
need-completion.jsx  — 场景点击路径:SystemPromptCard / NeedCompletionCard / RouteOptionsCard
                       + 6 个场景的问答配置 + 每场景 1–3 条路线变体的 mock 数据
nl-flow.jsx          — 自然语言路径:analyzeNL 分类器 + 4 个分支组件
                       (FollowupCard / ConflictCard + 4 种 summary banner)
history-panel.jsx    — 右上时钟入口的"你的路线"底部抽屉(含开始新对话)
chat-screen.jsx      — 主聊天屏(顶栏 / 欢迎页 / 各状态编排 / 输入框)
route-detail.jsx     — 路线详情页(地图 + 时间轴 + POI 详情 + 底部出发按钮)
app.jsx              — App 主组件 + 状态机(stage 切换 / 历史记录)
```

## 状态机(在 `app.jsx`)

```
chatState.stage:
  welcome      ─ 初始首页
  completing   ─ 点击场景卡 → 渐进式问答
  nl_followup  ─ NL 路径:输入太模糊,反问 1–2 题
  nl_conflict  ─ NL 路径:条件互斥,让用户选优先级
  generating   ─ 路线生成中(loading)
  route        ─ 多路线轮播输出
```

NL 输入会经 `analyzeNL(text)` 分到下面 4 种分支之一:

| branch       | 含义                | 后续 stage     |
|--------------|--------------------|----------------|
| `complete`   | 字段齐全           | → generating → route |
| `assumption` | 缺 1-2 个,用默认 | → generating → route(显示 AssumptionBanner)|
| `followup`   | 太模糊             | → nl_followup → generating → route |
| `conflict`   | 条件冲突           | → nl_conflict → generating → route |

## 设计系统

| 用途       | 色值       |
|------------|------------|
| 主色 / CTA | `#FF6633`(大众点评橙)|
| 主色深     | `#E94A1A`  |
| 主色背景   | `#FFEEE5`  |
| 页面底     | `#F7F7F8`  |
| 卡片       | `#FFFFFF`  |
| 描边       | `#EDEDEF` / `#E8E8EA` |
| 文字       | `#1d1d1f` / `#48484A` / `#8E8E93` |

字体:`Noto Sans SC`(中文)+ `DM Sans`(数字,带 `tnum` 等宽)。

## 主要交互

- **场景卡片点击** → 不伪造用户气泡,直接进入需求补全
- **自然语言输入** → 通过分类器进入 4 种分支
- **路线输出** → 横向滑动卡片轮播 + 下方 pager dots
- **快捷调整 chip** → 重新生成新一组路线,旧的进入历史
- **右上历史入口** → 抽屉式列表,可"开始新对话"或恢复任意历史

## 待办 / 集成点

- 路线详情页目前用 `MOCK_PLACES` 静态 mock,应改为接路由参数 / 接口
- `analyzeNL` 是启发式 + 关键词分类,生产应换成服务端 NLU
- POI 评价 / 等位 / 营业状态 字段在 `MOCK_PLACES` 中,需对接真实数据源
- 地图目前是 SVG 占位,需接入高德 / 腾讯地图 SDK
- `claude.complete` 钩子已留好,可以替换 `analyzeNL` 走 LLM

## 备注

所有 mock 数据(场景配置 / 路线变体 / POI / 路线规划文案)集中在 `need-completion.jsx` 顶部和 `components.jsx` 末尾,方便替换。
