# Python OpenAI Backend Migration Design

## Goal

Replace the Java/Spring runtime with a Python/FastAPI backend that preserves the
existing public API and PostgreSQL data model while using the OpenAI Agents SDK
for LLM-backed planning. The production runtime supports OpenAI only.

## Scope

- Replace the Java HTTP API, services, repositories, planner, Agent Loop,
  security filters, persistence integration, and external-data adapters.
- Preserve the existing `/api/auth`, `/api/route`, and `/api/favorites` API
  paths and response fields consumed by `routeplan/`.
- Preserve the current PostgreSQL schema initially; manage any Python-era
  changes through Alembic migrations.
- Port Java unit tests and the TC01–TC18 acceptance scenarios to pytest.
- Retain Java sources only as a temporary behavioral reference; do not run
  Java in the final deployment.

## Non-goals

- Supporting DeepSeek or a general multi-provider LLM abstraction.
- Changing the frontend user experience or API contract during the migration.
- Allowing an LLM to bypass deterministic route constraints or authorization.

## Architecture

```text
React frontend
       |
FastAPI API compatibility layer
       |
Application services
  |       |         |
Auth   Session    Favorites
  |       |         |
SQLAlchemy Async + PostgreSQL
       |
Route planning domain
  | intent/POI discovery/constraints/graph search/scoring
       |
OpenAI Agents SDK route-planning agent
  | function tools call application/domain services
OpenAI Responses API
```

`backend/api` owns request parsing, response compatibility, and HTTP error
translation. `backend/application` owns use cases and transactions.
`backend/domain` contains pure, deterministic models and route-planning logic.
`backend/infrastructure` owns SQLAlchemy repositories, external APIs, mock
data loading, and OpenAI configuration. `backend/agents` owns only the
OpenAI Agents SDK definitions, instructions, guardrails, and tool bindings.

## Request flow

1. `POST /api/route/smart-plan` authenticates the caller and resolves the
   user ID exclusively from the JWT.
2. The application service loads the profile and session state.
3. The route-planning Agent selects narrowly defined function tools for intent
   parsing, candidate discovery, route generation, constraint validation,
   scoring, and explanation.
4. Tool implementations call deterministic application/domain services; they
   never directly execute arbitrary database queries or external requests from
   model-provided strings.
5. The service validates the final route set, persists session/routes/snapshot
   records, and returns the legacy response schema.

`POST /plan`, `/adjust`, `/compare/{sessionId}`, favorites, and profile
operations use the same application services without requiring the Agent to
own persistence or authorization decisions.

## OpenAI integration

- The sole credential is `OPENAI_API_KEY`; startup fails when it is absent in
  non-development environments.
- The route-planning agent exposes typed Python function tools for:
  `parse_intent`, `search_pois`, `get_user_profile`, `generate_routes`,
  `check_constraints`, `score_and_rank`, and `explain_routes`.
- Tool schemas use Pydantic models. Every result is validated before it is
  returned to the Agent or API layer.
- A deterministic final validator rejects outputs that violate route, budget,
  time, ownership, or session invariants.
- SDK tracing is enabled through environment-controlled configuration. Logs
  record request and tool metadata but never API keys, passwords, or JWTs.

## Security

- Passwords use Argon2id via `pwdlib`; SHA-256 password hashes are not
  accepted for new credentials. A one-time compatibility migration must
  explicitly reset or migrate legacy users before Java removal.
- JWT signing requires `JWT_SECRET` and fails startup unless the environment
  is explicitly marked local development.
- Stored user-provided OpenAI keys are out of scope; the deployment-level
  `OPENAI_API_KEY` is the only supported LLM credential.
- Route and favorite ownership derives from the authenticated JWT user ID,
  not a request body or query parameter.
- Rate limiting, CORS, and security headers are implemented as FastAPI/ASGI
  middleware with configuration matching existing deployment needs.

## Data and compatibility

- SQLAlchemy mappings use the existing tables: users/profiles, sessions,
  routes, snapshots, and favorites.
- Alembic is introduced with a baseline migration that documents the existing
  schema without recreating production tables.
- JSON fields retain their existing serialized shapes while Python DTOs expose
  typed models internally.
- Mock POI data remains the default developer profile. Dianping/Meituan and
  Gaode adapters are ported behind explicit interfaces and selected by
  environment configuration.

## Testing and release gates

- Pytest unit tests cover model validation, constraints, graph search,
  preference scoring, password hashing, JWT authentication, and API errors.
- Contract tests assert response schemas for every frontend-facing endpoint.
- TC01–TC18 run against the Python application with mock data and deterministic
  OpenAI test doubles where an LLM response is not the subject under test.
- Integration tests use a disposable PostgreSQL database and mock external
  HTTP services.
- A Python implementation is accepted only after its contract and acceptance
  suite pass and its route output is comparable to the Java reference for the
  same deterministic inputs.

## Delivery sequence

1. Establish Python project, test harness, configuration, typed API contracts,
   and database baseline.
2. Port deterministic domain models, constraint engine, graph search, and
   their tests.
3. Port repositories, session/profile/favorites services, authentication, and
   API compatibility endpoints.
4. Port data-source adapters and route-planning application services.
5. Add OpenAI Agents SDK tools, agent guardrails, tracing, and agent endpoints.
6. Port acceptance/performance tests, execute compatibility checks, switch the
   deployment entrypoint to FastAPI, then remove Java runtime deployment files.

## Decisions

- The migration uses a clean Python implementation under `backend/`, rather
  than a Java/Python bridge.
- The final runtime is Python only; Java code is migration reference material
  until compatibility verification is complete.
- The external API and PostgreSQL schema remain stable during the initial
  cutover.
- OpenAI is the only LLM provider.
