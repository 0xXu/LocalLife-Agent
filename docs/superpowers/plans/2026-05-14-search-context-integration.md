# Search-Context Integration & Pipeline Refactor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make parallel search use weather/user-preference context, give RankerAgent richer candidate data, and split the 1260-line pipeline.py into focused modules.

**Architecture:** Search functions accept context (weather, preferences) to filter/rank candidates before they reach the ranker. RankerAgent receives full POI data (open_hours, risk_tags, avg_price, wait_minutes, booking_supported) instead of just brief summaries. Pipeline.py is split into: graph orchestration (pipeline.py), node implementations (nodes.py), constraint parsing (constraints.py), itinerary building (itinerary.py).

**Tech Stack:** Python 3.14, LangGraph StateGraph, pytest

---

## File Structure

- `backend/orchestrator/pipeline.py` — Graph compilation, agent node wrappers, build/revise/recover/execute methods (~400 lines after refactor)
- `backend/orchestrator/nodes.py` — Non-agent node functions: build_context, merge_search, search functions with context integration
- `backend/orchestrator/constraints.py` — Constraint parsing, normalization, deterministic fallbacks (extracted from pipeline.py)
- `backend/orchestrator/itinerary.py` — Itinerary building, step generation, route helpers, pending actions (extracted from pipeline.py)
- `backend/agents/ranker.py` — RankerAgent with enriched candidate brief
- `tests/backend/test_search_context.py` — New tests for context-aware search
- `tests/backend/test_pipeline.py` — Existing tests (must still pass)
- `tests/backend/test_api.py` — Existing tests (must still pass)

---

### Task 1: Enrich RankerAgent candidate brief

**Files:**
- Modify: `backend/agents/ranker.py:46-55`
- Test: `tests/backend/test_agents.py`

- [ ] **Step 1: Update `_candidate_brief` to include full context**

```python
def _candidate_brief(item: dict) -> dict:
    return {
        "id": item["id"],
        "name": item["name"],
        "rating": item.get("rating", 0),
        "tags": item.get("tags", []),
        "distance_km": item.get("distance_km", 0),
        "avg_price": item.get("avg_price", 0),
        "wait_minutes": item.get("wait_minutes", 0),
        "open_hours": item.get("open_hours", []),
        "risk_tags": item.get("risk_tags", []),
        "booking_supported": item.get("booking_supported", False),
        "duration_minutes": item.get("duration_minutes", 0),
        "reason": item.get("reason", ""),
        "review_count": item.get("review_count", 0),
        "source": item.get("source", ""),
    }
```

- [ ] **Step 2: Run existing ranker tests**

Run: `.venv/bin/python -m pytest tests/backend/test_agents.py -v --tb=short`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/agents/ranker.py
git commit -m "feat(ranker): enrich candidate brief with open_hours, risk_tags, and full context"
```

---

### Task 2: Integrate weather context into search filtering

**Files:**
- Modify: `backend/orchestrator/search.py`
- Modify: `backend/orchestrator/nodes.py`
- Create: `tests/backend/test_search_context.py`

- [ ] **Step 1: Write failing tests for weather-aware search**

```python
# tests/backend/test_search_context.py
import unittest
from backend.data.catalog import LocalDataCatalog
from backend.models.schemas import ParsedConstraints
from backend.orchestrator.search import search_activities, search_restaurants, search_walks


def _make_constraints(scenario="family", activity_tags=None, diet_tags=None, radius=8):
    return ParsedConstraints(
        scenario=scenario,
        origin={"type": "current_location", "label": "home", "lat": 39.9, "lng": 116.4},
        time_window={"date": "today", "start": "14:00", "duration_hours": 3, "flexible": True},
        people={"adults": 2, "children": [], "relationship": "family"},
        preferences={"distance": "nearby", "diet": diet_tags or [], "activity": activity_tags or ["child_friendly"], "budget_level": "medium"},
        constraints={"radius_km": radius, "max_wait_minutes": 15, "avoid": []},
        required_actions=["send_plan_message"],
    )


class TestWeatherAwareSearch(unittest.TestCase):
    def test_rainy_weather_excludes_outdoor_only_activities(self):
        catalog = LocalDataCatalog()
        constraints = _make_constraints(activity_tags=["outdoor", "hiking"])
        weather = {"condition": "rain", "rain_probability": 0.85}

        results = search_activities(catalog, constraints, weather=weather)

        for poi in results:
            tags = set(poi.get("tags", []))
            # Outdoor-only activities (no indoor tag) should be filtered out in rain
            if "outdoor" in tags and "indoor" not in tags and "rain_safe" not in tags:
                self.fail(f"Outdoor-only POI {poi['name']} should be filtered in rain")

    def test_clear_weather_keeps_outdoor_activities(self):
        catalog = LocalDataCatalog()
        constraints = _make_constraints(activity_tags=["outdoor", "hiking"])
        weather = {"condition": "clear", "rain_probability": 0.05}

        results = search_activities(catalog, constraints, weather=weather)

        # Should still have outdoor results
        has_outdoor = any("outdoor" in poi.get("tags", []) for poi in results)
        self.assertTrue(has_outdoor, "Clear weather should keep outdoor activities")

    def test_no_weather_info_returns_unfiltered(self):
        catalog = LocalDataCatalog()
        constraints = _make_constraints(activity_tags=["child_friendly"])

        results_without = search_activities(catalog, constraints)
        results_with_none = search_activities(catalog, constraints, weather=None)

        self.assertEqual(len(results_without), len(results_with_none))

    def test_search_restaurants_unaffected_by_weather(self):
        catalog = LocalDataCatalog()
        constraints = _make_constraints(diet_tags=["low_fat"])
        rainy_weather = {"condition": "rain", "rain_probability": 0.9}

        results = search_restaurants(catalog, constraints, weather=rainy_weather)

        self.assertGreater(len(results), 0, "Restaurants should not be filtered by weather")


class TestPreferenceWeightedSearch(unittest.TestCase):
    def test_user_preferences_boost_matching_pois(self):
        catalog = LocalDataCatalog()
        constraints = _make_constraints(activity_tags=["child_friendly"])
        preferences = {"activity": ["child_friendly", "indoor"], "diet": []}

        results = search_activities(catalog, constraints, user_preferences=preferences)

        # First result should have child_friendly tag
        if results:
            first_tags = set(results[0].get("tags", []))
            self.assertIn("child_friendly", first_tags, "Top result should match user preference")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/backend/test_search_context.py -v --tb=short`
Expected: FAIL — search functions don't accept `weather` or `user_preferences` params

- [ ] **Step 3: Update search functions to accept and use context**

Update `backend/orchestrator/search.py`:

```python
from __future__ import annotations

from typing import Any

from backend.data.catalog import LocalDataCatalog
from backend.models.schemas import ParsedConstraints
from backend.tools.registry import LocalToolRegistry


def _is_weather_safe(poi: dict, weather: dict | None) -> bool:
    if not weather:
        return True
    condition = weather.get("condition", "clear")
    rain_prob = float(weather.get("rain_probability", 0))
    tags = set(poi.get("tags", []))
    # If it's raining or high rain probability, exclude outdoor-only POIs
    if (condition == "rain" or rain_prob > 0.6) and "outdoor" in tags and "indoor" not in tags and "rain_safe" not in tags:
        return False
    return True


def _preference_boost(poi: dict, user_preferences: dict | None) -> float:
    if not user_preferences:
        return 0.0
    poi_tags = set(poi.get("tags", []))
    preferred = set(user_preferences.get("activity", [])) | set(user_preferences.get("diet", []))
    return len(poi_tags & preferred) * 2.0


def _search_and_filter(
    catalog: LocalDataCatalog,
    category: str | None,
    scenario: str | None,
    radius: float,
    tags: list[str],
    weather: dict | None = None,
    user_preferences: dict | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    raw = catalog.search_pois(category, scenario, radius, tags)
    filtered = [poi for poi in raw if _is_weather_safe(poi, weather)]
    if user_preferences:
        filtered.sort(key=lambda p: (-_preference_boost(p, user_preferences), -float(p.get("rating", 0))))
    if limit:
        filtered = filtered[:limit]
    return filtered


def search_activities(
    catalog: LocalDataCatalog,
    constraints: ParsedConstraints,
    weather: dict | None = None,
    user_preferences: dict | None = None,
) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    activity_tags = list(constraints.preferences.get("activity", []))
    return _search_and_filter(catalog, None, constraints.scenario, radius, activity_tags, weather, user_preferences)


def search_restaurants(
    catalog: LocalDataCatalog,
    constraints: ParsedConstraints,
    weather: dict | None = None,
    user_preferences: dict | None = None,
) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    restaurant_tags = list(constraints.preferences.get("diet", [])) or ["booking_supported"]
    return _search_and_filter(catalog, "restaurant", constraints.scenario, radius, restaurant_tags, weather, user_preferences)


def search_walks(
    catalog: LocalDataCatalog,
    constraints: ParsedConstraints,
    weather: dict | None = None,
    user_preferences: dict | None = None,
) -> list[dict[str, Any]]:
    radius = float(constraints.constraints.get("radius_km"))
    walks = catalog.search_pois("dessert_walk", None, radius, ["walkable"])[:6]
    if not walks:
        walks = _search_and_filter(
            catalog, None,
            "date" if constraints.scenario == "date" else "family",
            radius, ["walkable"], weather, user_preferences,
        )
    else:
        walks = [w for w in walks if _is_weather_safe(w, weather)]
    return walks
```

- [ ] **Step 4: Update nodes.py search node to pass weather and preferences**

Update the `_search_activities_node`, `_search_restaurants_node`, `_search_walks_node` methods in `pipeline.py` (lines 172-191) to pass context:

```python
def _search_activities_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    state = graph_state["state"]
    constraints = require_constraints(state)
    weather = state.context.get("weather")
    user_prefs = graph_state.get("profile")
    user_preferences = user_prefs.as_dict() if user_prefs and hasattr(user_prefs, "as_dict") else None
    items = search_activities(self.catalog, constraints, weather=weather, user_preferences=user_preferences)
    emit_progress(graph_state, "搜索活动场所", f"找到 {len(items)} 个候选")
    return {"activity_candidates": items}


def _search_restaurants_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    state = graph_state["state"]
    constraints = require_constraints(state)
    weather = state.context.get("weather")
    user_prefs = graph_state.get("profile")
    user_preferences = user_prefs.as_dict() if user_prefs and hasattr(user_prefs, "as_dict") else None
    items = search_restaurants(self.catalog, constraints, weather=weather, user_preferences=user_preferences)
    emit_progress(graph_state, "搜索餐厅", f"找到 {len(items)} 个候选")
    return {"restaurant_candidates": items}


def _search_walks_node(self, graph_state: BuildGraphState) -> BuildGraphState:
    state = graph_state["state"]
    constraints = require_constraints(state)
    weather = state.context.get("weather")
    user_prefs = graph_state.get("profile")
    user_preferences = user_prefs.as_dict() if user_prefs and hasattr(user_prefs, "as_dict") else None
    items = search_walks(self.catalog, constraints, weather=weather, user_preferences=user_preferences)
    emit_progress(graph_state, "搜索散步点", f"找到 {len(items)} 个候选")
    return {"walk_candidates": items}
```

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All pass (144+ existing + new tests)

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator/search.py backend/orchestrator/pipeline.py tests/backend/test_search_context.py
git commit -m "feat(search): integrate weather filtering and user preference weighting into parallel search"
```

---

### Task 3: Extract constraint parsing to constraints.py

**Files:**
- Create: `backend/orchestrator/constraints.py`
- Modify: `backend/orchestrator/pipeline.py`

- [ ] **Step 1: Create constraints.py with extracted functions**

Move these functions from pipeline.py to `backend/orchestrator/constraints.py`:
- `extract_json_object`
- `deterministic_constraints`
- `detect_scenario`
- `parse_child_age`
- `parse_adult_count`
- `constraints_from_dict`
- `normalize_constraints_for_goal`
- `enrich_constraints_for_goal`
- `normalize_scenario_label`
- `infer_activity_tags`
- `infer_intent_label`
- `missing_required_fields`
- `clarifying_questions_for`
- `is_hiking_goal`
- `has_family_signal`
- `has_date_signal`
- `has_food_signal`
- `has_explicit_duration`
- `parse_party_size`
- `unique_list`
- `normalize_people`
- `normalize_time_window`
- `normalize_preferences`
- `normalize_constraints`
- `ACTION_ALIASES`
- `SUPPORTED_REQUIRED_ACTIONS`
- `normalize_required_actions`
- `as_list`
- `int_or_default`
- `float_or_default`

- [ ] **Step 2: Update pipeline.py imports**

Replace the moved function definitions in pipeline.py with imports from `backend.orchestrator.constraints`.

- [ ] **Step 3: Run all tests**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/orchestrator/constraints.py backend/orchestrator/pipeline.py
git commit -m "refactor: extract constraint parsing to constraints.py"
```

---

### Task 4: Extract itinerary building to itinerary.py

**Files:**
- Create: `backend/orchestrator/itinerary.py`
- Modify: `backend/orchestrator/pipeline.py`

- [ ] **Step 1: Create itinerary.py with extracted functions**

Move these functions from pipeline.py to `backend/orchestrator/itinerary.py`:
- `build_steps`
- `parse_time_minutes`
- `format_time`
- `score_step`
- `risk_text`
- `build_variants` → renamed to `build_itinerary_variants` (already imported from planning.candidates, keep the one that builds ItineraryStep variants)
- `copy_step`
- `build_pending_actions`
- `party_size_of`
- `scenario_theme`
- `format_duration_hours`
- `frontend_route`
- `duration_hours_of`
- `required_actions_of`
- `should_include_restaurant`
- `should_include_walk`
- `restaurant_time_from_steps`
- `find_step`
- `require_constraints`
- `emit_progress`
- `apply_constraint_overrides`
- `rank_items`
- `LLMIntentParsingError`
- `_apply_replacement`

- [ ] **Step 2: Update pipeline.py imports**

Replace moved definitions with imports from `backend.orchestrator.itinerary`.

- [ ] **Step 3: Run all tests**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/orchestrator/itinerary.py backend/orchestrator/pipeline.py
git commit -m "refactor: extract itinerary building and helpers to itinerary.py"
```

---

### Task 5: Verify final state

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest tests/backend/ -v --tb=short`
Expected: All 144+ tests pass

- [ ] **Step 2: Run simulation to verify end-to-end flow**

```bash
.venv/bin/python -c "
import json
from backend.orchestrator.pipeline import PlanningPipeline
from backend.llm.config import LLMConfig

class SimulatedLLM:
    def chat_stream(self, messages):
        system = messages[0]['content'].lower() if messages else ''
        if 'ranker' in system:
            yield json.dumps({'reasoning': 'test: using deterministic fallback'})
        elif 'validator' in system:
            yield json.dumps({'valid': True, 'issues': [], 'suggestions': [], 'overall_score': 91})
        elif 'recovery' in system:
            yield json.dumps({'action': 'adjust', 'reason': 'No issues'})
        else:
            yield json.dumps({
                'scenario': 'family',
                'origin': {'type': 'current_location', 'label': 'home', 'lat': 39.9042, 'lng': 116.4074},
                'time_window': {'date': 'today', 'start': '14:00', 'duration_hours': 3, 'flexible': True},
                'people': {'adults': 2, 'children': [{'age': 5}], 'relationship': 'family'},
                'preferences': {'distance': 'nearby', 'diet': ['low_fat'], 'activity': ['child_friendly', 'not_too_tiring'], 'budget_level': 'medium'},
                'constraints': {'radius_km': 5, 'max_wait_minutes': 15, 'avoid': ['long_queue']},
                'required_actions': ['send_plan_message', 'create_calendar_event'],
            }, ensure_ascii=False)

pipeline = PlanningPipeline(llm_config=LLMConfig(
    base_url='https://example.test/v1', api_key='test', model='test', remote_enabled=True,
))
pipeline.llm = SimulatedLLM()
result = pipeline.build('周末想带5岁孩子出去玩，不要太累，预算适中')
assert result.status == 'pending_confirmation'
assert len(result.ranked.get('activities', [])) > 0
assert len(result.itinerary) > 0
print(f'Status: {result.status}')
print(f'Activities: {len(result.ranked[\"activities\"])}')
print(f'Steps: {len(result.itinerary)}')
print('Simulation passed!')
"
```

Expected: "Simulation passed!"

- [ ] **Step 3: Verify pipeline.py line count is reduced**

```bash
wc -l backend/orchestrator/pipeline.py backend/orchestrator/constraints.py backend/orchestrator/itinerary.py backend/orchestrator/nodes.py backend/orchestrator/search.py
```

Expected: pipeline.py ~400 lines (down from 1260)

- [ ] **Step 4: Final commit if needed**
