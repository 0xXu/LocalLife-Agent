# Multi-Agent Graph Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the linear 7-node pipeline into a true graph with parallel search branches, 3 LLM-driven agents (Ranker, Validator, Recovery), conditional routing, and a recovery loop.

**Architecture:** The pipeline becomes a LangGraph `StateGraph` with fan-out parallel search, LLM-driven decision-making in rank/validate/recover nodes, and a conditional loop where validation failures route to a recovery agent that can re-rank and re-validate (max 3 attempts). The `parse_intent` node remains unchanged. Deterministic helpers (route optimization, itinerary building, variant generation) stay as pure functions called by agents.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, LangChain (for `Send` fan-out pattern), existing LLMClient (OpenAI-compatible HTTP), pytest.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/models/schemas.py` | Modify | Add `recovery_attempts` and `agent_decisions` fields to `PlanState` |
| `backend/agents/__init__.py` | Create | Export agent classes |
| `backend/agents/base.py` | Create | `BaseAgent` with shared LLM call + JSON parse + trace helpers |
| `backend/agents/ranker.py` | Create | `RankerAgent` — LLM selects top candidates and explains reasoning |
| `backend/agents/validator.py` | Create | `ValidatorAgent` — LLM holistically evaluates plan quality |
| `backend/agents/recovery.py` | Create | `RecoveryAgent` — LLM decides which node to fix and how |
| `backend/orchestrator/pipeline.py` | Modify | New graph topology: parallel search, conditional routing, recovery loop |
| `backend/orchestrator/nodes.py` | Create | Extract non-agent node functions (build_context, search, build_itinerary, prepare_confirmation) |
| `backend/orchestrator/search.py` | Create | Parallel search node functions |
| `tests/backend/test_agents.py` | Create | Unit tests for 3 new agents |
| `tests/backend/test_graph_topology.py` | Create | Tests for parallel execution, conditional routing, recovery loop |
| `tests/backend/test_pipeline.py` | Modify | Update existing pipeline tests for new graph |

---

## Task 1: Extend PlanState with agent tracking fields

**Files:**
- Modify: `backend/models/schemas.py:227-251`
- Test: `tests/backend/test_agents.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/backend/test_agents.py
from backend.models.schemas import PlanState


def test_plan_state_has_recovery_tracking():
    state = PlanState(goal="test")
    assert state.recovery_attempts == 0
    assert state.agent_decisions == {}


def test_plan_state_increment_recovery():
    state = PlanState(goal="test")
    state.recovery_attempts += 1
    assert state.recovery_attempts == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_agents.py::test_plan_state_has_recovery_tracking -xvs`
Expected: FAIL with `AttributeError: 'PlanState' object has no attribute 'recovery_attempts'`

- [ ] **Step 3: Add fields to PlanState**

Add two new fields to the `PlanState` dataclass in `backend/models/schemas.py`:

```python
@dataclass
class PlanState:
    # ... existing fields ...
    validation_issues: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recovery_attempts: int = 0                          # NEW
    agent_decisions: dict[str, Any] = field(default_factory=dict)  # NEW
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_agents.py::test_plan_state_has_recovery_tracking tests/backend/test_agents.py::test_plan_state_increment_recovery -xvs`
Expected: PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/ -x -q`
Expected: 131 passed (same as before)

- [ ] **Step 6: Commit**

```bash
git add backend/models/schemas.py tests/backend/test_agents.py
git commit -m "feat: add recovery_attempts and agent_decisions fields to PlanState"
```

---

## Task 2: Create BaseAgent with shared LLM + JSON + trace helpers

**Files:**
- Create: `backend/agents/__init__.py`
- Create: `backend/agents/base.py`
- Test: `tests/backend/test_agents.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_agents.py`:

```python
import json
from backend.agents.base import BaseAgent


class FakeLLM:
    def __init__(self, response: dict):
        self._response = response
        self.calls = []

    def chat_stream(self, messages):
        self.calls.append(messages)
        yield json.dumps(self._response, ensure_ascii=False)


def test_base_agent_calls_llm_and_parses_json():
    llm = FakeLLM({"decision": "approve", "reason": "looks good"})
    agent = BaseAgent("TestAgent", llm)

    result = agent.run_llm("test prompt", {"key": "value"})

    assert result == {"decision": "approve", "reason": "looks good"}
    assert len(llm.calls) == 1
    assert "test prompt" in llm.calls[0][-1]["content"]


def test_base_agent_returns_none_on_llm_failure():
    class BrokenLLM:
        def chat_stream(self, messages):
            raise RuntimeError("LLM down")

    agent = BaseAgent("TestAgent", BrokenLLM())
    result = agent.run_llm("test", {})

    assert result is None


def test_base_agent_build_trace():
    llm = FakeLLM({"result": "ok"})
    agent = BaseAgent("TestAgent", llm)
    agent.run_llm("test", {})
    trace = agent.build_trace("ok", "did something", {"input": 1}, {"result": "ok"})

    assert trace.agent == "TestAgent"
    assert trace.status == "ok"
    assert trace.message == "did something"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_agents.py::test_base_agent_calls_llm_and_parses_json -xvs`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.agents'`

- [ ] **Step 3: Create backend/agents/__init__.py**

```python
from .base import BaseAgent

__all__ = ["BaseAgent"]
```

- [ ] **Step 4: Create backend/agents/base.py**

```python
from __future__ import annotations

import json
import re
from typing import Any

from backend.models.schemas import TraceStep
from backend.observability.spans import span


class BaseAgent:
    def __init__(self, name: str, llm: Any) -> None:
        self.name = name
        self.llm = llm
        self._last_messages: list[dict[str, str]] = []

    def run_llm(self, system_prompt: str, context: dict[str, Any], max_tokens: int = 1024) -> dict[str, Any] | None:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ]
        self._last_messages = messages
        try:
            content = ""
            for token in self.llm.chat_stream(messages):
                content += token
            return json.loads(extract_json_object(content))
        except Exception:
            return None

    def build_trace(self, status: str, message: str, input_summary: dict, output_summary: dict, duration_ms: int = 150) -> TraceStep:
        return span(self.name, self.name.lower().replace("agent", ""), status, message, "llm", input_summary, output_summary, duration_ms, {"model": "mimo"})


def extract_json_object(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("llm_json_not_found")
    return stripped[start:end + 1]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_agents.py -xvs`
Expected: PASS (all 5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/agents/ tests/backend/test_agents.py
git commit -m "feat: add BaseAgent with LLM call, JSON parse, and trace helpers"
```

---

## Task 3: Create RankerAgent (LLM-driven candidate selection)

**Files:**
- Create: `backend/agents/ranker.py`
- Test: `tests/backend/test_agents.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_agents.py`:

```python
from backend.agents.ranker import RankerAgent
from backend.models.schemas import ParsedConstraints


def test_ranker_agent_selects_top_candidates():
    candidates = {
        "activities": [
            {"id": "a1", "name": "Park A", "rating": 4.8, "tags": ["outdoor", "quiet"], "distance_km": 1.2, "avg_price": 0, "wait_minutes": 0},
            {"id": "a2", "name": "Museum B", "rating": 4.2, "tags": ["indoor", "art"], "distance_km": 3.5, "avg_price": 80, "wait_minutes": 15},
        ],
        "restaurants": [
            {"id": "r1", "name": "Cafe C", "rating": 4.5, "tags": ["quiet", "cafe"], "distance_km": 0.8, "avg_price": 60, "wait_minutes": 5},
        ],
        "walks": [],
    }
    constraints = ParsedConstraints(
        scenario="date",
        origin={"lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 3},
        people={"adults": 2, "children": [], "relationship": "date"},
        preferences={"activity": ["quiet", "romantic"], "budget_level": "medium"},
        constraints={"radius_km": 8, "max_wait_minutes": 15},
        required_actions=["send_plan_message"],
    )

    llm_response = {
        "ranked": {
            "activities": [{"id": "a1", "reason": "Best match for quiet date"}],
            "restaurants": [{"id": "r1", "reason": "Close and quiet"}],
            "walks": [],
        },
        "reasoning": "Prioritized quiet and close venues for a date scenario.",
    }
    llm = FakeLLM(llm_response)
    agent = RankerAgent(llm)

    result = agent.rank(candidates, constraints)

    assert "a1" in [item["id"] for item in result["activities"]]
    assert agent.last_reasoning == "Prioritized quiet and close venues for a date scenario."


def test_ranker_agent_falls_back_to_deterministic_on_llm_failure():
    candidates = {
        "activities": [
            {"id": "a1", "name": "Park A", "rating": 4.8, "tags": ["outdoor"], "distance_km": 1.2, "avg_price": 0, "wait_minutes": 0},
        ],
        "restaurants": [],
        "walks": [],
    }
    constraints = ParsedConstraints(
        scenario="family",
        origin={"lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 3},
        people={"adults": 2, "children": [{"age": 5}], "relationship": "family"},
        preferences={"activity": ["child_friendly"], "budget_level": "medium"},
        constraints={"radius_km": 8, "max_wait_minutes": 15},
        required_actions=["send_plan_message"],
    )

    class BrokenLLM:
        def chat_stream(self, messages):
            raise RuntimeError("LLM down")

    agent = RankerAgent(BrokenLLM())
    result = agent.rank(candidates, constraints)

    # Falls back to deterministic ranking — still returns candidates
    assert len(result["activities"]) == 1
    assert result["activities"][0]["id"] == "a1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_agents.py::test_ranker_agent_selects_top_candidates -xvs`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.agents.ranker'`

- [ ] **Step 3: Create backend/agents/ranker.py**

```python
from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.models.schemas import ParsedConstraints


class RankerAgent(BaseAgent):
    def __init__(self, llm: Any) -> None:
        super().__init__("RankerAgent", llm)
        self.last_reasoning: str = ""

    def rank(self, candidates: dict[str, list[dict]], constraints: ParsedConstraints) -> dict[str, list[dict]]:
        system_prompt = (
            "You are a local-life planning ranker. Given candidates and user constraints, "
            "select the best items for each category (activities, restaurants, walks). "
            "Return JSON: {\"ranked\": {\"activities\": [{\"id\": \"...\", \"reason\": \"...\"}], "
            "\"restaurants\": [...], \"walks\": [...]}, \"reasoning\": \"...\"}\n"
            "Select 1-3 items per category. Prefer items matching user tags, closer distance, "
            "lower wait time, and appropriate budget level."
        )
        context = {
            "candidates": {k: [_candidate_brief(item) for item in v] for k, v in candidates.items()},
            "constraints": {
                "scenario": constraints.scenario,
                "activity_tags": constraints.preferences.get("activity", []),
                "diet_tags": constraints.preferences.get("diet", []),
                "budget_level": constraints.preferences.get("budget_level", "medium"),
                "radius_km": constraints.constraints.get("radius_km", 8),
                "max_wait_minutes": constraints.constraints.get("max_wait_minutes", 15),
                "people": constraints.people,
            },
        }

        result = self.run_llm(system_prompt, context)
        if result and "ranked" in result:
            self.last_reasoning = result.get("reasoning", "")
            return _merge_ranked_with_candidates(result["ranked"], candidates)

        # Fallback: deterministic ranking by existing score
        self.last_reasoning = "LLM unavailable, using deterministic fallback."
        return _deterministic_fallback(candidates)


def _candidate_brief(item: dict) -> dict:
    return {
        "id": item["id"],
        "name": item["name"],
        "rating": item.get("rating", 0),
        "tags": item.get("tags", []),
        "distance_km": item.get("distance_km", 0),
        "avg_price": item.get("avg_price", 0),
        "wait_minutes": item.get("wait_minutes", 0),
    }


def _merge_ranked_with_candidates(ranked: dict[str, list[dict]], candidates: dict[str, list[dict]]) -> dict[str, list[dict]]:
    candidate_lookup: dict[str, dict] = {}
    for items in candidates.values():
        for item in items:
            candidate_lookup[item["id"]] = item

    result: dict[str, list[dict]] = {}
    for category in ("activities", "restaurants", "walks"):
        llm_selections = ranked.get(category, [])
        merged = []
        seen_ids: set[str] = set()
        for sel in llm_selections:
            sid = str(sel.get("id", ""))
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            full = candidate_lookup.get(sid, {})
            if full:
                enriched = dict(full)
                enriched["llm_reason"] = sel.get("reason", "")
                merged.append(enriched)
        result[category] = merged
    return result


def _deterministic_fallback(candidates: dict[str, list[dict]]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for category, items in candidates.items():
        sorted_items = sorted(items, key=lambda x: (-float(x.get("rating", 0)), float(x.get("distance_km", 99))))
        result[category] = sorted_items[:3]
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_agents.py::test_ranker_agent_selects_top_candidates tests/backend/test_agents.py::test_ranker_agent_falls_back_to_deterministic_on_llm_failure -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/ranker.py tests/backend/test_agents.py
git commit -m "feat: add RankerAgent with LLM-driven candidate selection and deterministic fallback"
```

---

## Task 4: Create ValidatorAgent (LLM-driven plan evaluation)

**Files:**
- Create: `backend/agents/validator.py`
- Test: `tests/backend/test_agents.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_agents.py`:

```python
from backend.agents.validator import ValidatorAgent
from backend.models.schemas import ItineraryStep


def test_validator_agent_approves_good_plan():
    itinerary = [
        ItineraryStep("14:00", "14:15", "transport", "出发", "origin_home", "", "约 35 元", "打车 12 分钟"),
        ItineraryStep("14:15", "15:45", "activity", "Park A", "a1", "quiet outdoor", "约 0 元", "到达", 92),
        ItineraryStep("16:00", "17:00", "restaurant", "Cafe C", "r1", "good food", "约 80 元", "步行 10 分钟", 88),
    ]
    constraints_data = {"scenario": "date", "budget_level": "medium", "duration_hours": 3}
    weather = {"condition": "sunny"}

    llm_response = {"valid": True, "issues": [], "suggestions": [], "overall_score": 90}
    llm = FakeLLM(llm_response)
    agent = ValidatorAgent(llm)

    result = agent.validate(itinerary, constraints_data, weather)

    assert result["valid"] is True
    assert result["overall_score"] == 90


def test_validator_agent_rejects_bad_plan():
    itinerary = [
        ItineraryStep("14:00", "14:15", "transport", "出发", "origin_home", "", "约 35 元", "打车 12 分钟"),
        ItineraryStep("14:15", "15:45", "activity", "Outdoor Park", "a1", "outdoor", "约 0 元", "到达", 60),
    ]
    constraints_data = {"scenario": "rainy_indoor", "budget_level": "low"}
    weather = {"condition": "rain"}

    llm_response = {
        "valid": False,
        "issues": [{"code": "weather_mismatch", "detail": "Outdoor activity during rain", "severity": "blocking"}],
        "suggestions": ["Switch to indoor activity"],
        "overall_score": 35,
    }
    llm = FakeLLM(llm_response)
    agent = ValidatorAgent(llm)

    result = agent.validate(itinerary, constraints_data, weather)

    assert result["valid"] is False
    assert len(result["issues"]) == 1
    assert result["issues"][0]["code"] == "weather_mismatch"


def test_validator_agent_falls_back_to_rules_on_llm_failure():
    itinerary = [
        ItineraryStep("14:00", "14:15", "transport", "出发", "origin_home", "", "约 35 元", "打车 12 分钟"),
        ItineraryStep("14:15", "15:45", "activity", "Park A", "a1", "outdoor", "约 0 元", "到达", 92),
    ]
    constraints_data = {"scenario": "family", "budget_level": "medium", "duration_hours": 3}
    weather = {"condition": "sunny"}

    class BrokenLLM:
        def chat_stream(self, messages):
            raise RuntimeError("LLM down")

    agent = ValidatorAgent(BrokenLLM())
    result = agent.validate(itinerary, constraints_data, weather)

    # Fallback uses rule-based validation
    assert "valid" in result
    assert "issues" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_agents.py::test_validator_agent_approves_good_plan -xvs`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create backend/agents/validator.py**

```python
from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.models.schemas import ItineraryStep, to_dict
from backend.validation.rules import validate_itinerary


class ValidatorAgent(BaseAgent):
    def __init__(self, llm: Any) -> None:
        super().__init__("ValidatorAgent", llm)

    def validate(
        self,
        itinerary: list[ItineraryStep],
        constraints_data: dict[str, Any],
        weather: dict[str, Any],
        candidate_lookup: dict[str, dict] | None = None,
        route: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        system_prompt = (
            "You are a plan validator for a local-life planner. Evaluate the itinerary holistically. "
            "Check: 1) Do activities match the scenario? 2) Are times reasonable? 3) Is budget appropriate? "
            "4) Does weather conflict with outdoor activities? 5) Is the route efficient? "
            "Return JSON: {\"valid\": bool, \"issues\": [{\"code\": \"...\", \"detail\": \"...\", \"severity\": \"blocking|warning\"}], "
            "\"suggestions\": [\"...\"], \"overall_score\": int(0-100)}"
        )
        context = {
            "itinerary": [to_dict(step) for step in itinerary],
            "constraints": constraints_data,
            "weather": weather,
        }

        result = self.run_llm(system_prompt, context)
        if result and "valid" in result:
            return result

        # Fallback: rule-based validation
        return self._rule_based_fallback(itinerary, constraints_data, weather, candidate_lookup, route)

    def _rule_based_fallback(
        self,
        itinerary: list[ItineraryStep],
        constraints_data: dict[str, Any],
        weather: dict[str, Any],
        candidate_lookup: dict[str, dict] | None,
        route: dict[str, Any] | None,
    ) -> dict[str, Any]:
        from backend.models.schemas import ParsedConstraints

        constraints = ParsedConstraints(
            scenario=constraints_data.get("scenario", "family"),
            origin=constraints_data.get("origin", {}),
            time_window=constraints_data.get("time_window", {}),
            people=constraints_data.get("people", {}),
            preferences=constraints_data.get("preferences", {"budget_level": constraints_data.get("budget_level", "medium")}),
            constraints=constraints_data.get("constraints", {}),
            required_actions=constraints_data.get("required_actions", []),
        )
        report = validate_itinerary(itinerary, constraints, candidate_lookup or {}, weather, route or {})
        return {
            "valid": report.valid,
            "issues": [{"code": issue["code"], "detail": str(issue), "severity": "blocking"} for issue in report.issues],
            "suggestions": [],
            "overall_score": 85 if report.valid else 40,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_agents.py -xvs`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add backend/agents/validator.py tests/backend/test_agents.py
git commit -m "feat: add ValidatorAgent with LLM-driven plan evaluation and rule-based fallback"
```

---

## Task 5: Create RecoveryAgent (LLM-driven failure recovery)

**Files:**
- Create: `backend/agents/recovery.py`
- Test: `tests/backend/test_agents.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_agents.py`:

```python
from backend.agents.recovery import RecoveryAgent


def test_recovery_agent_decides_to_replace_restaurant():
    issues = [{"code": "closed_at_visit_time", "detail": "Restaurant closes at 15:00", "severity": "blocking"}]
    itinerary_summary = [
        {"type": "activity", "place_id": "a1", "title": "Park A"},
        {"type": "restaurant", "place_id": "r1", "title": "Closed Cafe"},
    ]
    alternatives = {
        "restaurants": [
            {"id": "r2", "name": "Open Cafe", "rating": 4.5},
            {"id": "r3", "name": "Another Cafe", "rating": 4.0},
        ]
    }

    llm_response = {
        "action": "replace",
        "target_type": "restaurant",
        "target_id": "r1",
        "replacement_id": "r2",
        "reason": "Restaurant is closed, switching to Open Cafe which is nearby and well-rated.",
    }
    llm = FakeLLM(llm_response)
    agent = RecoveryAgent(llm)

    result = agent.recover(issues, itinerary_summary, alternatives)

    assert result["action"] == "replace"
    assert result["replacement_id"] == "r2"


def test_recovery_agent_decides_plan_is_recoverable_with_minor_changes():
    issues = [{"code": "budget_overrun", "detail": "Budget too high", "severity": "warning"}]
    itinerary_summary = [{"type": "activity", "place_id": "a1", "title": "Expensive Activity"}]
    alternatives = {}

    llm_response = {
        "action": "adjust",
        "target_type": "activity",
        "target_id": "a1",
        "adjustment": "Keep activity but skip restaurant to reduce budget",
        "reason": "Budget slightly over, can be fixed by removing optional components.",
    }
    llm = FakeLLM(llm_response)
    agent = RecoveryAgent(llm)

    result = agent.recover(issues, itinerary_summary, alternatives)

    assert result["action"] == "adjust"


def test_recovery_agent_falls_back_on_llm_failure():
    issues = [{"code": "closed_at_visit_time", "severity": "blocking"}]
    itinerary_summary = [{"type": "restaurant", "place_id": "r1", "title": "Closed"}]
    alternatives = {"restaurants": [{"id": "r2", "name": "Backup"}]}

    class BrokenLLM:
        def chat_stream(self, messages):
            raise RuntimeError("LLM down")

    agent = RecoveryAgent(BrokenLLM())
    result = agent.recover(issues, itinerary_summary, alternatives)

    assert result["action"] == "replace"
    assert result["target_type"] == "restaurant"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_agents.py::test_recovery_agent_decides_to_replace_restaurant -xvs`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create backend/agents/recovery.py**

```python
from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent


class RecoveryAgent(BaseAgent):
    def __init__(self, llm: Any) -> None:
        super().__init__("RecoveryAgent", llm)

    def recover(
        self,
        issues: list[dict[str, Any]],
        itinerary_summary: list[dict[str, Any]],
        alternatives: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        system_prompt = (
            "You are a plan recovery agent. The validator found issues with the itinerary. "
            "Decide how to fix it. Options:\n"
            "- 'replace': swap a problematic node with an alternative\n"
            "- 'adjust': keep the plan but modify timing/budget/optional components\n"
            "- 'replan': the plan is too broken, needs full re-ranking\n"
            "Return JSON: {\"action\": \"replace|adjust|replan\", \"target_type\": \"activity|restaurant|walk\", "
            "\"target_id\": \"...\", \"replacement_id\": \"...\", \"adjustment\": \"...\", \"reason\": \"...\"}"
        )
        context = {
            "issues": issues,
            "itinerary": itinerary_summary,
            "alternatives": {k: [{"id": item["id"], "name": item.get("name", "")} for item in v] for k, v in alternatives.items()},
        }

        result = self.run_llm(system_prompt, context)
        if result and "action" in result:
            return result

        # Fallback: simple heuristic recovery
        return self._heuristic_fallback(issues, alternatives)

    def _heuristic_fallback(
        self,
        issues: list[dict[str, Any]],
        alternatives: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        blocking = [issue for issue in issues if issue.get("severity") == "blocking"]
        if not blocking:
            return {"action": "adjust", "reason": "No blocking issues, minor adjustments only."}

        first_issue = blocking[0]
        code = first_issue.get("code", "")

        if "restaurant" in code or "closed" in code:
            replacements = alternatives.get("restaurants", [])
            if replacements:
                return {
                    "action": "replace",
                    "target_type": "restaurant",
                    "replacement_id": replacements[0]["id"],
                    "reason": f"Heuristic: replacing restaurant due to {code}.",
                }

        if "weather" in code:
            replacements = alternatives.get("activities", [])
            indoor = [a for a in replacements if "indoor" in a.get("tags", [])]
            if indoor:
                return {
                    "action": "replace",
                    "target_type": "activity",
                    "replacement_id": indoor[0]["id"],
                    "reason": f"Heuristic: switching to indoor activity due to {code}.",
                }

        return {"action": "replan", "reason": f"Cannot heuristically recover from {code}, full replan needed."}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_agents.py -xvs`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add backend/agents/recovery.py tests/backend/test_agents.py
git commit -m "feat: add RecoveryAgent with LLM-driven recovery decisions and heuristic fallback"
```

---

## Task 6: Extract node functions into orchestrator/nodes.py and orchestrator/search.py

**Files:**
- Create: `backend/orchestrator/nodes.py`
- Create: `backend/orchestrator/search.py`
- Modify: `backend/orchestrator/__init__.py`

- [ ] **Step 1: Create backend/orchestrator/search.py**

Extract the search logic from `_search_candidates_node` into standalone functions that can be used as parallel graph nodes:

```python
from __future__ import annotations

from typing import Any

from backend.data.catalog import LocalDataCatalog
from backend.models.schemas import ParsedConstraints, PlanState, TraceStep
from backend.observability.spans import span
from backend.tools.registry import LocalToolRegistry


def search_activities(catalog: LocalDataCatalog, constraints: ParsedConstraints) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    activity_tags = list(constraints.preferences.get("activity", []))
    tools = LocalToolRegistry(catalog)
    result = tools.search_places(constraints.scenario, radius, activity_tags)
    return result.output["items"]


def search_restaurants(catalog: LocalDataCatalog, constraints: ParsedConstraints) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    restaurant_tags = list(constraints.preferences.get("diet", [])) or ["booking_supported"]
    tools = LocalToolRegistry(catalog)
    result = tools.search_restaurants(constraints.scenario, radius, restaurant_tags)
    return result.output["items"]


def search_walks(catalog: LocalDataCatalog, constraints: ParsedConstraints) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    walks = catalog.search_pois("dessert_walk", None, radius, ["walkable"])[:6]
    if not walks:
        tools = LocalToolRegistry(catalog)
        result = tools.search_places("date" if constraints.scenario == "date" else "family", radius, ["walkable"])
        walks = result.output["items"]
    return walks
```

- [ ] **Step 2: Create backend/orchestrator/nodes.py**

Extract non-agent node functions from `pipeline.py`:

```python
from __future__ import annotations

from typing import Any

from backend.data.catalog import LocalDataCatalog
from backend.models.schemas import ParsedConstraints, PlanState, TraceStep
from backend.observability.spans import span
from backend.tools.registry import LocalToolRegistry


def build_context_node(state: PlanState, catalog: LocalDataCatalog) -> PlanState:
    constraints = state.constraints
    rainy = constraints.scenario == "rainy_indoor" or "下雨" in state.goal or "雨" in state.goal
    tools = LocalToolRegistry(catalog)
    weather = tools.get_weather(rainy).output
    state.context = {**state.context, "weather": weather, "profile": "local_demo_user", "privacy": "minimal"}
    state.status = "context_ready"
    state.add_trace(span("ContextBuilderAgent", "get_weather", "ok", "补全天气、位置和用户偏好上下文。", "tool", {}, weather, 120, {"provider": "local_weather_seed"}))
    return state


def merge_search_results_node(state: PlanState, activities: list, restaurants: list, walks: list) -> PlanState:
    state.candidates = {
        "activities": activities,
        "restaurants": restaurants,
        "walks": walks,
    }
    state.status = "candidates_ready"
    state.add_trace(span(
        "CandidateSearchAgent", "search_places", "ok",
        "并行检索活动、餐厅、甜品散步点。",
        "tool", {}, {"activities": len(activities), "restaurants": len(restaurants), "walks": len(walks)}, 260,
        {"provider": "local_seed_catalog", "parallel": True},
    ))
    return state
```

- [ ] **Step 3: Update backend/orchestrator/__init__.py**

```python
from .pipeline import PlanningPipeline

__all__ = ["PlanningPipeline"]
```

- [ ] **Step 4: Run full test suite to verify no regressions**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/ -x -q`
Expected: 131 passed (existing tests still work, pipeline.py unchanged so far)

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/nodes.py backend/orchestrator/search.py backend/orchestrator/__init__.py
git commit -m "refactor: extract node functions and parallel search into orchestrator modules"
```

---

## Task 7: Refactor pipeline.py — new graph topology with parallel search and agent nodes

**Files:**
- Modify: `backend/orchestrator/pipeline.py`
- Test: `tests/backend/test_graph_topology.py`

- [ ] **Step 1: Write the failing tests for new graph topology**

Create `tests/backend/test_graph_topology.py`:

```python
import json
import unittest

from backend.llm.config import LLMConfig
from backend.orchestrator.pipeline import PlanningPipeline


class FakeRankerLLM:
    """Returns valid ranker JSON."""
    def chat_stream(self, messages):
        content = messages[-1]["content"]
        yield json.dumps({
            "ranked": {
                "activities": [{"id": "act_kid_science_001", "reason": "Good for kids"}],
                "restaurants": [{"id": "rest_healthy_001", "reason": "Healthy options"}],
                "walks": [{"id": "walk_river_001", "reason": "Nice riverside walk"}],
            },
            "reasoning": "Best combination for family outing.",
        }, ensure_ascii=False)


class FakeValidatorLLM:
    """Returns valid validator JSON."""
    def chat_stream(self, messages):
        yield json.dumps({
            "valid": True,
            "issues": [],
            "suggestions": [],
            "overall_score": 88,
        })


class FakeRecoveryLLM:
    """Returns valid recovery JSON."""
    def chat_stream(self, messages):
        yield json.dumps({
            "action": "replace",
            "target_type": "restaurant",
            "replacement_id": "rest_healthy_002",
            "reason": "Switching to backup restaurant.",
        })


class ChainedLLM:
    """Routes to different responses based on system prompt content."""
    def __init__(self, responses_by_keyword: dict[str, str]):
        self.responses = responses_by_keyword
        self.calls = []

    def chat_stream(self, messages):
        self.calls.append(messages)
        system = messages[0]["content"] if messages else ""
        for keyword, response in self.responses.items():
            if keyword in system:
                yield response
                return
        yield '{"valid": true, "issues": [], "overall_score": 85}'


class GraphTopologyTest(unittest.TestCase):
    def test_pipeline_graph_has_parallel_search_nodes(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://example.test/v1",
                api_key="secret",
                model="test",
                remote_enabled=True,
            )
        )
        graph_nodes = set(pipeline.graph.get_graph().nodes)

        # Should have parallel search nodes
        self.assertIn("search_activities", graph_nodes)
        self.assertIn("search_restaurants", graph_nodes)
        self.assertIn("search_walks", graph_nodes)
        self.assertIn("merge_search_results", graph_nodes)

    def test_pipeline_graph_has_agent_nodes(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://example.test/v1",
                api_key="secret",
                model="test",
                remote_enabled=True,
            )
        )
        graph_nodes = set(pipeline.graph.get_graph().nodes)

        # Should have agent nodes
        self.assertIn("ranker_agent", graph_nodes)
        self.assertIn("validator_agent", graph_nodes)
        self.assertIn("recovery", graph_nodes)

    def test_pipeline_build_with_multi_agent(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://example.test/v1",
                api_key="secret",
                model="test",
                remote_enabled=True,
            )
        )
        # Chain: intent → ranker → validator
        pipeline.llm = ChainedLLM({
            "planning ranker": json.dumps({
                "ranked": {
                    "activities": [{"id": "act_kid_science_001", "reason": "Best fit"}],
                    "restaurants": [{"id": "rest_healthy_001", "reason": "Healthy"}],
                    "walks": [{"id": "walk_river_001", "reason": "Nice walk"}],
                },
                "reasoning": "Top picks.",
            }, ensure_ascii=False),
            "plan validator": json.dumps({
                "valid": True, "issues": [], "suggestions": [], "overall_score": 88,
            }),
        })

        result = pipeline.build("下午想和老婆孩子出去玩，孩子5岁")

        self.assertIn(result.status, {"pending_confirmation", "recovering"})
        self.assertGreaterEqual(len(result.trace), 5)

    def test_recovery_loop_max_iterations(self):
        """Recovery should stop after max attempts even if LLM keeps failing."""
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://example.test/v1",
                api_key="secret",
                model="test",
                remote_enabled=True,
            )
        )

        always_fail = ChainedLLM({
            "planning ranker": json.dumps({
                "ranked": {
                    "activities": [{"id": "act_kid_science_001", "reason": "ok"}],
                    "restaurants": [],
                    "walks": [],
                },
                "reasoning": "only activity",
            }, ensure_ascii=False),
            "plan validator": json.dumps({
                "valid": False,
                "issues": [{"code": "test_failure", "detail": "always fails", "severity": "blocking"}],
                "suggestions": [],
                "overall_score": 20,
            }),
            "recovery": json.dumps({
                "action": "replan",
                "reason": "needs full replan",
            }),
        })
        pipeline.llm = always_fail

        result = pipeline.build("下午朋友出去玩")

        # Should stop after max recovery attempts
        self.assertLessEqual(result.recovery_attempts, 3)
        self.assertIn(result.status, {"pending_confirmation", "recovering"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_graph_topology.py::GraphTopologyTest::test_pipeline_graph_has_parallel_search_nodes -xvs`
Expected: FAIL — current graph doesn't have `search_activities`, `search_restaurants`, `search_walks` as separate nodes

- [ ] **Step 3: Refactor pipeline.py — new graph topology**

This is the main refactor. Replace the `_compile_graph` method and add new node methods. The key changes:

1. Add `from backend.agents.ranker import RankerAgent`, `from backend.agents.validator import ValidatorAgent`, `from backend.agents.recovery import RecoveryAgent`
2. Add `from backend.orchestrator.search import search_activities, search_restaurants, search_walks`
3. Add `from backend.orchestrator.nodes import build_context_node, merge_search_results_node`
4. Replace `_compile_graph` with new graph that has parallel search, agent nodes, and conditional routing
5. Add `_ranker_agent_node`, `_validator_agent_node`, `_recovery_node` methods
6. Modify `_build_itinerary_node` to work with LLM-ranked candidates
7. Modify `_prepare_confirmation_node` to be simpler (no changes needed)
8. Add `_after_validate` conditional routing function

The new `_compile_graph`:

```python
def _compile_graph(self):
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(BuildGraphState)

    # Existing nodes
    graph.add_node("parse_intent", self._parse_intent_node)
    graph.add_node("build_context", self._build_context_node)

    # Parallel search nodes
    graph.add_node("search_activities", self._search_activities_node)
    graph.add_node("search_restaurants", self._search_restaurants_node)
    graph.add_node("search_walks", self._search_walks_node)
    graph.add_node("merge_search_results", self._merge_search_results_node)

    # Agent nodes
    graph.add_node("ranker_agent", self._ranker_agent_node)
    graph.add_node("build_itinerary", self._build_itinerary_node)
    graph.add_node("validator_agent", self._validator_agent_node)
    graph.add_node("prepare_confirmation", self._prepare_confirmation_node)
    graph.add_node("recovery", self._recovery_node)

    # Edges
    graph.add_edge(START, "parse_intent")
    graph.add_conditional_edges("parse_intent", should_continue_after_parse, {"continue": "build_context", "clarify": END})
    graph.add_edge("build_context", "search_activities")
    graph.add_edge("build_context", "search_restaurants")
    graph.add_edge("build_context", "search_walks")
    graph.add_edge("search_activities", "merge_search_results")
    graph.add_edge("search_restaurants", "merge_search_results")
    graph.add_edge("search_walks", "merge_search_results")
    graph.add_edge("merge_search_results", "ranker_agent")
    graph.add_edge("ranker_agent", "build_itinerary")
    graph.add_edge("build_itinerary", "validator_agent")
    graph.add_conditional_edges("validator_agent", self._after_validate, {
        "confirm": "prepare_confirmation",
        "recover": "recovery",
    })
    graph.add_edge("recovery", "ranker_agent")  # Loop back
    graph.add_edge("prepare_confirmation", END)

    return graph.compile()
```

New node methods to add to `PlanningPipeline`:

```python
def _search_activities_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    state = graph_state["state"]
    constraints = require_constraints(state)
    items = search_activities(self.catalog, constraints)
    return {"activity_candidates": items}

def _search_restaurants_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    state = graph_state["state"]
    constraints = require_constraints(state)
    items = search_restaurants(self.catalog, constraints)
    return {"restaurant_candidates": items}

def _search_walks_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    state = graph_state["state"]
    constraints = require_constraints(state)
    items = search_walks(self.catalog, constraints)
    return {"walk_candidates": items}

def _merge_search_results_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    state = graph_state["state"]
    return {
        "state": merge_search_results_node(
            state,
            graph_state.get("activity_candidates", []),
            graph_state.get("restaurant_candidates", []),
            graph_state.get("walk_candidates", []),
        )
    }

def _ranker_agent_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    state = graph_state["state"]
    constraints = require_constraints(state)
    agent = RankerAgent(self.llm)
    ranked = agent.rank(state.candidates, constraints)
    state.ranked = ranked
    state.agent_decisions["ranker"] = {"reasoning": agent.last_reasoning}
    state.add_trace(agent.build_trace("ok", "LLM 驱动的多目标候选排序。", {"candidates": {k: len(v) for k, v in state.candidates.items()}}, {"ranked": {k: len(v) for k, v in ranked.items()}, "reasoning": agent.last_reasoning}))
    emit_progress(graph_state, "LLM 多目标排序", "LLM 驱动的多目标候选排序。")
    return {"state": state}

def _validator_agent_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    state = graph_state["state"]
    constraints = require_constraints(state)
    agent = ValidatorAgent(self.llm)
    constraints_data = {
        "scenario": constraints.scenario,
        "budget_level": constraints.preferences.get("budget_level", "medium"),
        "duration_hours": constraints.time_window.get("duration_hours", 4.5),
        "time_window": constraints.time_window,
        "people": constraints.people,
        "preferences": constraints.preferences,
        "constraints": constraints.constraints,
    }
    weather = state.context.get("weather", {})
    lookup = {item["id"]: item for group in state.ranked.values() for item in group}
    validation = agent.validate(state.itinerary, constraints_data, weather, lookup, state.route)
    state.validation_issues = validation.get("issues", [])
    state.status = "pending_confirmation" if validation.get("valid", True) else "recovering"
    state.agent_decisions["validator"] = {"score": validation.get("overall_score", 85), "issues": validation.get("issues", [])}
    state.add_trace(agent.build_trace("ok" if validation.get("valid", True) else "warning", "LLM 驱动的方案整体评估。", {"itinerary_steps": len(state.itinerary)}, validation))
    emit_progress(graph_state, "LLM 方案评估", "LLM 驱动的方案整体评估。")
    return {"state": state, "validation": validation}

def _after_validate(self, graph_state: BuildGraphState) -> str:
    state = graph_state["state"]
    validation = graph_state.get("validation", {})
    if validation.get("valid", True) and state.pending_actions:
        return "confirm"
    if state.recovery_attempts >= 3:
        return "confirm"
    return "recover"

def _recovery_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    state = graph_state["state"]
    state.recovery_attempts += 1
    issues = state.validation_issues
    itinerary_summary = [{"type": step.type, "place_id": step.place_id, "title": step.title} for step in state.itinerary]
    alternatives = {k: v for k, v in state.ranked.items()}
    agent = RecoveryAgent(self.llm)
    decision = agent.recover(issues, itinerary_summary, alternatives)
    state.agent_decisions["recovery"] = decision
    # Apply recovery decision
    if decision.get("action") == "replace":
        _apply_replacement(state, decision)
    state.status = "recovering"
    state.add_trace(agent.build_trace("ok", f"恢复尝试 #{state.recovery_attempts}。", {"issues": issues}, decision))
    emit_progress(graph_state, f"异常恢复 #{state.recovery_attempts}", decision.get("reason", ""))
    return {"state": state}
```

- [ ] **Step 4: Run the new topology tests**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_graph_topology.py -xvs`
Expected: PASS

- [ ] **Step 5: Run existing pipeline tests — fix any breakage**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_pipeline.py -xvs`
Expected: Some tests may fail because they use `FakeLLMClient` that doesn't handle the new multi-prompt routing. Fix by updating test LLM clients to handle ranker/validator/recovery prompts.

- [ ] **Step 6: Run full test suite**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/ -x -q`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/orchestrator/pipeline.py tests/backend/test_graph_topology.py tests/backend/test_pipeline.py
git commit -m "feat: refactor pipeline to multi-agent graph with parallel search, LLM agents, and recovery loop"
```

---

## Task 8: Update API tests and integration tests

**Files:**
- Modify: `tests/backend/test_api.py`
- Modify: `tests/backend/test_complete_product_backend.py`
- Modify: `tests/backend/test_graph_run_api.py`

- [ ] **Step 1: Update test helper to handle multi-agent LLM routing**

The `RuleBasedLLMClient` in `tests/backend/helpers.py` needs to return valid JSON for ranker, validator, and recovery prompts too. Update it to detect the prompt type and return appropriate responses:

```python
class RuleBasedLLMClient:
    def __init__(self):
        self.calls = []

    def chat_stream(self, messages):
        self.calls.append(messages)
        system = messages[0]["content"] if messages else ""
        goal = messages[-1]["content"] if len(messages) > 1 else ""

        # Ranker agent prompt
        if "planning ranker" in system.lower() or "local-life planning ranker" in system.lower():
            yield json.dumps({
                "ranked": {
                    "activities": [{"id": "act_kid_science_001", "reason": "Good match"}],
                    "restaurants": [{"id": "rest_healthy_001", "reason": "Healthy"}],
                    "walks": [{"id": "walk_river_001", "reason": "Nice"}],
                },
                "reasoning": "Best combo.",
            }, ensure_ascii=False)
            return

        # Validator agent prompt
        if "plan validator" in system.lower():
            yield json.dumps({"valid": True, "issues": [], "suggestions": [], "overall_score": 88})
            return

        # Recovery agent prompt
        if "recovery agent" in system.lower():
            yield json.dumps({"action": "adjust", "reason": "Minor fix"})
            return

        # Default: intent parsing
        constraints = deterministic_constraints(goal)
        normalized = goal.lower()
        if "friends" in normalized:
            constraints.scenario = "friends"
            constraints.people = {"adults": 4, "children": [], "relationship": "friends"}
            constraints.preferences["activity"] = ["social", "photo", "indoor"]
        elif "date" in normalized:
            constraints.scenario = "date"
            constraints.people = {"adults": 2, "children": [], "relationship": "date"}
            constraints.preferences["activity"] = ["quiet", "romantic"]
        elif "rain" in normalized or "indoor" in normalized:
            constraints.scenario = "rainy_indoor"
            constraints.preferences["activity"] = ["indoor", "rain_safe"]
        elif "child" in normalized or "family" in normalized:
            constraints.scenario = "family"
            constraints.people = {"adults": 2, "children": [{"age": 5}], "relationship": "family"}
            constraints.preferences["activity"] = ["child_friendly", "not_too_tiring"]
        yield json.dumps(to_dict(constraints), ensure_ascii=False)
```

- [ ] **Step 2: Run API tests**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_api.py -xvs`
Expected: PASS

- [ ] **Step 3: Run graph run API tests**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_graph_run_api.py -xvs`
Expected: PASS

- [ ] **Step 4: Run complete product backend tests**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/test_complete_product_backend.py -xvs`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add tests/backend/helpers.py tests/backend/test_api.py tests/backend/test_graph_run_api.py tests/backend/test_complete_product_backend.py
git commit -m "test: update test helpers and API tests for multi-agent pipeline"
```

---

## Task 9: Update progress labels in schemas.py for new agent names

**Files:**
- Modify: `backend/models/schemas.py:515-534`

- [ ] **Step 1: Update progress_from_trace labels**

The `progress_from_trace` function maps agent names to display labels. Add entries for the new agent names:

```python
def progress_from_trace(trace: list[TraceStep]) -> list[dict[str, str]]:
    labels = {
        "IntentParserAgent": "理解出行需求",
        "ContextBuilderAgent": "补全场景上下文",
        "CandidateSearchAgent": "筛选本地供给",
        "RankerAgent": "LLM 多目标排序",
        "RouteSchedulerAgent": "生成时间轴和路线",
        "PlanValidatorAgent": "校验可订性和约束",
        "ValidatorAgent": "LLM 方案评估",
        "ConfirmationAgent": "等待用户确认",
        "ExecutionAgent": "执行已确认动作",
        "RecoveryAgent": "LLM 异常恢复",
    }
    return [
        {
            "label": labels.get(step.agent, step.agent),
            "detail": step.message,
            "status": "done" if step.status == "ok" else step.status,
        }
        for step in trace
    ]
```

- [ ] **Step 2: Run full test suite**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/ -x -q`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/models/schemas.py
git commit -m "feat: add progress labels for new agent names"
```

---

## Task 10: Final integration verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run pytest tests/backend/ -v`
Expected: All tests pass, including new topology tests

- [ ] **Step 2: Start backend server and verify health**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run python -c "from backend.api.app import app; print('App created:', app.title)"`
Expected: `App created: WeekendPilot Backend`

- [ ] **Step 3: Verify graph structure visually**

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && uv run python -c "
from backend.orchestrator.pipeline import PlanningPipeline
from backend.llm.config import LLMConfig
p = PlanningPipeline(llm_config=LLMConfig(api_key='test', base_url='http://x', model='test', remote_enabled=True))
nodes = set(p.graph.get_graph().nodes)
print('Nodes:', sorted(nodes))
edges = list(p.graph.get_graph().edges)
print('Edges:', len(edges))
print('Has parallel search:', all(n in nodes for n in ['search_activities', 'search_restaurants', 'search_walks']))
print('Has agent nodes:', all(n in nodes for n in ['ranker_agent', 'validator_agent', 'recovery']))
print('Has merge:', 'merge_search_results' in nodes)
"`
Expected: Shows all new nodes present

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final integration verification for multi-agent graph refactor"
```
