# AI Route Planner

本地生活路线规划服务，后端已迁移到 Python 3.12、FastAPI 和 OpenAI Agents SDK。路线搜索、约束校验与评分保持确定性；OpenAI 仅用于 Agent 编排与语言理解。

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- `OPENAI_API_KEY`（生产环境必需）
- PostgreSQL 16（Docker Compose 会自动提供）

服务只支持 OpenAI，不读取 DeepSeek 或其他模型提供商配置。

## Local development

```bash
cd backend
uv sync
export OPENAI_API_KEY=sk-your-openai-api-key
export JWT_SECRET='a-local-development-secret-that-is-at-least-32-characters'
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
```

检查服务：

```bash
curl http://localhost:8081/api/route/health
```

FastAPI 的交互式 API 文档位于 `http://localhost:8081/docs`。

## Tests

```bash
cd backend
uv run pytest tests/acceptance -v
uv run pytest -q
```

验收测试覆盖代表性的竞赛路线请求以及保留的 API 合约。

## Docker

本地环境（可使用内置 mock 数据源）：

```bash
export OPENAI_API_KEY=sk-your-openai-api-key
export JWT_SECRET='a-local-development-secret-that-is-at-least-32-characters'
docker compose up --build
curl http://localhost:8081/api/route/health
```

生产环境（Nginx、FastAPI、PostgreSQL）：

```bash
cp .env.production .env
# 编辑 .env：设置 OPENAI_API_KEY、JWT_SECRET 和 POSTGRES_PASSWORD
docker compose -f docker-compose.prod.yml up -d --build
curl http://localhost/api/route/health
```

生产环境强制要求 `OPENAI_API_KEY`、至少 32 字符的 `JWT_SECRET` 以及 `POSTGRES_PASSWORD`。数据库连接使用 `DATABASE_URL`，格式为 `postgresql+asyncpg://user:password@host:5432/database`。

## API

兼容的主要端点：

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册用户 |
| POST | `/api/auth/login` | 登录并取得 JWT |
| GET | `/api/route/health` | 健康检查 |
| POST | `/api/route/plan` | 生成路线 |
| POST | `/api/route/smart-plan` | 意图解析与路线生成 |
| GET/POST/DELETE | `/api/favorites` | 管理收藏路线 |

受保护端点需要 `Authorization: Bearer <token>`。注册或登录可取得 token。

```bash
curl -X POST http://localhost:8081/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo","password":"a-secure-demo-password"}'
```
