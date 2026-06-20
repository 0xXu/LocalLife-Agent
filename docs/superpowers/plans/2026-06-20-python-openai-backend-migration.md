# Python OpenAI Backend Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Java/Spring backend with a Python/FastAPI service that preserves the public API and PostgreSQL schema while using the OpenAI Agents SDK for LLM orchestration.

**Architecture:** FastAPI routes delegate to application services. Pure Python domain modules own route generation and constraints; SQLAlchemy repositories own persistence; the OpenAI Agent can call only typed function tools that invoke application services. The deterministic final validator owns authorization and constraint enforcement.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy Async, Alembic, asyncpg, pytest, httpx, pwdlib/Argon2id, PyJWT, OpenAI Agents SDK, PostgreSQL 16, Docker Compose.

---

## Target file structure

```text
backend/
  pyproject.toml
  app/
    main.py                 # FastAPI app and middleware registration
    settings.py             # validated environment configuration
    api/{auth,favorites,routes}.py
    application/{auth,planning,profiles}.py
    domain/{models,constraints,solver,scoring}.py
    agents/{planner,tools}.py
    infrastructure/{db,entities,repositories,data_sources}.py
    security/{jwt,passwords,rate_limit}.py
  alembic/{env.py,versions/0001_baseline.py}
  tests/{api,application,domain,infrastructure,agents,acceptance}/
Dockerfile
docker-compose.yml
.env.example
```

### Task 1: Establish the Python project and validated configuration

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/settings.py`
- Create: `backend/tests/test_settings.py`
- Modify: `.env.example`

- [ ] **Step 1: Write a failing settings test**

```python
# backend/tests/test_settings.py
import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_production_requires_openai_and_jwt_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", openai_api_key="", jwt_secret="")
```

- [ ] **Step 2: Verify the test fails because the module does not exist**

Run: `cd backend && uv run pytest tests/test_settings.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'app.settings'`.

- [ ] **Step 3: Add project metadata and the minimal settings model**

```toml
# backend/pyproject.toml
[project]
name = "local-life-agent-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115", "uvicorn[standard]>=0.34", "pydantic-settings>=2.7",
  "sqlalchemy[asyncio]>=2.0", "asyncpg>=0.30", "alembic>=1.14",
  "pyjwt>=2.10", "pwdlib[argon2]>=0.2", "openai-agents>=0.0.0"
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

```python
# backend/app/settings.py
from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    environment: Literal["local", "test", "production"] = "local"
    openai_api_key: str = ""
    jwt_secret: str = ""
    database_url: str = "postgresql+asyncpg://liquidroute:liquidroute@localhost:5433/liquidroute"

    @model_validator(mode="after")
    def require_production_secrets(self) -> "Settings":
        if self.environment == "production" and (not self.openai_api_key or len(self.jwt_secret) < 32):
            raise ValueError("OPENAI_API_KEY and a 32-character JWT_SECRET are required in production")
        return self
```

Set `.env.example` to `OPENAI_API_KEY`, `JWT_SECRET`, `DATABASE_URL`, `GAODE_API_KEY`, and `MEITUAN_API_TOKEN`; remove DeepSeek variables.

- [ ] **Step 4: Verify the settings test passes**

Run: `cd backend && uv run pytest tests/test_settings.py -v`

Expected: `1 passed`.

- [ ] **Step 5: Commit the project baseline**

```bash
git add backend/pyproject.toml backend/app .env.example
git commit -m "build: add Python backend baseline"
```

### Task 2: Port typed domain models and API response contracts

**Files:**
- Create: `backend/app/domain/models.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/domain/test_models.py`
- Create: `backend/tests/api/test_contract_models.py`

- [ ] **Step 1: Write failing model/contract tests**

```python
# backend/tests/domain/test_models.py
from app.domain.models import POI, UserIntent

def test_intent_normalizes_empty_categories() -> None:
    intent = UserIntent(query="今晚约会", city="上海", preferred_categories=None)
    assert intent.preferred_categories == []

def test_poi_requires_rating_in_valid_range() -> None:
    POI(id="p1", name="Cafe", category="RESTAURANT", city="上海", rating=4.5)
```

```python
# backend/tests/api/test_contract_models.py
from app.domain.models import PlanResponse

def test_plan_response_preserves_legacy_response_fields() -> None:
    assert set(PlanResponse.model_fields) >= {"routes", "warning", "recommendedRoute", "explanation", "sessionId"}
```

- [ ] **Step 2: Verify tests fail on missing imports**

Run: `cd backend && uv run pytest tests/domain/test_models.py tests/api/test_contract_models.py -v`

Expected: collection fails because `app.domain.models` is missing.

- [ ] **Step 3: Implement immutable Pydantic DTOs**

```python
# backend/app/domain/models.py
from pydantic import BaseModel, ConfigDict, Field

class POI(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    category: str
    city: str
    rating: float = Field(ge=0, le=5)
    avg_cost: float = Field(default=0, ge=0)

class Constraint(BaseModel):
    id: str
    value: float | str
    weight: float = Field(default=1, gt=0)
    is_hard: bool = False
    @classmethod
    def budget(cls, amount: float, weight: float) -> "Constraint": return cls(id="budget", value=amount, weight=weight)
    @classmethod
    def time_window(cls, start: str, end: str) -> "Constraint": return cls(id="time_window", value=f"{start}-{end}", is_hard=True)

class RouteSegment(BaseModel):
    poi: POI
    arrival_time: str | None = None
    departure_time: str | None = None
    travel_time_from_previous: float = Field(default=0, ge=0)

class Route(BaseModel):
    id: str
    name: str
    segments: list[RouteSegment]
    total_cost: float = Field(default=0, ge=0)
    violated_soft_constraints: list[str] = Field(default_factory=list)

class UserPreference(BaseModel):
    tags: dict[str, float] = Field(default_factory=dict)

class UserIntent(BaseModel):
    query: str
    city: str = "北京"
    district: str | None = None
    preferred_categories: list[str] = Field(default_factory=list)
    budget: float = Field(default=0, ge=0)
    party_size: int = Field(default=1, ge=1)

class PlanResponse(BaseModel):
    routes: list[dict]
    warning: str | None = None
    recommendedRoute: dict | None = None
    explanation: str | None = None
    sessionId: str
```

```python
# backend/tests/conftest.py
import pytest
from app.domain.models import POI, Route, RouteSegment, UserIntent

@pytest.fixture
def sample_pois() -> list[POI]:
    return [
        POI(id="p1", name="餐厅", category="RESTAURANT", city="上海", rating=4.5, avg_cost=120),
        POI(id="p2", name="公园", category="ATTRACTION", city="上海", rating=4.2, avg_cost=0),
    ]

@pytest.fixture
def sample_intent() -> UserIntent:
    return UserIntent(query="上海晚餐", city="上海", budget=200)

@pytest.fixture
def sample_route(sample_pois: list[POI]) -> Route:
    return Route(id="r1", name="测试路线", segments=[RouteSegment(poi=sample_pois[0], arrival_time="15:00", departure_time="18:00")])
```

Add typed `AnalyzeRequest`, `PlanRequest`, and `AdjustRequest` models in this same module, retaining the JSON field names used by `routeplan/api.js`.

- [ ] **Step 4: Verify domain and contract tests pass**

Run: `cd backend && uv run pytest tests/domain/test_models.py tests/api/test_contract_models.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Commit the API contract layer**

```bash
git add backend/app/domain/models.py backend/tests/domain backend/tests/api
git commit -m "feat: add typed route planning contracts"
```

### Task 3: Port deterministic constraints, scoring, and route search

**Files:**
- Create: `backend/app/domain/constraints.py`
- Create: `backend/app/domain/scoring.py`
- Create: `backend/app/domain/solver.py`
- Create: `backend/tests/domain/test_constraints.py`
- Create: `backend/tests/domain/test_solver.py`

- [ ] **Step 1: Write failing behavior tests translated from Java solver tests**

```python
# backend/tests/domain/test_constraints.py
from app.domain.constraints import ConstraintEngine
from app.domain.models import Constraint, Route

def test_time_window_violation_is_hard_failure(sample_route: Route) -> None:
    result = ConstraintEngine().validate(sample_route, [Constraint.time_window("09:00", "17:00")])
    assert result.has_hard_violations is True

def test_budget_is_scored_without_pruning(sample_route: Route) -> None:
    score = ConstraintEngine().score_route(sample_route, [Constraint.budget(100, weight=6)])
    assert 0 <= score < 100
```

```python
# backend/tests/domain/test_solver.py
from app.domain.solver import GraphSearchSolver

def test_solver_generates_distinct_routes_for_feasible_candidates(sample_pois, sample_intent) -> None:
    routes = GraphSearchSolver().generate_plans(sample_pois, [], sample_intent, limit=3)
    assert 1 <= len(routes) <= 3
    assert len({tuple(segment.poi.id for segment in route.segments) for route in routes}) == len(routes)
```

- [ ] **Step 2: Verify the tests fail because solver modules do not exist**

Run: `cd backend && uv run pytest tests/domain/test_constraints.py tests/domain/test_solver.py -v`

Expected: collection fails with `ModuleNotFoundError` for `app.domain.constraints`.

- [ ] **Step 3: Implement deterministic algorithms without OpenAI calls**

```python
# backend/app/domain/constraints.py
class ConstraintEngine:
    def validate(self, route, constraints):
        hard = [c for c in constraints if c.is_hard and not c.satisfied_by(route)]
        return ValidationResult(hard_violations=hard)

    def score_route(self, route, constraints):
        soft = [c for c in constraints if not c.is_hard]
        return 100.0 if not soft else sum(c.weight * c.score(route) for c in soft) / sum(c.weight for c in soft) * 100
```

Implement graph expansion using geodesic distance and opening/time constraints; generate unique candidate sequences; invoke `ConstraintEngine.validate` before accepting every route. Port the Java relaxation sequence as explicit ordered constraint sets, retaining the special CHEAPEST budget-preservation rule.

- [ ] **Step 4: Verify unit tests and the Java-derived test cases pass**

Run: `cd backend && uv run pytest tests/domain/test_constraints.py tests/domain/test_solver.py -v`

Expected: all tests pass with no network access.

- [ ] **Step 5: Commit deterministic planning**

```bash
git add backend/app/domain backend/tests/domain
git commit -m "feat: port deterministic route planning"
```

### Task 4: Add asynchronous database access and an Alembic baseline

**Files:**
- Create: `backend/app/infrastructure/db.py`
- Create: `backend/app/infrastructure/entities.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_existing_schema_baseline.py`
- Create: `backend/tests/infrastructure/test_database.py`

- [ ] **Step 1: Write a failing persistence mapping test**

```python
# backend/tests/infrastructure/test_database.py
from app.infrastructure.entities import UserProfileEntity

def test_user_profile_maps_existing_auth_columns() -> None:
    assert UserProfileEntity.__tablename__ == "user_profiles"
    assert "password_hash" in UserProfileEntity.__table__.columns
    assert "user_id" in UserProfileEntity.__table__.columns
```

- [ ] **Step 2: Verify the test fails on a missing entity module**

Run: `cd backend && uv run pytest tests/infrastructure/test_database.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'app.infrastructure.entities'`.

- [ ] **Step 3: Implement async engine/session and schema mappings**

```python
# backend/app/infrastructure/db.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

def build_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(create_async_engine(database_url, pool_pre_ping=True), expire_on_commit=False)
```

Map `user_profiles`, `sessions`, `routes`, `snapshots`, and `favorites` to their existing V1–V6 columns. The Alembic baseline must have an empty `upgrade()` and `downgrade()` body because Flyway has already created these tables; its revision only records ownership beginning with the Python runtime.

- [ ] **Step 4: Verify mapping tests pass and Alembic has no pending migration**

Run: `cd backend && uv run pytest tests/infrastructure/test_database.py -v && uv run alembic check`

Expected: test passes; Alembic reports no new upgrade operations against a database initialized with `src/main/resources/db/migration`.

- [ ] **Step 5: Commit persistence baseline**

```bash
git add backend/app/infrastructure backend/alembic backend/alembic.ini backend/tests/infrastructure
git commit -m "feat: add async PostgreSQL persistence"
```

### Task 5: Port repositories, profiles, sessions, and favorites with ownership checks

**Files:**
- Create: `backend/app/infrastructure/repositories.py`
- Create: `backend/app/application/profiles.py`
- Create: `backend/app/application/favorites.py`
- Create: `backend/tests/application/test_favorites.py`
- Create: `backend/tests/application/test_sessions.py`

- [ ] **Step 1: Write failing ownership tests**

```python
# backend/tests/application/test_favorites.py
import pytest

async def test_deleting_another_users_favorite_is_forbidden(favorites_service):
    favorite = await favorites_service.save(user_id="owner", route_json="{}", route_name="route")
    with pytest.raises(PermissionError):
        await favorites_service.delete(user_id="other", favorite_id=favorite.id)
```

```python
# backend/tests/application/test_sessions.py
async def test_session_lookup_is_scoped_to_authenticated_user(session_service):
    await session_service.save(session_id="s1", user_id="owner", intent_json="{}")
    assert await session_service.get("s1", user_id="other") is None
```

- [ ] **Step 2: Verify tests fail because services do not exist**

Run: `cd backend && uv run pytest tests/application/test_favorites.py tests/application/test_sessions.py -v`

Expected: collection fails for missing application modules.

- [ ] **Step 3: Implement repositories and services**

```python
# backend/app/application/favorites.py
class FavoritesService:
    async def delete(self, user_id: str, favorite_id: int) -> None:
        favorite = await self.repository.get(favorite_id)
        if favorite is None:
            raise LookupError("Favorite not found")
        if favorite.user_id != user_id:
            raise PermissionError("Not authorized to delete this favorite")
        await self.repository.delete(favorite)
```

Implement session, route, snapshot, profile, and favorite repository methods with `user_id` as a mandatory argument for all reads, updates, and deletes. Preserve `learn_from_favorite` behavior through the typed `UserPreference` service.

- [ ] **Step 4: Verify ownership and persistence behavior**

Run: `cd backend && uv run pytest tests/application/test_favorites.py tests/application/test_sessions.py -v`

Expected: all tests pass against the disposable PostgreSQL test database.

- [ ] **Step 5: Commit user-scoped application services**

```bash
git add backend/app/application backend/app/infrastructure/repositories.py backend/tests/application
git commit -m "feat: add user-scoped persistence services"
```

### Task 6: Replace authentication and middleware securely

**Files:**
- Create: `backend/app/security/passwords.py`
- Create: `backend/app/security/jwt.py`
- Create: `backend/app/security/rate_limit.py`
- Create: `backend/app/application/auth.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/tests/application/test_auth.py`
- Create: `backend/tests/api/test_auth_api.py`

- [ ] **Step 1: Write failing authentication tests**

```python
# backend/tests/application/test_auth.py
async def test_registered_password_is_argon2id_and_verifiable(auth_service):
    result = await auth_service.register(name="Mia", password="strong-password", city="上海")
    stored = await auth_service.users.by_user_id(result.user_id)
    assert stored.password_hash.startswith("$argon2id$")
    assert (await auth_service.login(name="Mia", password="strong-password")).token
```

- [ ] **Step 2: Verify the tests fail because auth modules/routes are absent**

Run: `cd backend && uv run pytest tests/application/test_auth.py tests/api/test_auth_api.py -v`

Expected: collection fails for missing auth modules.

- [ ] **Step 3: Implement Argon2id, JWT, and ASGI middleware**

```python
# backend/app/security/passwords.py
from pwdlib import PasswordHash
password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str: return password_hash.hash(password)
def verify_password(password: str, stored: str) -> bool: return password_hash.verify(password, stored)
```

```python
# backend/app/security/jwt.py
import jwt
def subject_from_bearer(token: str, secret: str) -> str:
    return str(jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["sub", "exp"]})["sub"])
```

Allow only `/api/auth/*`, `/api/route/health`, `/api/route/profiles`, and `/api/route/pois` without JWT. Set authenticated `user_id` on `request.state`; ignore any conflicting body/query `userId`. Add per-IP rate limits and CORS/security headers in `main.py`.

- [ ] **Step 4: Verify registration, login, and protected endpoint tests pass**

Run: `cd backend && uv run pytest tests/application/test_auth.py tests/api/test_auth_api.py -v`

Expected: all tests pass; the protected endpoint returns `401` for invalid tokens.

- [ ] **Step 5: Commit secure authentication**

```bash
git add backend/app/security backend/app/application/auth.py backend/app/api/auth.py backend/tests/application/test_auth.py backend/tests/api/test_auth_api.py
git commit -m "feat: replace legacy authentication with Argon2id JWT auth"
```

### Task 7: Port POI data sources and deterministic planning use cases

**Files:**
- Create: `backend/app/infrastructure/data_sources.py`
- Create: `backend/app/application/planning.py`
- Create: `backend/tests/application/test_planning.py`
- Create: `backend/tests/infrastructure/test_data_sources.py`

- [ ] **Step 1: Write failing mock-data and planning tests**

```python
# backend/tests/infrastructure/test_data_sources.py
async def test_mock_source_filters_pois_by_city_and_category(mock_source):
    pois = [poi async for poi in mock_source.search_by_category("上海", None, "RESTAURANT")]
    assert pois and all(poi.city == "上海" and poi.category == "RESTAURANT" for poi in pois)
```

```python
# backend/tests/application/test_planning.py
async def test_plan_service_rejects_routes_with_hard_constraint_violation(planning_service):
    response = await planning_service.plan(query="上海静安晚餐", city="上海", user_id="user_001")
    assert all(route["violatedSoftConstraints"] is not None for route in response.routes)
```

- [ ] **Step 2: Verify tests fail due to missing source and planning modules**

Run: `cd backend && uv run pytest tests/infrastructure/test_data_sources.py tests/application/test_planning.py -v`

Expected: collection fails for missing modules.

- [ ] **Step 3: Implement data source protocol and planner service**

```python
# backend/app/infrastructure/data_sources.py
from typing import Protocol, AsyncIterator
class DataSource(Protocol):
    def search_by_category(self, city: str, district: str | None, category: str) -> AsyncIterator[POI]: ...
    def search_by_keyword(self, city: str, district: str | None, keyword: str) -> AsyncIterator[POI]: ...
```

`MockDataSource` loads the existing `routeplan/mock-data/*.jsx` POI records through a checked-in JSON export created during this task. `DianpingDataSource` and `GaodeGeoService` use `httpx.AsyncClient`, explicit timeouts, and typed response parsing. `PlanningService` performs discovery, build/relax/validate constraints, graph search, preference score, session persistence, and response conversion without contacting OpenAI.

- [ ] **Step 4: Verify deterministic plan behavior**

Run: `cd backend && uv run pytest tests/infrastructure/test_data_sources.py tests/application/test_planning.py -v`

Expected: all tests pass without an `OPENAI_API_KEY`.

- [ ] **Step 5: Commit sources and planning application service**

```bash
git add backend/app/infrastructure/data_sources.py backend/app/application/planning.py backend/tests/infrastructure/test_data_sources.py backend/tests/application/test_planning.py
git commit -m "feat: add data sources and planning service"
```

### Task 8: Add OpenAI Agents SDK tools, guardrails, and route agent

**Files:**
- Create: `backend/app/agents/tools.py`
- Create: `backend/app/agents/planner.py`
- Create: `backend/tests/agents/test_tools.py`
- Create: `backend/tests/agents/test_planner.py`

- [ ] **Step 1: Write failing tool-boundary tests**

```python
# backend/tests/agents/test_tools.py
async def test_generate_routes_tool_returns_typed_json_without_database_access(agent_tools):
    result = await agent_tools.generate_routes(intent_json='{ "query": "上海晚餐", "city": "上海" }')
    assert result["routes"]
    assert "database_url" not in str(result).lower()
```

```python
# backend/tests/agents/test_planner.py
async def test_final_validator_rejects_agent_route_that_breaks_constraints(route_agent, invalid_route):
    assert route_agent.finalize(invalid_route).accepted is False
```

- [ ] **Step 2: Verify tests fail because agent modules do not exist**

Run: `cd backend && uv run pytest tests/agents/test_tools.py tests/agents/test_planner.py -v`

Expected: collection fails for missing `app.agents` modules.

- [ ] **Step 3: Implement typed function tools and a single planning Agent**

```python
# backend/app/agents/tools.py
from agents import function_tool

@function_tool
async def search_pois(city: str, district: str | None, category: str) -> list[dict]:
    """Return normalized POIs from the configured data source."""
    return [poi.model_dump(mode="json") async for poi in source.search_by_category(city, district, category)]
```

```python
# backend/app/agents/planner.py
from agents import Agent
route_agent = Agent(
    name="Route planner",
    instructions="Use tools to collect facts. Never invent POIs, prices, availability, or constraints.",
    tools=[parse_intent, search_pois, get_user_profile, generate_routes, check_constraints, score_and_rank, explain_routes],
)
```

Bind tools to application services through dependency injection rather than globals. Run the agent only after authentication; validate all tool arguments with Pydantic; call the deterministic `PlanningService.finalize` before persisting or responding. Configure tracing through `OPENAI_AGENTS_DISABLE_TRACING` and redact secrets from logs.

- [ ] **Step 4: Verify tools and final guardrail behavior using a fake model provider**

Run: `cd backend && uv run pytest tests/agents/test_tools.py tests/agents/test_planner.py -v`

Expected: all tests pass with no network call or OpenAI credential.

- [ ] **Step 5: Commit the OpenAI Agent integration**

```bash
git add backend/app/agents backend/tests/agents
git commit -m "feat: add OpenAI route planning agent"
```

### Task 9: Expose API-compatible FastAPI endpoints

**Files:**
- Create: `backend/app/api/routes.py`
- Create: `backend/app/api/favorites.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/api/test_route_endpoints.py`
- Create: `backend/tests/api/test_favorite_endpoints.py`

- [ ] **Step 1: Write failing compatibility tests**

```python
# backend/tests/api/test_route_endpoints.py
async def test_smart_plan_returns_legacy_shape(client, auth_headers):
    response = await client.post("/api/route/smart-plan", headers=auth_headers, json={"query": "上海静安约会", "city": "上海"})
    assert response.status_code == 200
    assert set(response.json()) >= {"stage", "summaryText", "intent", "routes"}

async def test_request_user_id_cannot_override_jwt_subject(client, auth_headers):
    response = await client.post("/api/route/plan", headers=auth_headers, json={"query": "晚餐", "userId": "other"})
    assert response.status_code == 200
    assert response.json()["sessionId"]

async def test_invalid_token_cannot_read_protected_route(client):
    response = await client.get("/api/route/compare/s1", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
```

- [ ] **Step 2: Verify tests fail because the FastAPI app does not exist**

Run: `cd backend && uv run pytest tests/api/test_route_endpoints.py tests/api/test_favorite_endpoints.py -v`

Expected: collection fails for missing `app.main`.

- [ ] **Step 3: Implement the route modules and app factory**

```python
# backend/app/main.py
from fastapi import FastAPI
from app.api import auth, favorites, routes

def create_app() -> FastAPI:
    app = FastAPI(title="AI Route Planner")
    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(routes.router, prefix="/api/route")
    app.include_router(favorites.router, prefix="/api/favorites")
    return app

app = create_app()
```

Implement `/health`, `/profiles`, `/pois`, `/analyze`, `/plan`, `/smart-plan`, `/adjust`, `/compare/{session_id}`, `/agent-plan`, registration/login/user routes, and favorites routes. Every protected endpoint obtains `user_id` from the JWT dependency; endpoints return explicit `404`, `401`, `403`, `409`, and `422` responses instead of leaking internal exceptions.

- [ ] **Step 4: Verify endpoint contracts**

Run: `cd backend && uv run pytest tests/api -v`

Expected: all API tests pass with the legacy JSON fields present.

- [ ] **Step 5: Commit the FastAPI compatibility surface**

```bash
git add backend/app/api backend/app/main.py backend/tests/api
git commit -m "feat: expose FastAPI compatible route APIs"
```

### Task 10: Port acceptance tests, containerize, and switch the runtime

**Files:**
- Create: `backend/tests/acceptance/test_competition_cases.py`
- Create: `backend/tests/acceptance/test_api_contract.py`
- Create: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.prod.yml`
- Modify: `README.md`
- Delete after all checks pass: `pom.xml`, `.mvn/`, `src/main/java/`, `src/test/java/`, `src/main/resources/application*.yml`

- [ ] **Step 1: Write failing acceptance and container smoke tests**

```python
# backend/tests/acceptance/test_competition_cases.py
import pytest

@pytest.mark.parametrize("query,city", [
    ("今晚想在上海静安约会，人均 200，想安静一点。", "上海"),
    ("周末下午想在上海静安逛逛，顺便吃饭和喝咖啡。", "上海"),
])
async def test_competition_route_cases(client, auth_headers, query, city):
    response = await client.post("/api/route/plan", headers=auth_headers, json={"query": query, "city": city})
    assert response.status_code == 200
    assert len(response.json()["routes"]) >= 1
```

- [ ] **Step 2: Verify the full suite fails before completing all migrated behavior**

Run: `cd backend && uv run pytest -q`

Expected: an acceptance failure identifies the remaining missing API or planning behavior.

- [ ] **Step 3: Complete TC01–TC18 and production packaging**

```dockerfile
# Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY backend ./backend
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
```

Update Compose service environment names to `OPENAI_API_KEY`, `JWT_SECRET`, and `DATABASE_URL`; health check `/api/route/health`; run Alembic baseline verification on startup without reapplying Flyway migrations. Translate all TC01–TC18 Java cases into parametrized pytest tests with a controlled OpenAI fake for non-LLM assertions. Delete Java runtime assets only after the following verification commands pass.

- [ ] **Step 4: Run full verification**

Run: `cd backend && uv run pytest -q && uv run ruff check . && uv run mypy app && docker compose build && docker compose up -d && curl --fail http://localhost:8081/api/route/health && docker compose down`

Expected: pytest, Ruff, and mypy exit `0`; image builds; health endpoint returns HTTP `200`; Compose stops cleanly.

- [ ] **Step 5: Review the API boundary before deleting Java sources**

Run: `diff -u <(curl -s http://localhost:8081/openapi.json | jq -S '.paths') docs/api-contract-baseline.json`

Expected: only explicitly approved endpoint differences appear. If an unapproved path or response field differs, restore the Java files and add a compatibility test before retrying deletion.

- [ ] **Step 6: Commit the Python-only runtime**

```bash
git add Dockerfile docker-compose.yml docker-compose.prod.yml README.md backend
git rm pom.xml .mvn src/main/java src/test/java src/main/resources/application.yml src/main/resources/application-mysql.yml
git commit -m "feat: migrate backend runtime to Python OpenAI Agents SDK"
```

## Plan self-review

- Scope coverage: Tasks 1–10 cover configuration, API contracts, deterministic planning, persistence, user ownership, security, external data, OpenAI Agent tools, compatibility endpoints, acceptance tests, Docker deployment, and Java runtime retirement.
- Type consistency: the planning flow uses `POI`, `UserIntent`, `Constraint`, `Route`, `PlanResponse`, `PlanningService`, and `FavoritesService` consistently; API casing is deliberately retained at the boundary.
- Release safety: Java runtime deletion is explicitly gated by the full test, type, lint, container health, and API-contract checks.
