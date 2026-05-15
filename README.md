# WeekendPilot 本地生活规划助手

WeekendPilot 是一个前后端分离的本地生活规划 Demo。前端使用 Next.js 进行页面渲染，后端由 FastAPI 提供 API 服务，并包含完整的 AI 规划流水线。

## 功能特性

- 智能生活规划：基于 AI 的本地活动、餐厅、路线推荐
- 实时流式更新：通过 SSE 实时展示规划进度
- 多智能体系统：Ranker、Validator、Recovery 等专业智能体协作
- 用户偏好管理：支持显式和隐式偏好学习
- 响应式设计：适配桌面和移动设备

## 技术栈

### 前端
- **框架**: Next.js 15 + React 19
- **语言**: TypeScript (strict mode)
- **样式**: Tailwind CSS
- **状态管理**: React Hooks
- **测试**: Playwright (E2E), tsx (单元测试)

### 后端
- **框架**: FastAPI
- **语言**: Python 3.11+
- **AI/ML**: LangChain + LangGraph
- **数据库**: SQLite (workflow + profiles)
- **测试**: pytest
- **包管理**: uv

## 快速开始

### 环境要求

- Node.js 18+
- Python 3.11+
- uv (Python 包管理器)

### 安装依赖

```bash
# 前端依赖
npm install

# 后端依赖
uv sync
```

### 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件，填入你的 API 密钥
# LLM_API_KEY=your-api-key-here
```

### 启动开发服务器

```bash
# 同时启动前后端
npm run dev:full

# 或分别启动
npm run dev          # 前端 (http://127.0.0.1:4174)
npm run dev:backend  # 后端 (http://127.0.0.1:8787)
```

## 开发指南

### 测试

```bash
# 运行所有测试
npm run test:all

# 分类测试
npm run test:frontend   # 前端单元测试
npm run test:backend    # 后端 pytest 测试
npm run test:contracts  # 前后端契约测试

# 端到端测试
npx playwright test

# 构建检查
npm run build
```

### 运行单个测试

```bash
# 后端单个测试
uv run pytest tests/backend/test_api.py -q

# 前端单个测试
tsx --test tests/frontend/component.test.ts

# E2E 单个测试
npx playwright test tests/e2e/feature.spec.ts
```

### 代码检查

```bash
# TypeScript 类型检查
npx tsc --noEmit

# Python 代码检查 (如果配置了)
uv run ruff check backend/
```

## 项目架构

### 目录结构

```
├── app/                    # Next.js 应用入口
├── components/             # React 组件
├── features/planner/       # 规划功能模块
├── lib/                    # 共享库和工具
├── backend/                # FastAPI 后端
│   ├── api/               # API 路由和中间件
│   ├── services/          # 业务逻辑服务
│   ├── orchestrator/      # 规划流水线
│   ├── agents/            # AI 智能体
│   ├── llm/               # LLM 集成
│   └── tools/             # 工具注册表
├── tests/                  # 测试文件
│   ├── backend/           # 后端测试
│   ├── frontend/          # 前端测试
│   ├── contracts/         # 契约测试
│   └── e2e/               # 端到端测试
└── types/                  # TypeScript 类型定义
```

### 请求流程

```
用户界面 → API 客户端 → FastAPI 路由 → 业务服务 → 规划流水线 → AI 智能体
```

### 核心组件

**前端**
- `app/page.tsx`: 主页面入口
- `components/`: UI 组件库
- `features/planner/apiClient.ts`: API 客户端封装
- `lib/api/client.ts`: HTTP 请求工具

**后端**
- `backend/api/app.py`: FastAPI 应用和路由定义
- `backend/services/workflow_service.py`: 核心业务逻辑
- `backend/orchestrator/pipeline.py`: LangGraph 规划流水线
- `backend/agents/`: AI 智能体实现

### AI 智能体系统

规划流水线使用 LangGraph 构建，包含多个专业智能体：

- **RankerAgent**: 对候选方案进行评分和排序
- **ValidatorAgent**: 验证方案是否符合约束条件
- **RecoveryAgent**: 处理错误并生成恢复方案
- **MemoryAgent**: 管理用户偏好和会话上下文

## API 文档

后端 API 文档地址: `http://127.0.0.1:8787/docs`

### 主要端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/llm/status` | LLM 状态信息 |
| POST | `/api/plans/runs` | 创建规划任务 |
| GET | `/api/plans/runs/{run_id}/stream` | SSE 实时更新流 |
| GET | `/api/plans/{plan_id}` | 获取规划详情 |
| GET | `/api/plans` | 获取所有规划列表 |

## 配置说明

### 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `NEXT_PUBLIC_API_URL` | 后端 API 地址 | `http://127.0.0.1:8787` |
| `LLM_PROVIDER` | LLM 提供商 | - |
| `LLM_BASE_URL` | LLM API 地址 | - |
| `LLM_API_KEY` | LLM API 密钥 | - |
| `LLM_MODEL` | 使用的模型 | - |
| `LLM_REMOTE_ENABLED` | 启用远程 LLM | `true` |
| `LLM_TEMPERATURE` | 生成温度 | `0.2` |
| `LLM_MAX_TOKENS` | 最大 token 数 | `2048` |
| `LLM_TIMEOUT_SECONDS` | 请求超时时间 | `90` |

### 数据存储

- 工作流数据: `.weekendpilot/workflow.sqlite`
- 用户配置: `.weekendpilot/profiles.sqlite`

## 部署

### 生产环境构建

```bash
# 构建前端
npm run build

# 启动生产服务器
npm run start
```

### Docker 部署 (可选)

```bash
# 构建镜像
docker build -t weekendpilot .

# 运行容器
docker run -p 4174:4174 -p 8787:8787 weekendpilot
```

## 故障排除

### 常见问题

1. **LLM 连接失败**
   - 检查 `.env` 文件中的 API 密钥是否正确
   - 确认 `LLM_REMOTE_ENABLED=true`
   - 验证网络连接和 API 端点可用性

2. **前端无法连接后端**
   - 确认后端服务已启动 (端口 8787)
   - 检查 `NEXT_PUBLIC_API_URL` 配置
   - 查看浏览器控制台的网络请求

3. **测试失败**
   - 确保所有依赖已安装: `npm install` 和 `uv sync`
   - 检查 Python 版本是否符合要求 (3.11+)
   - 查看测试输出中的具体错误信息

### 日志查看

```bash
# 后端日志
npm run dev:backend 2>&1 | tee backend.log

# 前端日志
npm run dev 2>&1 | tee frontend.log
```

## 贡献指南

1. Fork 项目
2. 创建功能分支: `git checkout -b feature/your-feature`
3. 提交更改: `git commit -m 'Add some feature'`
4. 推送分支: `git push origin feature/your-feature`
5. 创建 Pull Request

### 代码规范

- 前端: TypeScript strict mode, ESLint
- 后端: Python 3.11+ 类型提示, pytest 测试覆盖
- 提交信息: 使用中文，格式为 `类型: 描述`

## 许可证

本项目为演示项目，仅供学习和参考使用。

## 联系方式

如有问题或建议，请通过以下方式联系:
- 提交 Issue
- 发送邮件至项目维护者

---

**注意**: 本项目使用远程 LLM 服务，需要有效的 API 密钥才能运行完整功能。