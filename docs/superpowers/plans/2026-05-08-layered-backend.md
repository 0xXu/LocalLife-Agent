# Layered Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, layered Python backend for WeekendPilot while leaving the existing frontend demo unchanged.

**Architecture:** Add a Python `backend/` package modeled after the reference repository's separation of `api/`, `models/`, `agents/`, `tools/`, `orchestrator/`, and `services/`. The backend uses deterministic mock data and stdlib HTTP serving so it runs without additional dependencies, but its boundaries mirror the detailed design document: orchestrator, specialized agents, tools, execution, recovery, and trace store.

**Tech Stack:** Python 3.11+ standard library, dataclasses, unittest, `http.server`.

---

### Task 1: Contract Tests

**Files:**
- Create: `tests/backend/test_pipeline.py`
- Create: `tests/backend/test_api.py`

- [ ] Write pipeline tests for `PlanningService.build_plan`, `execute_plan`, and `recover_plan`.
- [ ] Write API tests for `GET /api/health`, `POST /api/plans/build`, `POST /api/plans/{id}/execute`, and `POST /api/plans/{id}/recover`.
- [ ] Run `python -m unittest discover -s tests -p "test_*.py"` and verify failures are import/feature-missing failures.

### Task 2: Backend Domain And Tools

**Files:**
- Create: `backend/models/schemas.py`
- Create: `backend/tools/poi_repository.py`
- Create: `backend/tools/availability.py`
- Create: `backend/tools/routing.py`
- Create: `backend/tools/execution.py`
- Create: `backend/tools/trace_store.py`
- Create: `backend/data/poi_seed.json`

- [ ] Implement dataclass schemas for constraints, POI, itinerary steps, plan actions, trace steps, receipts, recovery diff, and plan state.
- [ ] Implement repository and mock tool adapters with no UI imports.
- [ ] Keep all side-effect-like actions in `tools/execution.py`.

### Task 3: Agents And Orchestration

**Files:**
- Create: `backend/agents/base.py`
- Create: `backend/agents/intent_parser.py`
- Create: `backend/agents/context_builder.py`
- Create: `backend/agents/candidate_search.py`
- Create: `backend/agents/ranker.py`
- Create: `backend/agents/route_scheduler.py`
- Create: `backend/agents/validator.py`
- Create: `backend/agents/executor.py`
- Create: `backend/agents/recovery.py`
- Create: `backend/orchestrator/pipeline.py`
- Create: `backend/orchestrator/parallel.py`
- Create: `backend/orchestrator/recovery_loop.py`

- [ ] Implement `BaseAgent.run` as a template method that records trace spans.
- [ ] Implement specialized agents that mutate and return `PlanState`.
- [ ] Implement the pipeline order: parse -> context -> search -> rank -> route -> validate -> ready for confirmation.
- [ ] Implement recovery that replaces only the failed restaurant node.

### Task 4: Service And API

**Files:**
- Create: `backend/services/planning_service.py`
- Create: `backend/api/app.py`
- Create: `backend/__init__.py` and package `__init__.py` files

- [ ] Implement `PlanningService` as the app-facing facade and in-memory plan store.
- [ ] Implement stdlib JSON API with CORS and the four required routes.
- [ ] Make API response shapes compatible with the current frontend data concepts.

### Task 5: Documentation And Verification

**Files:**
- Modify: `README.md`
- Create: `backend/README.md`

- [ ] Document backend run and test commands for PowerShell and Bash.
- [ ] Run `python -m unittest discover -s tests -p "test_*.py"`.
- [ ] Run existing frontend Node tests when Node is available.
- [ ] Run Python compile check for backend modules.

