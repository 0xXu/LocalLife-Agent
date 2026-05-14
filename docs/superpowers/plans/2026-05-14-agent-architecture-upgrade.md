# Agent Architecture Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade RankerAgent, ValidatorAgent, RecoveryAgent from single LLM-call functions to true ReAct agents with tool calling, memory, and autonomous reasoning.

**Architecture:** Each agent becomes a LangGraph `create_react_agent` subgraph with per-agent toolsets. Tools are `@tool`-decorated functions wrapping `LocalToolRegistry` methods, created via factory pattern. Memory: short-term (messages + working_memory) + long-term (BaseStore with namespace-separated keys). Pipeline integration via adapter nodes that convert between pipeline state and agent subgraph messages.

**Tech Stack:** Python 3.14, LangGraph >= 1.1.10, langchain-openai, Pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-05-14-agent-architecture-upgrade-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/llm/chat_model.py` | Create | ChatOpenAI factory from LLMConfig |
| `backend/agents/tools.py` | Create | Pydantic input schemas + tool factory functions |
| `backend/agents/memory.py` | Create | MemoryItem schema, store helpers, selective retrieval |
| `backend/agents/base.py` | Modify | Add `build_react_agent` factory |
| `backend/agents/ranker.py` | Modify | ReAct subgraph with ranker tools |
| `backend/agents/validator.py` | Modify | ReAct subgraph with validator tools |
| `backend/agents/recovery.py` | Modify | ReAct subgraph with recovery tools |
| `backend/agents/__init__.py` | Modify | Update exports |
| `backend/tools/registry.py` | Modify | Add missing tool methods |
| `backend/orchestrator/pipeline.py` | Modify | Adapter nodes, checkpointer, progress events |
| `tests/backend/test_react_agents.py` | Create | ReAct loop, tool calling, memory tests |

---

### Task 1: Add langchain-openai dependency and ChatOpenAI factory

**Files:**
- Modify: `pyproject.toml`
- Create: `backend/llm/chat_model.py`
- Test: inline verification

- [ ] **Step 1: Add langchain-openai dependency**

Add to `pyproject.toml` dependencies:
```
"langchain-openai>=0.3.0",
```

Run: `cd "/Users/huangxu/Desktop/LocalLife Agent" && .venv/bin/uv sync`
Expected: Successfully installs langchain-openai

- [ ] **Step 2: Create ChatOpenAI factory**

Create `backend/llm/chat_model.py`:

```python
from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from backend.llm.config import LLMConfig


def build_chat_model(config: LLMConfig, temperature: float = 0.3) -> ChatOpenAI:
    """Build a LangChain ChatOpenAI from our LLMConfig.

    Uses OpenAI-compatible endpoint. Supports native function calling.
    """
    if not config.is_configured or not config.remote_enabled:
        raise RuntimeError("LLM is not configured or remote is disabled.")
    return ChatOpenAI(
        base_url=config.base_url.rstrip("/") + "/chat/completions".replace("/chat/completions", ""),
        api_key=config.api_key,
        model=config.model,
        temperature=temperature,
        max_tokens=config.max_tokens,
        timeout=config.timeout_seconds,
        streaming=True,
    )
```

Note: `ChatOpenAI` uses `base_url` without the `/chat/completions` suffix — it appends that automatically. Our `LLMConfig.base_url` already includes `/v1`, so we just need to strip the trailing path if present.

Actually, let me be more careful. Check what the current `base_url` looks like:

- [ ] **Step 3: Verify ChatOpenAI works with the endpoint**

Run: `.venv/bin/python -c "
from backend.llm.chat_model import build_chat_model
from backend.llm.config import LLMConfig
config = LLMConfig(base_url='https://token-plan-sgp.xiaomimimo.com/v1', api_key='test', model='mimo-v2.5-pro', remote_enabled=True)
model = build_chat_model(config)
print(f'Model: {model}')
print(f'Base URL: {model.openai_api_base}')
print('ChatOpenAI factory OK')
"`
Expected: Prints model info without error (actual API call would need valid key)

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml backend/llm/chat_model.py
git commit -m "feat(llm): add ChatOpenAI factory for native function calling"
```

---

### Task 2: Add missing tool methods to LocalToolRegistry

**Files:**
- Modify: `backend/tools/registry.py`
- Test: `tests/backend/test_tools.py` (new)

- [ ] **Step 1: Write failing tests for new tool methods**

Create `tests/backend/test_tools.py`:

```python
import unittest
from backend.data.catalog import LocalDataCatalog
from backend.tools.registry import LocalToolRegistry


class TestNewToolMethods(unittest.TestCase):
    def setUp(self):
        self.catalog = LocalDataCatalog()
        self.registry = LocalToolRegistry(self.catalog)

    def test_get_poi_details_returns_full_poi(self):
        poi_id = self.catalog.pois[0]["id"]
        result = self.registry.get_poi_details(poi_id)
        self.assertEqual(result.output["id"], poi_id)
        self.assertIn("open_hours", result.output)
        self.assertIn("risk_tags", result.output)
        self.assertIn("avg_price", result.output)

    def test_get_poi_details_raises_on_missing(self):
        with self.assertRaises(KeyError):
            self.registry.get_poi_details("nonexistent_poi")

    def test_check_weather_returns_weather(self):
        result = self.registry.check_weather("today")
        self.assertIn("condition", result.output)
        self.assertIn("temperature", result.output)

    def test_check_weather_rainy(self):
        result = self.registry.check_weather("rainy")
        self.assertEqual(result.output["condition"], "rain")

    def test_check_opening_hours_returns_status(self):
        poi_id = self.catalog.pois[0]["id"]
        result = self.registry.check_opening_hours(poi_id, "14:00")
        self.assertIn("is_open", result.output)
        self.assertIn("poi_id", result.output)

    def test_search_alternatives_excludes_specified_ids(self):
        all_pois = self.catalog.pois[:5]
        exclude_ids = [all_pois[0]["id"], all_pois[1]["id"]]
        category = all_pois[0]["category"]
        result = self.registry.search_alternatives(category, exclude_ids, 8, [])
        returned_ids = [p["id"] for p in result.output["items"]]
        for eid in exclude_ids:
            self.assertNotIn(eid, returned_ids)

    def test_estimate_cost_sums_avg_prices(self):
        poi = self.catalog.pois[0]
        result = self.registry.estimate_cost(poi["id"], 2)
        self.assertIn("total_cost", result.output)
        self.assertIn("per_person", result.output)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/backend/test_tools.py -v --tb=short`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Implement new methods**

Add to `backend/tools/registry.py`:

```python
def get_poi_details(self, poi_id: str) -> ToolResult:
    """Get full details of a single POI."""
    poi = self.catalog.get_poi(poi_id)
    return ToolResult("get_poi_details", dict(poi))

def check_weather(self, date_key: str = "today") -> ToolResult:
    """Get weather for a date."""
    weather = dict(self.catalog.weather.get(date_key, self.catalog.weather["today"]))
    return ToolResult("check_weather", weather)

def check_opening_hours(self, poi_id: str, time: str) -> ToolResult:
    """Check if a POI is open at a given time."""
    poi = self.catalog.get_poi(poi_id)
    is_open = False
    for hours in poi.get("open_hours", []):
        start = hours.get("start", "00:00")
        end = hours.get("end", "23:59")
        if start <= time <= end:
            is_open = True
            break
    return ToolResult("check_opening_hours", {
        "poi_id": poi_id,
        "time": time,
        "is_open": is_open,
        "open_hours": poi.get("open_hours", []),
    })

def search_alternatives(self, category: str, exclude_ids: list[str], radius_km: float, tags: list[str]) -> ToolResult:
    """Search for alternative POIs, excluding specified IDs."""
    items = self.catalog.search_pois(category, None, radius_km, tags)
    filtered = [item for item in items if item["id"] not in set(exclude_ids)]
    return ToolResult("search_alternatives", {"items": filtered[:8]})

def estimate_cost(self, poi_id: str, party_size: int) -> ToolResult:
    """Estimate total cost for a POI visit."""
    poi = self.catalog.get_poi(poi_id)
    per_person = int(poi.get("avg_price", 100))
    total = per_person * party_size
    return ToolResult("estimate_cost", {
        "poi_id": poi_id,
        "party_size": party_size,
        "per_person": per_person,
        "total_cost": total,
    })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/backend/test_tools.py -v --tb=short`
Expected: All pass

- [ ] **Step 5: Run all existing tests to check for regressions**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All 165+ pass

- [ ] **Step 6: Commit**

```bash
git add backend/tools/registry.py tests/backend/test_tools.py
git commit -m "feat(tools): add get_poi_details, check_weather, check_opening_hours, search_alternatives, estimate_cost"
```

---

### Task 3: Create tool definitions with Pydantic schemas

**Files:**
- Create: `backend/agents/tools.py`
- Test: `tests/backend/test_agent_tools.py` (new)

- [ ] **Step 1: Write failing tests for tool factories**

Create `tests/backend/test_agent_tools.py`:

```python
import unittest
from backend.agents.tools import (
    build_ranker_tools,
    build_validator_tools,
    build_recovery_tools,
    AgentContext,
)
from backend.data.catalog import LocalDataCatalog
from backend.tools.registry import LocalToolRegistry


class TestToolFactories(unittest.TestCase):
    def setUp(self):
        self.catalog = LocalDataCatalog()
        self.registry = LocalToolRegistry(self.catalog)
        self.context = AgentContext(user_id="test_user", locale="zh-CN")

    def test_ranker_tools_count(self):
        tools = build_ranker_tools(self.registry, self.context)
        self.assertEqual(len(tools), 4)
        names = {t.name for t in tools}
        self.assertEqual(names, {"search_places", "get_poi_details", "check_availability", "compare_pois"})

    def test_validator_tools_count(self):
        tools = build_validator_tools(self.registry, self.context)
        self.assertEqual(len(tools), 4)
        names = {t.name for t in tools}
        self.assertEqual(names, {"check_weather", "check_opening_hours", "check_availability", "check_route_time"})

    def test_recovery_tools_count(self):
        tools = build_recovery_tools(self.registry, self.context)
        self.assertEqual(len(tools), 4)
        names = {t.name for t in tools}
        self.assertEqual(names, {"search_alternatives", "check_availability", "compare_options", "estimate_cost"})

    def test_search_places_tool_returns_results(self):
        tools = build_ranker_tools(self.registry, self.context)
        search_fn = next(t for t in tools if t.name == "search_places")
        result = search_fn.invoke({"scenario": "family", "radius_km": 8, "tags": ["child_friendly"]})
        self.assertIn("items", result)
        self.assertIsInstance(result["items"], list)

    def test_get_poi_details_tool_returns_details(self):
        tools = build_ranker_tools(self.registry, self.context)
        details_fn = next(t for t in tools if t.name == "get_poi_details")
        poi_id = self.catalog.pois[0]["id"]
        result = details_fn.invoke({"poi_id": poi_id})
        self.assertEqual(result["id"], poi_id)

    def test_check_weather_tool_returns_weather(self):
        tools = build_validator_tools(self.registry, self.context)
        weather_fn = next(t for t in tools if t.name == "check_weather")
        result = weather_fn.invoke({"date_key": "today"})
        self.assertIn("condition", result)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/backend/test_agent_tools.py -v --tb=short`
Expected: FAIL — module not found

- [ ] **Step 3: Implement tool definitions**

Create `backend/agents/tools.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.tools.registry import LocalToolRegistry


@dataclass
class AgentContext:
    user_id: str
    locale: str = "zh-CN"


# --- Pydantic input schemas ---

class SearchPlacesInput(BaseModel):
    scenario: str = Field(description="Scenario label, e.g. 'family', 'date', 'hiking'")
    radius_km: float = Field(description="Search radius in kilometers", ge=0.5, le=20)
    tags: list[str] = Field(description="Filter tags, e.g. ['child_friendly', 'indoor']")


class GetPoiDetailsInput(BaseModel):
    poi_id: str = Field(description="Unique POI identifier")


class CheckAvailabilityInput(BaseModel):
    poi_id: str = Field(description="POI identifier")
    time: str = Field(description="Desired time, e.g. '14:00'")
    party_size: int = Field(description="Number of people", ge=1, le=20)


class ComparePoisInput(BaseModel):
    poi_ids: list[str] = Field(description="List of POI IDs to compare")
    criteria: list[str] = Field(description="Comparison criteria, e.g. ['price', 'rating', 'distance']")


class CheckWeatherInput(BaseModel):
    date_key: str = Field(description="Date key, e.g. 'today' or 'rainy'", default="today")


class CheckOpeningHoursInput(BaseModel):
    poi_id: str = Field(description="POI identifier")
    time: str = Field(description="Time to check, e.g. '14:00'")


class CheckRouteTimeInput(BaseModel):
    waypoint_ids: list[str] = Field(description="Ordered list of POI IDs as route waypoints")


class SearchAlternativesInput(BaseModel):
    category: str = Field(description="POI category, e.g. 'restaurant', 'social_activity'")
    exclude_ids: list[str] = Field(description="POI IDs to exclude from results")
    radius_km: float = Field(description="Search radius in kilometers", ge=0.5, le=20)
    tags: list[str] = Field(description="Filter tags")


class CompareOptionsInput(BaseModel):
    option_ids: list[str] = Field(description="POI IDs to compare as alternatives")
    original_id: str = Field(description="Original POI ID to compare against")


class EstimateCostInput(BaseModel):
    poi_id: str = Field(description="POI identifier")
    party_size: int = Field(description="Number of people", ge=1, le=20)


# --- Tool factories ---

def build_ranker_tools(registry: LocalToolRegistry, context: AgentContext) -> list:
    """Build read-only tools for RankerAgent."""

    @tool(args_schema=SearchPlacesInput)
    def search_places(scenario: str, radius_km: float, tags: list[str]) -> dict:
        """Search candidate POIs matching the scenario, radius, and tags. Use this to discover options before ranking."""
        result = registry.search_places(scenario, radius_km, tags)
        return {"ok": True, "data": result.output, "source": "local_catalog"}

    @tool(args_schema=GetPoiDetailsInput)
    def get_poi_details(poi_id: str) -> dict:
        """Get detailed information for one POI including opening hours, price, rating, risk tags, and availability."""
        try:
            result = registry.get_poi_details(poi_id)
            return {"ok": True, "data": result.output, "source": "local_catalog"}
        except KeyError:
            return {"ok": False, "error_code": "POI_NOT_FOUND", "message": f"No POI found: {poi_id}"}

    @tool(args_schema=CheckAvailabilityInput)
    def check_availability(poi_id: str, time: str, party_size: int) -> dict:
        """Check whether a POI has enough availability for rough ranking. Use this only for promising candidates."""
        result = registry.check_availability(poi_id, time, party_size)
        return {"ok": True, "data": result.output, "source": "local_catalog"}

    @tool(args_schema=ComparePoisInput)
    def compare_pois(poi_ids: list[str], criteria: list[str]) -> dict:
        """Compare multiple POIs by specified criteria (price, rating, distance, wait_time). Returns side-by-side comparison."""
        details = []
        for pid in poi_ids:
            try:
                poi = registry.get_poi_details(pid).output
                details.append({
                    "id": pid,
                    "name": poi.get("name", ""),
                    "rating": poi.get("rating", 0),
                    "avg_price": poi.get("avg_price", 0),
                    "distance_km": poi.get("distance_km", 0),
                    "wait_minutes": poi.get("wait_minutes", 0),
                    "tags": poi.get("tags", []),
                })
            except KeyError:
                details.append({"id": pid, "error": "not_found"})
        return {"ok": True, "data": {"comparison": details, "criteria": criteria}, "source": "local_catalog"}

    return [search_places, get_poi_details, check_availability, compare_pois]


def build_validator_tools(registry: LocalToolRegistry, context: AgentContext) -> list:
    """Build read-only tools for ValidatorAgent."""

    @tool(args_schema=CheckWeatherInput)
    def check_weather(date_key: str = "today") -> dict:
        """Get weather forecast for a date. Use to verify outdoor activities are weather-safe."""
        result = registry.check_weather(date_key)
        return {"ok": True, "data": result.output, "source": "local_catalog"}

    @tool(args_schema=CheckOpeningHoursInput)
    def check_opening_hours(poi_id: str, time: str) -> dict:
        """Strictly verify whether a POI is open at the exact planned time. Use for final validation."""
        try:
            result = registry.check_opening_hours(poi_id, time)
            return {"ok": True, "data": result.output, "source": "local_catalog"}
        except KeyError:
            return {"ok": False, "error_code": "POI_NOT_FOUND", "message": f"No POI found: {poi_id}"}

    @tool(args_schema=CheckAvailabilityInput)
    def check_availability(poi_id: str, time: str, party_size: int) -> dict:
        """Strictly verify whether the selected POI is available at the exact planned time and party size."""
        result = registry.check_availability(poi_id, time, party_size)
        return {"ok": True, "data": result.output, "source": "local_catalog"}

    @tool(args_schema=CheckRouteTimeInput)
    def check_route_time(waypoint_ids: list[str]) -> dict:
        """Check total route time for a list of waypoint POI IDs. Returns travel time breakdown."""
        waypoints = []
        for pid in waypoint_ids:
            try:
                poi = registry.get_poi_details(pid).output
                waypoints.append(poi)
            except KeyError:
                return {"ok": False, "error_code": "POI_NOT_FOUND", "message": f"No POI found: {pid}"}
        result = registry.optimize_route(waypoints)
        return {"ok": True, "data": result.output, "source": "local_catalog"}

    return [check_weather, check_opening_hours, check_availability, check_route_time]


def build_recovery_tools(registry: LocalToolRegistry, context: AgentContext) -> list:
    """Build read-only tools for RecoveryAgent."""

    @tool(args_schema=SearchAlternativesInput)
    def search_alternatives(category: str, exclude_ids: list[str], radius_km: float, tags: list[str]) -> dict:
        """Search for replacement POIs, excluding the ones already tried. Use when original plan fails."""
        result = registry.search_alternatives(category, exclude_ids, radius_km, tags)
        return {"ok": True, "data": result.output, "source": "local_catalog"}

    @tool(args_schema=CheckAvailabilityInput)
    def check_availability(poi_id: str, time: str, party_size: int) -> dict:
        """Check availability for replacement POIs before proposing them as recovery options."""
        result = registry.check_availability(poi_id, time, party_size)
        return {"ok": True, "data": result.output, "source": "local_catalog"}

    @tool(args_schema=CompareOptionsInput)
    def compare_options(option_ids: list[str], original_id: str) -> dict:
        """Compare alternative POIs against the original. Shows what changed."""
        all_ids = [original_id] + option_ids
        details = []
        for pid in all_ids:
            try:
                poi = registry.get_poi_details(pid).output
                details.append({
                    "id": pid,
                    "name": poi.get("name", ""),
                    "rating": poi.get("rating", 0),
                    "avg_price": poi.get("avg_price", 0),
                    "distance_km": poi.get("distance_km", 0),
                    "is_original": pid == original_id,
                })
            except KeyError:
                details.append({"id": pid, "error": "not_found"})
        return {"ok": True, "data": {"comparison": details}, "source": "local_catalog"}

    @tool(args_schema=EstimateCostInput)
    def estimate_cost(poi_id: str, party_size: int) -> dict:
        """Estimate total cost for a POI visit with given party size."""
        result = registry.estimate_cost(poi_id, party_size)
        return {"ok": True, "data": result.output, "source": "local_catalog"}

    return [search_alternatives, check_availability, compare_options, estimate_cost]
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/backend/test_agent_tools.py -v --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/agents/tools.py tests/backend/test_agent_tools.py
git commit -m "feat(agents): add tool definitions with Pydantic schemas and factory pattern"
```

---

### Task 4: Create memory module

**Files:**
- Create: `backend/agents/memory.py`
- Test: `tests/backend/test_memory.py` (new)

- [ ] **Step 1: Write failing tests**

Create `tests/backend/test_memory.py`:

```python
import unittest
from backend.agents.memory import MemoryItem, MemoryStore


class TestMemoryItem(unittest.TestCase):
    def test_create_preference_item(self):
        item = MemoryItem(
            type="preference",
            content={"diet": "low_fat"},
            source="user_explicit",
            confidence=1.0,
        )
        self.assertEqual(item.type, "preference")
        self.assertEqual(item.source, "user_explicit")
        self.assertEqual(item.confidence, 1.0)

    def test_create_history_item(self):
        item = MemoryItem(
            type="history",
            content={"poi_id": "poi_001", "action": "selected"},
            source="user_behavior",
            confidence=0.8,
        )
        self.assertEqual(item.type, "history")

    def test_default_values(self):
        item = MemoryItem(type="preference", content={}, source="user_explicit", confidence=1.0)
        self.assertIsNone(item.expires_at)


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()

    def test_put_and_get_preference(self):
        self.store.put_preference("user_1", {"diet": "low_fat"})
        pref = self.store.get_preference("user_1")
        self.assertEqual(pref["diet"], "low_fat")

    def test_get_missing_preference_returns_empty(self):
        pref = self.store.get_preference("nonexistent")
        self.assertEqual(pref, {})

    def test_add_history_entry(self):
        self.store.add_history("user_1", {"poi_id": "poi_001", "action": "selected"})
        self.store.add_history("user_1", {"poi_id": "poi_002", "action": "rejected"})
        history = self.store.get_history("user_1", limit=10)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["poi_id"], "poi_001")

    def test_history_limit(self):
        for i in range(5):
            self.store.add_history("user_1", {"idx": i})
        history = self.store.get_history("user_1", limit=3)
        self.assertEqual(len(history), 3)

    def test_add_poi_feedback(self):
        self.store.add_poi_feedback("poi_001", {"rating": 4.5, "comment": "great"})
        feedback = self.store.get_poi_feedback("poi_001")
        self.assertEqual(len(feedback), 1)
        self.assertEqual(feedback[0]["rating"], 4.5)

    def test_build_context_message(self):
        self.store.put_preference("user_1", {"diet": "low_fat", "budget": "medium"})
        self.store.add_history("user_1", {"poi_id": "poi_001", "action": "selected"})
        msg = self.store.build_context_message("user_1")
        self.assertIn("low_fat", msg)
        self.assertIn("poi_001", msg)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/backend/test_memory.py -v --tb=short`
Expected: FAIL — module not found

- [ ] **Step 3: Implement memory module**

Create `backend/agents/memory.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class MemoryItem:
    type: Literal["preference", "history", "poi_feedback"]
    content: dict[str, Any]
    source: Literal["user_explicit", "user_behavior", "agent_inferred", "system_observed"]
    confidence: float = 1.0
    created_at: str = ""
    updated_at: str = ""
    expires_at: str | None = None


class MemoryStore:
    """In-memory store for agent memory. First version — production should use persistent backend."""

    def __init__(self) -> None:
        self._preferences: dict[str, dict[str, Any]] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._poi_feedback: dict[str, list[dict[str, Any]]] = {}

    def put_preference(self, user_id: str, preferences: dict[str, Any]) -> None:
        """Store user preferences (hard memory)."""
        if user_id not in self._preferences:
            self._preferences[user_id] = {}
        self._preferences[user_id].update(preferences)

    def get_preference(self, user_id: str) -> dict[str, Any]:
        """Get user preferences."""
        return dict(self._preferences.get(user_id, {}))

    def add_history(self, user_id: str, entry: dict[str, Any]) -> None:
        """Add a recommendation history entry."""
        if user_id not in self._history:
            self._history[user_id] = []
        self._history[user_id].append(entry)

    def get_history(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent recommendation history."""
        return list(self._history.get(user_id, [])[-limit:])

    def add_poi_feedback(self, poi_id: str, feedback: dict[str, Any]) -> None:
        """Add feedback for a POI."""
        if poi_id not in self._poi_feedback:
            self._poi_feedback[poi_id] = []
        self._poi_feedback[poi_id].append(feedback)

    def get_poi_feedback(self, poi_id: str) -> list[dict[str, Any]]:
        """Get feedback for a POI."""
        return list(self._poi_feedback.get(poi_id, []))

    def build_context_message(self, user_id: str) -> str:
        """Build a context string from user memory for injection into agent prompts."""
        parts = []
        prefs = self.get_preference(user_id)
        if prefs:
            parts.append(f"User preferences: {json.dumps(prefs, ensure_ascii=False)}")
        history = self.get_history(user_id, limit=10)
        if history:
            parts.append(f"Recent choices: {json.dumps(history, ensure_ascii=False)}")
        if not parts:
            return "No prior memory available for this user."
        return "\n".join(parts)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/backend/test_memory.py -v --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/agents/memory.py tests/backend/test_memory.py
git commit -m "feat(agents): add memory module with MemoryItem schema and MemoryStore"
```

---

### Task 5: Add build_react_agent factory to base.py

**Files:**
- Modify: `backend/agents/base.py`

- [ ] **Step 1: Add factory function**

Add to `backend/agents/base.py`:

```python
from typing import Any, Callable


def build_react_agent(llm, tools: list, prompt: str | Callable, checkpointer=None):
    """Build a ReAct agent subgraph. Wraps create_react_agent for future migration."""
    from langgraph.prebuilt import create_react_agent
    return create_react_agent(
        llm,
        tools=tools,
        prompt=prompt,
        checkpointer=checkpointer,
    )
```

- [ ] **Step 2: Run existing tests**

Run: `.venv/bin/python -m pytest tests/backend/test_agents.py -v --tb=short`
Expected: All pass (no existing behavior changed)

- [ ] **Step 3: Commit**

```bash
git add backend/agents/base.py
git commit -m "feat(agents): add build_react_agent factory to base module"
```

---

### Task 6: Convert RankerAgent to ReAct subgraph

**Files:**
- Modify: `backend/agents/ranker.py`
- Test: `tests/backend/test_agents.py` (existing tests should still pass)

- [ ] **Step 1: Rewrite RankerAgent as ReAct subgraph**

Replace `backend/agents/ranker.py`:

```python
from __future__ import annotations

import json
from typing import Any

from backend.agents.base import BaseAgent, build_react_agent, extract_json_object
from backend.agents.tools import AgentContext, build_ranker_tools
from backend.models.schemas import ParsedConstraints
from backend.tools.registry import LocalToolRegistry


RANKER_SYSTEM_PROMPT = """You are RankerAgent — a local-life planning ranker.

Your job: discover and rank candidate POIs for activities, restaurants, and walks.

Rules:
- Use search_places to find candidates if needed
- Use get_poi_details to check promising candidates before ranking
- Use check_availability only for top candidates (not all)
- Use compare_pois when you need to decide between close options
- Do NOT validate full itinerary feasibility — that's ValidatorAgent's job
- Do NOT search for alternatives to failed plans — that's RecoveryAgent's job

Final answer MUST be a JSON object:
{
  "ranked": {
    "activities": [{"id": "poi_xxx", "reason": "..."}],
    "restaurants": [{"id": "poi_yyy", "reason": "..."}],
    "walks": [{"id": "poi_zzz", "reason": "..."}]
  },
  "reasoning": "..."
}
Select 1-3 items per category. Prefer items matching user tags, closer distance, lower wait time."""


class RankerAgent(BaseAgent):
    def __init__(self, llm: Any, registry: LocalToolRegistry | None = None, memory_store=None) -> None:
        super().__init__("RankerAgent", llm)
        self.registry = registry
        self.memory_store = memory_store
        self.last_reasoning: str = ""
        self._react_graph = None

    def _ensure_graph(self, context: AgentContext):
        if self._react_graph is None:
            tools = build_ranker_tools(self.registry, context)
            self._react_graph = build_react_agent(self.llm, tools=tools, prompt=RANKER_SYSTEM_PROMPT)
        return self._react_graph

    def rank(self, candidates: dict[str, list[dict]], constraints: ParsedConstraints, context: AgentContext | None = None) -> dict[str, list[dict]]:
        context = context or AgentContext(user_id="default")
        graph = self._ensure_graph(context)

        # Build task message with candidates and constraints
        memory_context = ""
        if self.memory_store:
            memory_context = f"\n\nUser memory:\n{self.memory_store.build_context_message(context.user_id)}"

        task_message = (
            f"Rank these candidates for the user.\n\n"
            f"Scenario: {constraints.scenario}\n"
            f"Activity tags: {constraints.preferences.get('activity', [])}\n"
            f"Diet tags: {constraints.preferences.get('diet', [])}\n"
            f"Budget: {constraints.preferences.get('budget_level', 'medium')}\n"
            f"Radius: {constraints.constraints.get('radius_km', 8)}km\n"
            f"People: {constraints.people}\n\n"
            f"Candidates:\n{json.dumps({k: [{'id': i['id'], 'name': i['name'], 'rating': i.get('rating',0), 'tags': i.get('tags',[]), 'distance_km': i.get('distance_km',0)} for i in v[:8]] for k, v in candidates.items()}, ensure_ascii=False)}"
            f"{memory_context}"
        )

        try:
            result = graph.invoke({"messages": [{"role": "user", "content": task_message}]})
            final_message = result["messages"][-1].content
            parsed = json.loads(extract_json_object(final_message))
            self.last_reasoning = parsed.get("reasoning", "")
            return _merge_ranked_with_candidates(parsed.get("ranked", {}), candidates)
        except Exception:
            self.last_reasoning = "ReAct agent failed, using deterministic fallback."
            return _deterministic_fallback(candidates)

    # Keep old interface for backward compatibility
    def rank_legacy(self, candidates, constraints):
        return self.rank(candidates, constraints)


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
            full = candidate_lookup.get(sid, None)
            if full is not None:
                enriched = dict(full)
                enriched["llm_reason"] = sel.get("reason", "")
                merged.append(enriched)
        if not merged:
            fallback_items = candidates.get(category, [])
            sorted_fallback = sorted(
                fallback_items,
                key=lambda x: (-float(x.get("rating", 0)), float(x.get("distance_km", 99))),
            )
            merged = sorted_fallback[:3]
        result[category] = merged
    return result


def _deterministic_fallback(candidates: dict[str, list[dict]]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for category, items in candidates.items():
        sorted_items = sorted(items, key=lambda x: (-float(x.get("rating", 0)), float(x.get("distance_km", 99))))
        result[category] = sorted_items[:3]
    return result
```

- [ ] **Step 2: Run existing agent tests**

Run: `.venv/bin/python -m pytest tests/backend/test_agents.py -v --tb=short`
Expected: All pass (existing tests use fake LLM, should still work)

- [ ] **Step 3: Run all tests**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/agents/ranker.py
git commit -m "feat(ranker): convert to ReAct subgraph with tool calling"
```

---

### Task 7: Convert ValidatorAgent to ReAct subgraph

**Files:**
- Modify: `backend/agents/validator.py`

- [ ] **Step 1: Rewrite ValidatorAgent**

Replace `backend/agents/validator.py`:

```python
from __future__ import annotations

import json
from typing import Any

from backend.agents.base import BaseAgent, build_react_agent, extract_json_object
from backend.agents.tools import AgentContext, build_validator_tools
from backend.models.schemas import ItineraryStep, ParsedConstraints, to_dict
from backend.tools.registry import LocalToolRegistry
from backend.validation.rules import validate_itinerary


VALIDATOR_SYSTEM_PROMPT = """You are ValidatorAgent — a plan validator for a local-life planner.

Your job: verify the feasibility of an existing itinerary.

Rules:
- Use check_weather to verify outdoor activities are weather-safe
- Use check_opening_hours to verify each POI is open at its planned time
- Use check_availability to verify reservations are possible
- Use check_route_time to verify the route is efficient
- Do NOT search for alternatives — that's RecoveryAgent's job
- Do NOT re-rank candidates — that's RankerAgent's job

Final answer MUST be a JSON object:
{
  "valid": true/false,
  "issues": [{"code": "...", "detail": "...", "severity": "blocking|warning"}],
  "suggestions": ["..."],
  "overall_score": 0-100
}"""


class ValidatorAgent(BaseAgent):
    def __init__(self, llm: Any, registry: LocalToolRegistry | None = None) -> None:
        super().__init__("ValidatorAgent", llm)
        self.registry = registry
        self._react_graph = None

    def _ensure_graph(self, context: AgentContext):
        if self._react_graph is None:
            tools = build_validator_tools(self.registry, context)
            self._react_graph = build_react_agent(self.llm, tools=tools, prompt=VALIDATOR_SYSTEM_PROMPT)
        return self._react_graph

    def validate(
        self,
        itinerary: list[ItineraryStep],
        constraints_data: dict[str, Any],
        weather: dict[str, Any],
        candidate_lookup: dict[str, dict] | None = None,
        route: dict[str, Any] | None = None,
        context: AgentContext | None = None,
    ) -> dict[str, Any]:
        context = context or AgentContext(user_id="default")
        graph = self._ensure_graph(context)

        task_message = (
            f"Validate this itinerary.\n\n"
            f"Itinerary:\n{json.dumps([to_dict(step) for step in itinerary], ensure_ascii=False)}\n\n"
            f"Constraints:\n{json.dumps(constraints_data, ensure_ascii=False)}\n\n"
            f"Weather:\n{json.dumps(weather, ensure_ascii=False)}\n\n"
            f"Route:\n{json.dumps(route or {}, ensure_ascii=False)}"
        )

        try:
            result = graph.invoke({"messages": [{"role": "user", "content": task_message}]})
            final_message = result["messages"][-1].content
            parsed = json.loads(extract_json_object(final_message))
            return parsed
        except Exception:
            # Fallback to rule-based validation
            return self._rule_based_fallback(itinerary, constraints_data, weather, candidate_lookup, route)

    def _rule_based_fallback(
        self,
        itinerary: list[ItineraryStep],
        constraints_data: dict[str, Any],
        weather: dict[str, Any],
        candidate_lookup: dict[str, dict] | None,
        route: dict[str, Any] | None,
    ) -> dict[str, Any]:
        constraints = ParsedConstraints(
            scenario=constraints_data.get("scenario", "family"),
            origin=constraints_data.get("origin", {}),
            time_window=constraints_data.get("time_window", {}),
            people=constraints_data.get("people", {}),
            preferences={"budget_level": constraints_data.get("budget_level", "medium")},
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

- [ ] **Step 2: Run all tests**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/agents/validator.py
git commit -m "feat(validator): convert to ReAct subgraph with tool calling"
```

---

### Task 8: Convert RecoveryAgent to ReAct subgraph

**Files:**
- Modify: `backend/agents/recovery.py`

- [ ] **Step 1: Rewrite RecoveryAgent**

Replace `backend/agents/recovery.py`:

```python
from __future__ import annotations

import json
from typing import Any

from backend.agents.base import BaseAgent, build_react_agent, extract_json_object
from backend.agents.tools import AgentContext, build_recovery_tools
from backend.tools.registry import LocalToolRegistry


RECOVERY_SYSTEM_PROMPT = """You are RecoveryAgent — a plan recovery specialist.

Your job: find substitutes when the original plan fails validation.

Rules:
- Use search_alternatives to find replacement POIs (excluding the failed ones)
- Use check_availability to verify replacements are actually available
- Use compare_options to compare replacements against the original
- Use estimate_cost to check budget impact of replacements
- Do NOT re-rank the entire candidate pool — that's RankerAgent's job
- Do NOT validate the full plan — that's ValidatorAgent's job

Final answer MUST be a JSON object:
{
  "action": "replace|adjust|replan",
  "target_type": "activity|restaurant|walk",
  "target_id": "original_poi_id",
  "replacement_id": "new_poi_id",
  "adjustment": "description of adjustment",
  "reason": "why this recovery action"
}"""


class RecoveryAgent(BaseAgent):
    def __init__(self, llm: Any, registry: LocalToolRegistry | None = None) -> None:
        super().__init__("RecoveryAgent", llm)
        self.registry = registry
        self._react_graph = None

    def _ensure_graph(self, context: AgentContext):
        if self._react_graph is None:
            tools = build_recovery_tools(self.registry, context)
            self._react_graph = build_react_agent(self.llm, tools=tools, prompt=RECOVERY_SYSTEM_PROMPT)
        return self._react_graph

    def recover(
        self,
        issues: list[dict[str, Any]],
        itinerary_summary: list[dict[str, Any]],
        alternatives: dict[str, list[dict[str, Any]]],
        context: AgentContext | None = None,
    ) -> dict[str, Any]:
        context = context or AgentContext(user_id="default")
        graph = self._ensure_graph(context)

        task_message = (
            f"The validator found issues with this itinerary. Find a recovery plan.\n\n"
            f"Issues:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
            f"Current itinerary:\n{json.dumps(itinerary_summary, ensure_ascii=False)}\n\n"
            f"Available alternatives:\n{json.dumps({k: [{'id': i['id'], 'name': i.get('name','')} for i in v] for k, v in alternatives.items()}, ensure_ascii=False)}"
        )

        try:
            result = graph.invoke({"messages": [{"role": "user", "content": task_message}]})
            final_message = result["messages"][-1].content
            parsed = json.loads(extract_json_object(final_message))
            return parsed
        except Exception:
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

- [ ] **Step 2: Run all tests**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/agents/recovery.py
git commit -m "feat(recovery): convert to ReAct subgraph with tool calling"
```

---

### Task 9: Update agents __init__.py exports

**Files:**
- Modify: `backend/agents/__init__.py`

- [ ] **Step 1: Update exports**

Replace `backend/agents/__init__.py`:

```python
from .base import BaseAgent, build_react_agent
from .memory import MemoryItem, MemoryStore
from .ranker import RankerAgent
from .recovery import RecoveryAgent
from .tools import AgentContext, build_ranker_tools, build_recovery_tools, build_validator_tools
from .validator import ValidatorAgent

__all__ = [
    "AgentContext",
    "BaseAgent",
    "MemoryItem",
    "MemoryStore",
    "RankerAgent",
    "RecoveryAgent",
    "ValidatorAgent",
    "build_ranker_tools",
    "build_react_agent",
    "build_recovery_tools",
    "build_validator_tools",
]
```

- [ ] **Step 2: Run all tests**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/agents/__init__.py
git commit -m "feat(agents): update exports for new modules"
```

---

### Task 10: Update pipeline agent nodes with adapters

**Files:**
- Modify: `backend/orchestrator/pipeline.py`

- [ ] **Step 1: Update RankerAgent instantiation in pipeline**

In `backend/orchestrator/pipeline.py`, find `_ranker_agent_node` and update:

```python
def _ranker_agent_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    from backend.agents.tools import AgentContext

    state = graph_state["state"]
    constraints = require_constraints(state)
    context = AgentContext(user_id=state.context.get("user_id", "default"))

    agent = RankerAgent(self.llm, registry=self.tools, memory_store=getattr(self, 'memory_store', None))
    ranked = agent.rank(state.candidates, constraints, context=context)

    if "deterministic" in agent.last_reasoning.lower() or "fallback" in agent.last_reasoning.lower():
        preferred_tags = list(constraints.preferences.get("activity", [])) + list(constraints.preferences.get("diet", []))
        candidate_sets: dict[str, list[dict[str, Any]]] = {}
        rejected: dict[str, list[dict[str, Any]]] = {}
        for key, items in state.candidates.items():
            grounded = [ground_place(item, confidence_for_tags(item, preferred_tags)) for item in items]
            result = rank_candidates(grounded, constraints)
            ranked[key] = [candidate.place.as_poi_dict() for candidate in result.items]
            candidate_sets[key] = [
                {
                    "place": candidate.place.as_poi_dict(),
                    "total_score": candidate.total_score,
                    "score_breakdown": candidate.breakdown,
                    "explanation": candidate.explanation,
                }
                for candidate in result.items
            ]
            rejected[key] = result.rejected
        state.candidate_sets = candidate_sets
        state.rejected_candidates = rejected

    state.ranked = ranked
    state.status = "ranked"
    state.agent_decisions["ranker"] = {"reasoning": agent.last_reasoning}
    state.add_trace(agent.build_trace(
        "ok", "LLM 驱动的多目标候选排序。",
        {"candidates": {k: len(v) for k, v in state.candidates.items()}},
        {"ranked": {k: len(v) for k, v in ranked.items()}, "reasoning": agent.last_reasoning},
    ))
    emit_progress(graph_state, "LLM 多目标排序", "LLM 驱动的多目标候选排序。")
    return {"state": state}
```

- [ ] **Step 2: Update ValidatorAgent instantiation**

Find `_validator_agent_node` and update similarly — pass `registry=self.tools` and `context`.

- [ ] **Step 3: Update RecoveryAgent instantiation**

Find `_recovery_node` and update similarly — pass `registry=self.tools` and `context`.

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/pipeline.py
git commit -m "feat(pipeline): update agent nodes to use ReAct subgraphs with adapters"
```

---

### Task 11: Add ReAct agent tests

**Files:**
- Create: `tests/backend/test_react_agents.py`

- [ ] **Step 1: Write comprehensive ReAct tests**

Create `tests/backend/test_react_agents.py`:

```python
import json
import unittest

from backend.agents.memory import MemoryItem, MemoryStore
from backend.agents.ranker import RankerAgent, RANKER_SYSTEM_PROMPT
from backend.agents.recovery import RecoveryAgent, RECOVERY_SYSTEM_PROMPT
from backend.agents.tools import AgentContext, build_ranker_tools, build_recovery_tools, build_validator_tools
from backend.agents.validator import ValidatorAgent, VALIDATOR_SYSTEM_PROMPT
from backend.data.catalog import LocalDataCatalog
from backend.tools.registry import LocalToolRegistry


class FakeLLMForReact:
    """Fake LLM that returns tool_calls or final answers based on message count."""
    def __init__(self, final_answer):
        self.final_answer = final_answer
        self.call_count = 0
        self.tool_calls_made = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, **kwargs):
        self.call_count += 1
        # First call: make a tool call
        if self.call_count == 1:
            class FakeMessage:
                def __init__(self):
                    self.content = ""
                    self.tool_calls = [{"id": "call_1", "name": "search_places", "args": {"scenario": "family", "radius_km": 8, "tags": ["child_friendly"]}}]
                    self.type = "ai"
            return FakeMessage()
        # Second call: return final answer
        class FakeFinalMessage:
            def __init__(self, content):
                self.content = content
                self.tool_calls = []
                self.type = "ai"
        return FakeFinalMessage(self.final_answer)


class TestRankerAgentReact(unittest.TestCase):
    def test_ranker_has_system_prompt(self):
        self.assertIn("RankerAgent", RANKER_SYSTEM_PROMPT)
        self.assertIn("search_places", RANKER_SYSTEM_PROMPT)
        self.assertIn("JSON", RANKER_SYSTEM_PROMPT)

    def test_ranker_deterministic_fallback(self):
        catalog = LocalDataCatalog()
        registry = LocalToolRegistry(catalog)
        # Use a failing LLM
        class FailingLLM:
            def bind_tools(self, tools): return self
            def invoke(self, messages, **kwargs): raise RuntimeError("LLM failed")

        agent = RankerAgent(FailingLLM(), registry=registry)
        candidates = {"activities": catalog.pois[:3], "restaurants": [], "walks": []}
        from backend.models.schemas import ParsedConstraints
        constraints = ParsedConstraints(
            scenario="family",
            origin={"type": "current_location", "label": "home", "lat": 39.9, "lng": 116.4},
            time_window={"date": "today", "start": "14:00", "duration_hours": 3, "flexible": True},
            people={"adults": 2, "children": [], "relationship": "family"},
            preferences={"distance": "nearby", "diet": [], "activity": ["child_friendly"], "budget_level": "medium"},
            constraints={"radius_km": 8, "max_wait_minutes": 15, "avoid": []},
            required_actions=["send_plan_message"],
        )
        result = agent.rank(candidates, constraints)
        self.assertIn("activities", result)
        self.assertGreater(len(result["activities"]), 0)
        self.assertIn("fallback", agent.last_reasoning.lower())


class TestValidatorAgentReact(unittest.TestCase):
    def test_validator_has_system_prompt(self):
        self.assertIn("ValidatorAgent", VALIDATOR_SYSTEM_PROMPT)
        self.assertIn("check_weather", VALIDATOR_SYSTEM_PROMPT)

    def test_validator_fallback(self):
        catalog = LocalDataCatalog()
        registry = LocalToolRegistry(catalog)
        class FailingLLM:
            def bind_tools(self, tools): return self
            def invoke(self, messages, **kwargs): raise RuntimeError("LLM failed")

        agent = ValidatorAgent(FailingLLM(), registry=registry)
        from backend.models.schemas import ItineraryStep
        itinerary = [ItineraryStep("14:00", "15:30", "activity", "Test", "poi_001", "reason", "100元", "walk", 85)]
        result = agent.validate(itinerary, {"scenario": "family"}, {})
        self.assertIn("valid", result)


class TestRecoveryAgentReact(unittest.TestCase):
    def test_recovery_has_system_prompt(self):
        self.assertIn("RecoveryAgent", RECOVERY_SYSTEM_PROMPT)
        self.assertIn("search_alternatives", RECOVERY_SYSTEM_PROMPT)

    def test_recovery_fallback(self):
        catalog = LocalDataCatalog()
        registry = LocalToolRegistry(catalog)
        class FailingLLM:
            def bind_tools(self, tools): return self
            def invoke(self, messages, **kwargs): raise RuntimeError("LLM failed")

        agent = RecoveryAgent(FailingLLM(), registry=registry)
        issues = [{"code": "restaurant_closed", "severity": "blocking"}]
        result = agent.recover(issues, [], {"restaurants": catalog.pois[:3]})
        self.assertIn("action", result)


class TestMemoryStore(unittest.TestCase):
    def test_build_context_message(self):
        store = MemoryStore()
        store.put_preference("user_1", {"diet": "low_fat"})
        store.add_history("user_1", {"poi_id": "poi_001", "action": "selected"})
        msg = store.build_context_message("user_1")
        self.assertIn("low_fat", msg)
        self.assertIn("poi_001", msg)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/backend/test_react_agents.py -v --tb=short`
Expected: All pass

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All 180+ pass

- [ ] **Step 4: Commit**

```bash
git add tests/backend/test_react_agents.py
git commit -m "test(agents): add ReAct agent tests with fallback verification"
```
