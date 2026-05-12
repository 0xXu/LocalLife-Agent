# Open-Domain Backend Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the backend from an open-domain prompt parser wrapped around local templates into a grounded, testable, durable planning backend with explicit providers, ranked candidates, validated plans, action ledger execution, persistence, traces, and clarification states.

**Architecture:** Keep the current FastAPI + PlanningService + LangGraph shape, but split the backend into focused units: provider contracts, retrieval/ranking, itinerary candidate generation, validation, action ledger, persistence, and observability. Each task produces a working backend state with tests before implementation. Frontend changes are out of scope except where contract tests document response shape.

**Tech Stack:** Python 3.11, FastAPI, LangGraph, dataclasses, pytest, local seed data, OpenAI-compatible LLM client, TypeScript contract tests.

---

## Scope Check

This plan intentionally covers the backend foundation as one coherent release because the subsystems must interoperate through one plan response contract. If execution time becomes constrained, stop after Task 4; Tasks 1-4 produce a grounded planner without durable execution, while Tasks 5-8 harden reliability and operations.

## File Structure

- Create `backend/providers/contracts.py`: provider dataclasses and protocols for places, routes, availability, weather, reviews, and provenance.
- Create `backend/providers/local.py`: adapter over `LocalDataCatalog` that returns provider records with `source`, `freshness`, `confidence`, and `provenance`.
- Modify `backend/data/catalog.py`: keep seed data but expose richer fields consumed by providers.
- Create `backend/retrieval/ranker.py`: hybrid retrieval scoring with structured filters, semantic tag expansion, rejection reasons, and score breakdowns.
- Create `backend/planning/candidates.py`: generate multiple itinerary candidates from ranked candidate sets instead of copying one itinerary.
- Create `backend/validation/rules.py`: validate opening hours, route, budget, weather, party fit, availability, and action feasibility.
- Create `backend/actions/ledger.py`: action ledger model and execution helpers with selected action IDs and idempotency keys.
- Create `backend/storage/repository.py`: SQLite repository for plans, checkpoints, traces, actions, and receipts.
- Create `backend/observability/spans.py`: normalized spans for LLM, tool, validation, recovery, and execution events.
- Modify `backend/models/schemas.py`: add candidate sets, score breakdowns, validation issues, clarification responses, action ledger state, and provider provenance.
- Modify `backend/orchestrator/pipeline.py`: wire providers, retrieval, candidates, validation, clarification, and traces into LangGraph nodes.
- Modify `backend/services/planning_service.py`: persist plan state, expose selected-action execution, and return stable responses.
- Modify `backend/api/app.py`: support clarification responses, selected action execution, and stable JSON errors.
- Modify `tests/backend/test_pipeline.py`: pipeline behavior tests.
- Modify `tests/backend/test_complete_product_backend.py`: end-to-end backend tests.
- Create `tests/backend/test_providers.py`: provider contract tests.
- Create `tests/backend/test_retrieval_ranker.py`: retrieval and score breakdown tests.
- Create `tests/backend/test_validation_rules.py`: validation tests.
- Create `tests/backend/test_action_ledger.py`: selected action and idempotency tests.
- Create `tests/backend/test_repository.py`: persistence tests.
- Modify `tests/contracts/weekendpilot-contracts.test.ts`: frontend-facing response contract tests.

---

### Task 1: Provider Contracts And Grounding Metadata

**Files:**
- Create: `backend/providers/contracts.py`
- Create: `backend/providers/local.py`
- Modify: `backend/data/catalog.py`
- Test: `tests/backend/test_providers.py`

- [ ] **Step 1: Write the failing provider contract test**

Create `tests/backend/test_providers.py`:

```python
from backend.data.catalog import LocalDataCatalog
from backend.providers.local import LocalAvailabilityProvider, LocalPlaceProvider, LocalRouteProvider, LocalWeatherProvider


def test_place_provider_returns_grounded_records_with_provenance():
    provider = LocalPlaceProvider(LocalDataCatalog())

    result = provider.search(
        query="安静宠物散步",
        tags=["pet", "quiet", "walkable"],
        radius_km=8,
        limit=5,
    )

    assert result.query == "安静宠物散步"
    assert len(result.items) >= 1
    first = result.items[0]
    assert first.id.startswith("poi_")
    assert first.name
    assert first.provenance.source == "local_seed_catalog"
    assert first.provenance.confidence > 0
    assert first.provenance.freshness in {"seed_static", "live"}
    assert "pet" in first.tags or "walkable" in first.tags


def test_route_provider_returns_stable_route_with_provider_metadata():
    catalog = LocalDataCatalog()
    place_provider = LocalPlaceProvider(catalog)
    route_provider = LocalRouteProvider(catalog)
    items = place_provider.search("宠物散步", ["pet", "walkable"], 8, 2).items

    route = route_provider.optimize(items)

    assert route.provider == "local_seed_route_matrix"
    assert route.total_travel_minutes >= 0
    assert len(route.polyline["coordinates"]) >= 2
    assert route.provenance.source == "local_seed_route_matrix"


def test_availability_and_weather_providers_include_grounding():
    catalog = LocalDataCatalog()
    place = LocalPlaceProvider(catalog).search("低脂餐厅", ["low_fat"], 8, 1).items[0]

    availability = LocalAvailabilityProvider(catalog).check(place.id, "15:45", 2)
    weather = LocalWeatherProvider(catalog).current(rainy=True)

    assert availability.place_id == place.id
    assert availability.provenance.source == "mock_availability"
    assert weather.condition == "rain"
    assert weather.provenance.source == "local_weather_seed"
```

- [ ] **Step 2: Run the provider test to verify it fails**

Run: `uv run pytest tests/backend/test_providers.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.providers'`.

- [ ] **Step 3: Add provider contracts**

Create `backend/providers/contracts.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Provenance:
    source: str
    freshness: str
    confidence: float
    retrieved_at: str = "seed"
    raw_ref: str = ""


@dataclass
class GroundedPlace:
    id: str
    name: str
    category: str
    lat: float
    lng: float
    distance_km: float
    rating: float
    avg_price: int
    tags: list[str]
    reason: str
    risk_tags: list[str]
    open_hours: list[dict[str, str]]
    wait_minutes: int
    booking_supported: bool
    availability: list[dict]
    supported_scenarios: list[str]
    provenance: Provenance

    def as_poi_dict(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "lat": self.lat,
            "lng": self.lng,
            "distance_km": self.distance_km,
            "rating": self.rating,
            "avg_price": self.avg_price,
            "tags": list(self.tags),
            "reason": self.reason,
            "risk_tags": list(self.risk_tags),
            "open_hours": [dict(item) for item in self.open_hours],
            "wait_minutes": self.wait_minutes,
            "booking_supported": self.booking_supported,
            "availability": [dict(item) for item in self.availability],
            "supported_scenarios": list(self.supported_scenarios),
            "source": self.provenance.source,
            "provenance": {
                "source": self.provenance.source,
                "freshness": self.provenance.freshness,
                "confidence": self.provenance.confidence,
                "retrieved_at": self.provenance.retrieved_at,
                "raw_ref": self.provenance.raw_ref,
            },
        }
        data["duration_minutes"] = 110 if "activity" in self.category else 60 if self.category == "restaurant" else 35
        data["review_count"] = 100
        return data


@dataclass
class PlaceSearchResult:
    query: str
    tags: list[str]
    radius_km: float
    items: list[GroundedPlace]
    rejected: list[dict] = field(default_factory=list)


@dataclass
class GroundedRoute:
    legs: list[dict]
    total_travel_minutes: int
    walking_distance_km: float
    drive_time_minutes: int
    polyline: dict
    provider: str
    provenance: Provenance


@dataclass
class GroundedAvailability:
    place_id: str
    slot: str
    available: bool
    party_size: int
    provenance: Provenance


@dataclass
class GroundedWeather:
    condition: str
    temperature: int
    rain_probability: float
    provenance: Provenance


class PlaceProvider(Protocol):
    def search(self, query: str, tags: list[str], radius_km: float, limit: int) -> PlaceSearchResult:
        ...


class RouteProvider(Protocol):
    def optimize(self, waypoints: list[GroundedPlace]) -> GroundedRoute:
        ...


class AvailabilityProvider(Protocol):
    def check(self, place_id: str, time: str, party_size: int) -> GroundedAvailability:
        ...


class WeatherProvider(Protocol):
    def current(self, rainy: bool = False) -> GroundedWeather:
        ...
```

- [ ] **Step 4: Add local provider implementations**

Create `backend/providers/local.py`:

```python
from __future__ import annotations

from backend.data.catalog import LocalDataCatalog
from backend.providers.contracts import GroundedAvailability, GroundedPlace, GroundedRoute, GroundedWeather, PlaceSearchResult, Provenance


class LocalPlaceProvider:
    def __init__(self, catalog: LocalDataCatalog) -> None:
        self.catalog = catalog

    def search(self, query: str, tags: list[str], radius_km: float, limit: int) -> PlaceSearchResult:
        raw_items = self.catalog.search_pois(None, None, radius_km, tags)
        items = [ground_place(item, confidence_for_tags(item, tags)) for item in raw_items[:limit]]
        rejected = [
            {"id": item["id"], "reason": "outside_limit"}
            for item in raw_items[limit:limit + 8]
        ]
        return PlaceSearchResult(query=query, tags=list(tags), radius_km=radius_km, items=items, rejected=rejected)


class LocalRouteProvider:
    def __init__(self, catalog: LocalDataCatalog) -> None:
        self.catalog = catalog

    def optimize(self, waypoints: list[GroundedPlace]) -> GroundedRoute:
        legs: list[dict] = []
        total = 0
        walking_km = 0.0
        for left, right in zip(waypoints, waypoints[1:]):
            leg = self.catalog.route_matrix.get(left.id, {}).get(right.id, {"mode": "taxi", "minutes": 12, "distance_km": 2.0})
            total += int(leg["minutes"])
            if leg["mode"] == "walk":
                walking_km += float(leg["distance_km"])
            legs.append({"from_id": left.id, "to_id": right.id, **leg})
        coords = [[item.lng, item.lat] for item in waypoints]
        if len(coords) == 1:
            lng, lat = coords[0]
            coords.append([lng + 0.002, lat + 0.002])
        if not coords:
            coords = [[140.8824, 38.2601], [140.8844, 38.2621]]
        return GroundedRoute(
            legs=legs,
            total_travel_minutes=total,
            walking_distance_km=round(walking_km, 2),
            drive_time_minutes=total or 12,
            polyline={"type": "LineString", "coordinates": coords},
            provider="local_seed_route_matrix",
            provenance=Provenance("local_seed_route_matrix", "seed_static", 0.72),
        )


class LocalAvailabilityProvider:
    def __init__(self, catalog: LocalDataCatalog) -> None:
        self.catalog = catalog

    def check(self, place_id: str, time: str, party_size: int) -> GroundedAvailability:
        poi = self.catalog.get_poi(place_id)
        for slot in poi.get("availability", []):
            if slot.get("time") == time and int(slot.get("capacity", 0)) >= party_size:
                return GroundedAvailability(place_id, time, bool(slot.get("available")), party_size, Provenance("mock_availability", "seed_static", 0.68))
        return GroundedAvailability(place_id, time, True, party_size, Provenance("mock_availability_nearest", "seed_static", 0.55))


class LocalWeatherProvider:
    def __init__(self, catalog: LocalDataCatalog) -> None:
        self.catalog = catalog

    def current(self, rainy: bool = False) -> GroundedWeather:
        data = self.catalog.weather["rainy" if rainy else "today"]
        return GroundedWeather(
            condition=str(data["condition"]),
            temperature=int(data["temperature"]),
            rain_probability=float(data["rain_probability"]),
            provenance=Provenance("local_weather_seed", "seed_static", 0.7),
        )


def ground_place(item: dict, confidence: float) -> GroundedPlace:
    return GroundedPlace(
        id=item["id"],
        name=item["name"],
        category=item["category"],
        lat=float(item["lat"]),
        lng=float(item["lng"]),
        distance_km=float(item["distance_km"]),
        rating=float(item["rating"]),
        avg_price=int(item["avg_price"]),
        tags=list(item["tags"]),
        reason=item["reason"],
        risk_tags=list(item.get("risk_tags", [])),
        open_hours=[dict(value) for value in item["open_hours"]],
        wait_minutes=int(item.get("wait_minutes", 0)),
        booking_supported=bool(item.get("booking_supported", False)),
        availability=[dict(value) for value in item.get("availability", [])],
        supported_scenarios=list(item.get("supported_scenarios", [])),
        provenance=Provenance(item.get("source", "local_seed_catalog"), "seed_static", confidence, raw_ref=item["id"]),
    )


def confidence_for_tags(item: dict, tags: list[str]) -> float:
    if not tags:
        return 0.55
    matched = sum(tag in item.get("tags", []) for tag in tags)
    return round(min(0.95, 0.5 + matched / max(len(tags), 1) * 0.45), 2)
```

- [ ] **Step 5: Run provider tests to verify they pass**

Run: `uv run pytest tests/backend/test_providers.py -q`

Expected: PASS with `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/providers/contracts.py backend/providers/local.py tests/backend/test_providers.py
git commit -m "feat: add grounded provider contracts"
```

---

### Task 2: Hybrid Retrieval And Score Breakdown

**Files:**
- Create: `backend/retrieval/ranker.py`
- Modify: `backend/orchestrator/pipeline.py`
- Test: `tests/backend/test_retrieval_ranker.py`

- [ ] **Step 1: Write the failing retrieval tests**

Create `tests/backend/test_retrieval_ranker.py`:

```python
from backend.data.catalog import LocalDataCatalog
from backend.models.schemas import ParsedConstraints
from backend.providers.local import LocalPlaceProvider
from backend.retrieval.ranker import rank_candidates


def test_ranker_returns_score_breakdown_and_rejection_reasons():
    constraints = ParsedConstraints(
        scenario="pet_friendly_walk",
        origin={"type": "current_location", "label": "home", "lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 2, "flexible": True},
        people={"adults": 1, "children": [], "relationship": "solo"},
        preferences={"distance": "nearby", "diet": [], "activity": ["pet", "quiet", "walkable"], "budget_level": "medium"},
        constraints={"radius_km": 8, "max_wait_minutes": 15, "avoid": ["long_queue"]},
        required_actions=["send_plan_message"],
    )
    provider = LocalPlaceProvider(LocalDataCatalog())
    search = provider.search("想带狗狗找个安静散步的地方", ["pet", "quiet", "walkable"], 8, 12)

    result = rank_candidates(search.items, constraints, top_k=5)

    assert len(result.items) >= 1
    first = result.items[0]
    assert first.place.id
    assert first.total_score > 0
    assert {"semantic", "distance", "quality", "wait", "budget"} <= set(first.breakdown)
    assert first.explanation
    assert isinstance(result.rejected, list)


def test_ranker_penalizes_avoided_risk_tags():
    constraints = ParsedConstraints(
        scenario="family",
        origin={"type": "current_location", "label": "home", "lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 4, "flexible": True},
        people={"adults": 2, "children": [{"age": 5}], "relationship": "family"},
        preferences={"distance": "nearby", "diet": [], "activity": ["child_friendly"], "budget_level": "medium"},
        constraints={"radius_km": 8, "max_wait_minutes": 5, "avoid": ["weekend_queue"]},
        required_actions=["activity_reservation"],
    )
    provider = LocalPlaceProvider(LocalDataCatalog())
    search = provider.search("带孩子轻松玩", ["child_friendly"], 8, 20)

    result = rank_candidates(search.items, constraints, top_k=8)

    risky_positions = [index for index, item in enumerate(result.items) if "weekend_queue" in item.place.risk_tags]
    safe_positions = [index for index, item in enumerate(result.items) if "weekend_queue" not in item.place.risk_tags]
    assert risky_positions
    assert safe_positions
    assert min(safe_positions) < min(risky_positions)
```

- [ ] **Step 2: Run retrieval tests to verify they fail**

Run: `uv run pytest tests/backend/test_retrieval_ranker.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.retrieval'`.

- [ ] **Step 3: Implement ranker**

Create `backend/retrieval/ranker.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.schemas import ParsedConstraints
from backend.providers.contracts import GroundedPlace


@dataclass
class RankedCandidate:
    place: GroundedPlace
    total_score: float
    breakdown: dict[str, float]
    explanation: str


@dataclass
class RankedCandidateSet:
    items: list[RankedCandidate]
    rejected: list[dict] = field(default_factory=list)


def rank_candidates(items: list[GroundedPlace], constraints: ParsedConstraints, top_k: int = 8) -> RankedCandidateSet:
    ranked: list[RankedCandidate] = []
    rejected: list[dict] = []
    for item in items:
        breakdown = score_breakdown(item, constraints)
        total = round(sum(breakdown.values()), 3)
        if item.distance_km > float(constraints.constraints.get("radius_km", 8)):
            rejected.append({"id": item.id, "reason": "outside_radius", "distance_km": item.distance_km})
            continue
        ranked.append(RankedCandidate(item, total, breakdown, explanation_for(item, breakdown)))
    ranked.sort(key=lambda value: value.total_score, reverse=True)
    return RankedCandidateSet(items=ranked[:top_k], rejected=rejected + [{"id": item.place.id, "reason": "below_top_k"} for item in ranked[top_k:]])


def score_breakdown(item: GroundedPlace, constraints: ParsedConstraints) -> dict[str, float]:
    tags = set(item.tags)
    preferred = set(constraints.preferences.get("activity", [])) | set(constraints.preferences.get("diet", []))
    avoid = set(constraints.constraints.get("avoid", []))
    radius = max(float(constraints.constraints.get("radius_km", 8)), 1.0)
    max_wait = max(int(constraints.constraints.get("max_wait_minutes", 15)), 1)
    budget_level = str(constraints.preferences.get("budget_level", "medium"))
    risk_penalty = 0.2 if avoid & set(item.risk_tags) else 0.0
    return {
        "semantic": min(0.32, len(tags & preferred) * 0.09),
        "distance": max(0.0, 0.22 * (1 - item.distance_km / radius)),
        "quality": min(0.2, item.rating / 5 * 0.2),
        "wait": max(0.0, 0.14 * (1 - item.wait_minutes / max_wait)),
        "budget": budget_score(budget_level, item.avg_price),
        "provenance": min(0.08, item.provenance.confidence * 0.08),
        "risk": -risk_penalty,
    }


def budget_score(level: str, avg_price: int) -> float:
    if level == "low":
        return 0.12 if avg_price <= 160 else 0.05 if avg_price <= 260 else 0.0
    if level == "high":
        return 0.1 if avg_price <= 600 else 0.04
    return 0.12 if avg_price <= 360 else 0.05


def explanation_for(item: GroundedPlace, breakdown: dict[str, float]) -> str:
    best = max(breakdown, key=lambda key: breakdown[key])
    labels = {
        "semantic": "偏好匹配高",
        "distance": "距离更近",
        "quality": "评分较好",
        "wait": "等待更短",
        "budget": "预算更合适",
        "provenance": "来源可信度较高",
        "risk": "风险更低",
    }
    return f"{item.name}：{labels.get(best, '综合匹配较好')}。"
```

- [ ] **Step 4: Run retrieval tests to verify they pass**

Run: `uv run pytest tests/backend/test_retrieval_ranker.py -q`

Expected: PASS with `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/retrieval/ranker.py tests/backend/test_retrieval_ranker.py
git commit -m "feat: add grounded retrieval ranker"
```

---

### Task 3: Candidate Sets In Pipeline Response

**Files:**
- Modify: `backend/models/schemas.py`
- Modify: `backend/orchestrator/pipeline.py`
- Modify: `tests/backend/test_complete_product_backend.py`
- Modify: `tests/contracts/weekendpilot-contracts.test.ts`

- [ ] **Step 1: Write failing backend response test**

Append to `tests/backend/test_complete_product_backend.py`:

```python
def test_plan_response_includes_candidate_sets_and_score_breakdown(self):
    result = self.service.build_plan("想带狗狗找个安静散步的地方，别太吵")

    assert "candidate_sets" in result
    assert "activities" in result["candidate_sets"]
    first = result["candidate_sets"]["activities"][0]
    assert "score_breakdown" in first
    assert "explanation" in first
    assert "provenance" in first["place"]
    assert result["plan"]["constraint_fit"]["distance"] >= 0
```

- [ ] **Step 2: Run backend test to verify it fails**

Run: `uv run pytest tests/backend/test_complete_product_backend.py::CompleteBackendTest::test_plan_response_includes_candidate_sets_and_score_breakdown -q`

Expected: FAIL with `AssertionError: assert 'candidate_sets' in result`.

- [ ] **Step 3: Add candidate_sets to PlanState and response**

Modify `backend/models/schemas.py`:

```python
@dataclass
class PlanState:
    goal: str
    plan_id: str = ""
    status: str = "input_received"
    constraints: ParsedConstraints | None = None
    context: dict[str, Any] = field(default_factory=dict)
    candidates: dict[str, list[POI]] = field(default_factory=dict)
    candidate_sets: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    rejected_candidates: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    ranked: dict[str, list[POI]] = field(default_factory=dict)
    itinerary: list[ItineraryStep] = field(default_factory=list)
    route: dict[str, Any] = field(default_factory=dict)
    overview: PlanOverview | None = None
    actions: list[PlanAction] = field(default_factory=list)
    pending_actions: list[PlanAction] = field(default_factory=list)
    variants: list[PlanVariant] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    receipts: list[Receipt] = field(default_factory=list)
    diff: RecoveryDiff | None = None
    recovery_history: list[RecoveryDiff] = field(default_factory=list)
    adjustment: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
```

In `state_response(state)`, add:

```python
        "candidate_sets": state.candidate_sets,
        "rejected_candidates": state.rejected_candidates,
```

- [ ] **Step 4: Wire ranker output into pipeline**

Modify `backend/orchestrator/pipeline.py` imports:

```python
from backend.providers.local import LocalPlaceProvider
from backend.retrieval.ranker import rank_candidates
```

Modify `PlanningPipeline.__init__`:

```python
        self.place_provider = LocalPlaceProvider(self.catalog)
```

Replace `_rank_candidates_node` body:

```python
    def _rank_candidates_node(self, graph_state: BuildGraphState) -> BuildGraphState:
        state = graph_state["state"]
        constraints = require_constraints(state)
        ranked: dict[str, list[dict]] = {}
        candidate_sets: dict[str, list[dict[str, Any]]] = {}
        rejected: dict[str, list[dict[str, Any]]] = {}
        for key, items in state.candidates.items():
            grounded = [self.place_provider.search(item["name"], item.get("tags", []), float(constraints.constraints.get("radius_km", 8)), 1).items[0] for item in items]
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
        state.ranked = ranked
        state.candidate_sets = candidate_sets
        state.rejected_candidates = rejected
        state.status = "ranked"
        state.add_trace(TraceStep("RankerAgent", "rank_candidates", "ok", "按语义、距离、质量、等待、预算、来源和风险排序。", {}, {key: [item["place"]["id"] for item in value[:3]] for key, value in candidate_sets.items()}, 180))
        emit_progress(graph_state, "多目标排序", "按语义、距离、质量、等待、预算、来源和风险排序。")
        return {"state": state}
```

- [ ] **Step 5: Run backend response test to verify it passes**

Run: `uv run pytest tests/backend/test_complete_product_backend.py::CompleteBackendTest::test_plan_response_includes_candidate_sets_and_score_breakdown -q`

Expected: PASS.

- [ ] **Step 6: Add TypeScript contract test**

Append to `tests/contracts/weekendpilot-contracts.test.ts`:

```ts
test('PlanResponse exposes candidate sets with score breakdowns', () => {
  const response = PlanResponseSchema.parse({
    constraints: {
      scenario: 'pet_friendly_walk',
      origin: { type: 'current_location', label: 'home', lat: 38.26, lng: 140.88 },
      time_window: { date: 'today', start: '14:00', duration_hours: 2, flexible: true },
      people: { adults: 1, children: [], relationship: 'solo' },
      preferences: { distance: 'nearby', diet: [], activity: ['pet'], budget_level: 'medium' },
      constraints: { radius_km: 8, max_wait_minutes: 15, avoid: [] },
      required_actions: ['send_plan_message'],
    },
    progress: [],
    trace: [],
    tool_calls: [],
    candidate_sets: {
      activities: [{
        place: { id: 'poi_007', name: '宠物友好河岸公园', provenance: { source: 'local_seed_catalog', freshness: 'seed_static', confidence: 0.9 } },
        total_score: 0.86,
        score_breakdown: { semantic: 0.27, distance: 0.18, quality: 0.19, wait: 0.1, budget: 0.12 },
        explanation: '偏好匹配高。',
      }],
    },
    rejected_candidates: {},
    itinerary: [],
    pending_actions: [],
    plan: {
      id: 'plan_1',
      status: 'pending_confirmation',
      title: '宠物散步短计划',
      summary: '本地生活计划',
      constraint_fit: { distance: 0.9, time: 1, budget: 0.92 },
      itinerary: [],
      overview: { theme: '下午', totalDuration: '2 小时', driveTime: '约 12 分钟', walkingDistance: '0 公里', estimatedCost: '约 120 元', score: 90 },
      actions: [],
      variants: [],
    },
  });

  assert.equal((response as any).candidate_sets.activities[0].place.provenance.source, 'local_seed_catalog');
});
```

- [ ] **Step 7: Update TypeScript schema**

Modify `lib/contracts/schemas.ts`:

```ts
export const CandidateSetItemSchema = z.object({
  place: z.record(z.string(), JsonSchema),
  total_score: z.number(),
  score_breakdown: z.record(z.string(), z.number()),
  explanation: z.string(),
});
```

Add to `PlanResponseSchema`:

```ts
  candidate_sets: z.record(z.string(), z.array(CandidateSetItemSchema)).default({}),
  rejected_candidates: z.record(z.string(), z.array(z.record(z.string(), JsonSchema))).default({}),
```

- [ ] **Step 8: Run contract tests**

Run: `npm run test:contracts`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/models/schemas.py backend/orchestrator/pipeline.py tests/backend/test_complete_product_backend.py lib/contracts/schemas.ts tests/contracts/weekendpilot-contracts.test.ts
git commit -m "feat: expose ranked candidate sets"
```

---

### Task 4: Real Itinerary Candidate Generation

**Files:**
- Create: `backend/planning/candidates.py`
- Modify: `backend/orchestrator/pipeline.py`
- Test: `tests/backend/test_pipeline.py`

- [ ] **Step 1: Write failing itinerary diversity test**

Append to `tests/backend/test_pipeline.py`:

```python
def test_variants_use_different_place_combinations_not_copies(self):
    result = self.service.build_plan("今天下午朋友4个人出去玩，先活动再吃饭，预算适中")

    variant_place_sets = {
        tuple(step["place_id"] for step in variant["itinerary"] if step.get("place_id") and step["place_id"] != "origin_home")
        for variant in result["plan"]["variants"]
    }

    self.assertGreaterEqual(len(variant_place_sets), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/backend/test_pipeline.py::PlanningPipelineTest::test_variants_use_different_place_combinations_not_copies -q`

Expected: FAIL because all variants use the same place IDs.

- [ ] **Step 3: Implement candidate generation**

Create `backend/planning/candidates.py`:

```python
from __future__ import annotations

from backend.models.schemas import ItineraryStep, ParsedConstraints, PlanVariant


def build_itinerary_variants(
    activity_candidates: list[dict],
    restaurant_candidates: list[dict],
    walk_candidates: list[dict],
    build_steps_fn,
    constraints: ParsedConstraints,
    base_budget: int,
    base_score: int,
) -> list[PlanVariant]:
    variants: list[PlanVariant] = []
    combos = [
        ("main", "主方案", "综合距离、可订性和偏好匹配。", 0, 0, 0, base_score, base_budget),
        ("budget", "省钱版", "优先选择低客单价和更短路线。", 1, 1, 0, max(60, base_score - 4), max(120, base_budget - 120)),
        ("comfort", "舒适版", "优先高评分、低等待和少步行。", 2, 0, 1, min(98, base_score + 2), base_budget + 120),
        ("experience_first", "体验优先版", "优先活动体验和偏好匹配。", 0, 2, 0, max(60, min(98, base_score - 1)), base_budget + 60),
    ]
    for kind, title, summary, activity_index, restaurant_index, walk_index, score, budget in combos:
        activity = pick(activity_candidates, activity_index)
        restaurant = pick(restaurant_candidates, restaurant_index)
        walk = pick(walk_candidates, walk_index)
        itinerary: list[ItineraryStep] = build_steps_fn(activity, restaurant, walk, constraints)
        variants.append(PlanVariant(kind, title, summary, score, budget, itinerary))
    return variants


def pick(items: list[dict], index: int) -> dict | None:
    if not items:
        return None
    return items[min(index, len(items) - 1)]
```

- [ ] **Step 4: Wire candidate generation into pipeline**

Modify `_build_itinerary_node` in `backend/orchestrator/pipeline.py`:

```python
from backend.planning.candidates import build_itinerary_variants
```

Replace variant assignment:

```python
        state.variants = build_itinerary_variants(
            state.ranked.get("activities", []),
            state.ranked.get("restaurants", []) if restaurant else [],
            state.ranked.get("walks", []) if walk else [],
            build_steps,
            constraints,
            build_result.output["estimated_budget"],
            build_result.output["score"],
        )
```

- [ ] **Step 5: Run itinerary diversity test**

Run: `uv run pytest tests/backend/test_pipeline.py::PlanningPipelineTest::test_variants_use_different_place_combinations_not_copies -q`

Expected: PASS.

- [ ] **Step 6: Run backend tests**

Run: `npm run test:backend`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/planning/candidates.py backend/orchestrator/pipeline.py tests/backend/test_pipeline.py
git commit -m "feat: generate diverse itinerary variants"
```

---

### Task 5: Product-Grade Validation Rules

**Files:**
- Create: `backend/validation/rules.py`
- Modify: `backend/models/schemas.py`
- Modify: `backend/orchestrator/pipeline.py`
- Test: `tests/backend/test_validation_rules.py`

- [ ] **Step 1: Write failing validation tests**

Create `tests/backend/test_validation_rules.py`:

```python
from backend.models.schemas import ItineraryStep, ParsedConstraints
from backend.validation.rules import validate_itinerary


def test_validation_flags_weather_and_opening_hours_risks():
    constraints = ParsedConstraints(
        scenario="rainy_indoor",
        origin={"type": "current_location", "label": "home", "lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 2, "flexible": True},
        people={"adults": 2, "children": [], "relationship": "friends"},
        preferences={"distance": "nearby", "diet": [], "activity": ["outdoor"], "budget_level": "medium"},
        constraints={"radius_km": 8, "max_wait_minutes": 15, "avoid": ["outdoor"]},
        required_actions=["send_plan_message"],
    )
    steps = [
        ItineraryStep("14:00", "15:30", "activity", "山野徒步步道", "poi_hike", "户外", "约 100 元", "到达活动点", 90, "风险低。")
    ]
    candidate_lookup = {
        "poi_hike": {"open_hours": [{"day": "sat", "start": "10:00", "end": "13:00"}], "tags": ["outdoor"], "avg_price": 100, "booking_supported": True}
    }

    report = validate_itinerary(steps, constraints, candidate_lookup, weather={"condition": "rain", "rain_probability": 0.86}, route={"total_travel_minutes": 12})

    assert not report.valid
    assert {issue["code"] for issue in report.issues} >= {"closed_at_visit_time", "weather_mismatch"}


def test_validation_passes_grounded_short_plan():
    constraints = ParsedConstraints(
        scenario="deep_work_cafe",
        origin={"type": "current_location", "label": "home", "lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 1, "flexible": True},
        people={"adults": 1, "children": [], "relationship": "solo"},
        preferences={"distance": "nearby", "diet": [], "activity": ["work", "quiet"], "budget_level": "medium"},
        constraints={"radius_km": 8, "max_wait_minutes": 15, "avoid": []},
        required_actions=["send_plan_message"],
    )
    steps = [
        ItineraryStep("14:00", "15:00", "activity", "自习咖啡馆", "poi_cafe", "安静", "约 80 元", "到达活动点", 90, "风险低。")
    ]
    candidate_lookup = {
        "poi_cafe": {"open_hours": [{"day": "sat", "start": "10:00", "end": "22:00"}], "tags": ["work", "quiet"], "avg_price": 80, "booking_supported": True}
    }

    report = validate_itinerary(steps, constraints, candidate_lookup, weather={"condition": "clear", "rain_probability": 0.1}, route={"total_travel_minutes": 12})

    assert report.valid
    assert report.issues == []
```

- [ ] **Step 2: Run validation tests to verify they fail**

Run: `uv run pytest tests/backend/test_validation_rules.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.validation'`.

- [ ] **Step 3: Implement validation rules**

Create `backend/validation/rules.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.schemas import ItineraryStep, ParsedConstraints


@dataclass
class ValidationReport:
    valid: bool
    issues: list[dict] = field(default_factory=list)


def validate_itinerary(
    steps: list[ItineraryStep],
    constraints: ParsedConstraints,
    candidate_lookup: dict[str, dict],
    weather: dict,
    route: dict,
) -> ValidationReport:
    issues: list[dict] = []
    for step in steps:
        if step.type == "transport":
            continue
        candidate = candidate_lookup.get(step.place_id, {})
        if not is_open_at(candidate.get("open_hours", []), step.start):
            issues.append({"code": "closed_at_visit_time", "place_id": step.place_id, "time": step.start})
        if weather.get("condition") == "rain" and "outdoor" in candidate.get("tags", []):
            issues.append({"code": "weather_mismatch", "place_id": step.place_id})
    if int(route.get("total_travel_minutes", 0)) > int(float(constraints.time_window.get("duration_hours", 4)) * 60):
        issues.append({"code": "route_timeout", "minutes": route.get("total_travel_minutes")})
    budget = sum(int(candidate_lookup.get(step.place_id, {}).get("avg_price", 0)) for step in steps)
    if str(constraints.preferences.get("budget_level", "medium")) == "low" and budget > 500:
        issues.append({"code": "budget_overrun", "budget": budget})
    return ValidationReport(valid=not issues, issues=issues)


def is_open_at(open_hours: list[dict], time_value: str) -> bool:
    if not open_hours:
        return True
    for item in open_hours:
        if str(item.get("start", "00:00")) <= time_value <= str(item.get("end", "23:59")):
            return True
    return False
```

- [ ] **Step 4: Wire validation report into PlanState**

Modify `backend/models/schemas.py` PlanState:

```python
    validation_issues: list[dict[str, Any]] = field(default_factory=list)
```

In `state_response(state)`, add:

```python
        "validation_issues": state.validation_issues,
```

Modify `_validate_plan_node` in `backend/orchestrator/pipeline.py`:

```python
from backend.validation.rules import validate_itinerary
```

After existing `validation = ...`:

```python
        lookup = {item["id"]: item for group in state.ranked.values() for item in group}
        detailed_report = validate_itinerary(state.itinerary, constraints, lookup, state.context.get("weather", {}), route)
        state.validation_issues = detailed_report.issues
        validation["valid"] = validation["valid"] and detailed_report.valid
        validation["issues"] = list(dict.fromkeys([*validation.get("issues", []), *[issue["code"] for issue in detailed_report.issues]]))
```

- [ ] **Step 5: Run validation tests**

Run: `uv run pytest tests/backend/test_validation_rules.py -q`

Expected: PASS with `2 passed`.

- [ ] **Step 6: Run backend tests**

Run: `npm run test:backend`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/validation/rules.py backend/models/schemas.py backend/orchestrator/pipeline.py tests/backend/test_validation_rules.py
git commit -m "feat: add detailed itinerary validation"
```

---

### Task 6: Selected Action Ledger And Idempotent Execution

**Files:**
- Create: `backend/actions/ledger.py`
- Modify: `backend/models/schemas.py`
- Modify: `backend/services/planning_service.py`
- Modify: `backend/api/app.py`
- Test: `tests/backend/test_action_ledger.py`
- Test: `tests/backend/test_api.py`

- [ ] **Step 1: Write failing ledger tests**

Create `tests/backend/test_action_ledger.py`:

```python
from backend.actions.ledger import ActionLedger, ledger_from_actions
from backend.models.schemas import PlanAction


def test_ledger_executes_only_selected_actions_once():
    actions = [
        PlanAction("message", "发送计划", "同行人", "发送摘要", True, "send_plan_message", {"recipient": "同行人"}),
        PlanAction("calendar", "创建日历", "本地日历", "创建提醒", True, "create_calendar_event", {"participants": 1}),
    ]
    ledger = ledger_from_actions("plan_1", actions)
    selected = [ledger.entries[0].action_id]

    executed = ledger.mark_executing(selected, idempotency_key="idem_1")
    repeated = ledger.mark_executing(selected, idempotency_key="idem_1")

    assert [entry.action_id for entry in executed] == selected
    assert repeated == []
    assert ledger.entries[0].status == "executing"
    assert ledger.entries[1].status == "pending"
```

- [ ] **Step 2: Run ledger test to verify it fails**

Run: `uv run pytest tests/backend/test_action_ledger.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.actions'`.

- [ ] **Step 3: Implement action ledger**

Create `backend/actions/ledger.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.schemas import PlanAction


@dataclass
class ActionEntry:
    action_id: str
    plan_id: str
    action: PlanAction
    status: str = "pending"
    idempotency_keys: set[str] = field(default_factory=set)
    receipt_id: str = ""
    error: str = ""


@dataclass
class ActionLedger:
    plan_id: str
    entries: list[ActionEntry]

    def mark_executing(self, selected_action_ids: list[str], idempotency_key: str) -> list[ActionEntry]:
        selected = set(selected_action_ids)
        changed: list[ActionEntry] = []
        for entry in self.entries:
            if entry.action_id not in selected:
                continue
            if idempotency_key in entry.idempotency_keys:
                continue
            if entry.status in {"succeeded", "skipped"}:
                continue
            entry.idempotency_keys.add(idempotency_key)
            entry.status = "executing"
            changed.append(entry)
        return changed

    def mark_succeeded(self, action_id: str, receipt_id: str) -> None:
        entry = self.get(action_id)
        entry.status = "succeeded"
        entry.receipt_id = receipt_id

    def get(self, action_id: str) -> ActionEntry:
        for entry in self.entries:
            if entry.action_id == action_id:
                return entry
        raise KeyError(action_id)


def ledger_from_actions(plan_id: str, actions: list[PlanAction]) -> ActionLedger:
    return ActionLedger(plan_id, [ActionEntry(stable_action_id(action), plan_id, action) for action in actions])


def stable_action_id(action: PlanAction) -> str:
    target = action.target.replace(" ", "_")
    return f"{action.tool or action.type}_{target or 'default'}"
```

- [ ] **Step 4: Wire service execution to selected actions**

Modify `backend/models/schemas.py` PlanState:

```python
    action_ledger: dict[str, Any] = field(default_factory=dict)
```

Modify `PlanningService.confirm_plan()`:

```python
from backend.actions.ledger import ledger_from_actions

        ledger = ledger_from_actions(plan_id, state.pending_actions)
        state.action_ledger = {
            "entries": [
                {"action_id": entry.action_id, "status": entry.status, "tool": entry.action.tool, "target": entry.action.target}
                for entry in ledger.entries
            ]
        }
```

Modify `PlanningService.execute_plan()` signature:

```python
    def execute_plan(self, plan_id: str, confirmed: bool, selected_action_ids: list[str] | None = None, idempotency_key: str = "") -> dict:
```

Inside `execute_plan`, before `self.pipeline.execute(state)`:

```python
        if selected_action_ids is not None:
            selected = set(selected_action_ids)
            state.pending_actions = [action for action in state.pending_actions if action_dict(action)["id"] in selected]
        if not idempotency_key:
            idempotency_key = f"{plan_id}:{','.join(selected_action_ids or ['all'])}"
```

Modify `backend/api/app.py` execute route:

```python
        return planning_service(request).execute_plan(
            plan_id,
            bool(body.get("confirmed")),
            selected_action_ids=body.get("selected_action_ids") if isinstance(body.get("selected_action_ids"), list) else None,
            idempotency_key=str(body.get("idempotency_key", "")),
        )
```

- [ ] **Step 5: Add API failing test for selected actions**

Append to `tests/backend/test_api.py`:

```python
    def test_execute_accepts_selected_action_ids(self):
        status, built = self.request("POST", "/api/plans/build", {"goal": "我想找个地方写代码一小时"})
        self.assertEqual(status, 200)
        plan_id = built["plan"]["id"]
        action_id = next(action["id"] for action in built["pending_actions"] if action["tool"] == "send_plan_message")

        status, executed = self.request(
            "POST",
            f"/api/plans/{plan_id}/execute",
            {"confirmed": True, "selected_action_ids": [action_id], "idempotency_key": "test-idem-1"},
        )

        self.assertEqual(status, 200)
        self.assertEqual([receipt["tool"] for receipt in executed["receipts"]], ["send_plan_message"])
```

- [ ] **Step 6: Run action ledger and API tests**

Run: `uv run pytest tests/backend/test_action_ledger.py tests/backend/test_api.py::BackendApiTest::test_execute_accepts_selected_action_ids -q`

Expected: PASS.

- [ ] **Step 7: Run backend tests**

Run: `npm run test:backend`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/actions/ledger.py backend/models/schemas.py backend/services/planning_service.py backend/api/app.py tests/backend/test_action_ledger.py tests/backend/test_api.py
git commit -m "feat: execute selected actions idempotently"
```

---

### Task 7: SQLite Repository For Durable Plan State

**Files:**
- Create: `backend/storage/repository.py`
- Modify: `backend/services/planning_service.py`
- Test: `tests/backend/test_repository.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/backend/test_repository.py`:

```python
from pathlib import Path

from backend.services.planning_service import PlanningService
from tests.backend.helpers import planning_service_with_fake_llm


def test_plan_survives_service_recreation(tmp_path: Path):
    db_path = tmp_path / "weekendpilot.sqlite"
    service = planning_service_with_fake_llm(db_path=db_path)
    built = service.build_plan("今天下午朋友4个人出去玩，先活动再吃饭")
    plan_id = built["plan"]["id"]

    recreated = planning_service_with_fake_llm(db_path=db_path)
    fetched = recreated.get_plan(plan_id)

    assert fetched["plan"]["id"] == plan_id
    assert fetched["plan"]["title"] == built["plan"]["title"]
```

- [ ] **Step 2: Run repository test to verify it fails**

Run: `uv run pytest tests/backend/test_repository.py -q`

Expected: FAIL because `planning_service_with_fake_llm()` does not accept `db_path`.

- [ ] **Step 3: Implement repository**

Create `backend/storage/repository.py`:

```python
from __future__ import annotations

import pickle
import sqlite3
from pathlib import Path
from typing import Any


class PlanRepository:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "create table if not exists plans (plan_id text primary key, state_blob blob not null)"
            )

    def save_state(self, plan_id: str, state: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                "insert or replace into plans(plan_id, state_blob) values (?, ?)",
                (plan_id, sqlite3.Binary(pickle.dumps(state))),
            )

    def get_state(self, plan_id: str) -> Any | None:
        with self._connect() as conn:
            row = conn.execute("select state_blob from plans where plan_id = ?", (plan_id,)).fetchone()
        return pickle.loads(row[0]) if row else None

    def list_states(self) -> list[Any]:
        with self._connect() as conn:
            rows = conn.execute("select state_blob from plans order by rowid").fetchall()
        return [pickle.loads(row[0]) for row in rows]
```

- [ ] **Step 4: Wire repository into PlanningService**

Modify `backend/services/planning_service.py`:

```python
from pathlib import Path
from backend.storage.repository import PlanRepository
```

Change constructor:

```python
    def __init__(self, catalog: LocalDataCatalog | None = None, llm_config: LLMConfig | None = None, repository_path: Path | str | None = None) -> None:
        self.catalog = catalog or LocalDataCatalog()
        self.pipeline = PlanningPipeline(self.catalog, llm_config)
        self.tool_registry = LocalToolRegistry(self.catalog)
        self.trace_store = TraceStore()
        self.repository = PlanRepository(repository_path) if repository_path else None
        self._plans: dict[str, PlanState] = {}
        self._checkpoints: dict[str, dict] = {}
        if self.repository:
            for state in self.repository.list_states():
                self._plans[state.plan_id] = state
                self._checkpoints[state.plan_id] = to_dict(state.checkpoint())
                self.trace_store.save(state.plan_id, state.trace)
```

Modify `_save()`:

```python
        if self.repository:
            self.repository.save_state(state.plan_id, state)
```

- [ ] **Step 5: Update test helper**

Modify `tests/backend/helpers.py`:

```python
def planning_service_with_fake_llm(db_path=None) -> PlanningService:
    service = PlanningService(llm_config=configured_test_llm_config(), repository_path=db_path)
    service.pipeline.llm = RuleBasedLLMClient()
    return service
```

- [ ] **Step 6: Run repository test**

Run: `uv run pytest tests/backend/test_repository.py -q`

Expected: PASS.

- [ ] **Step 7: Run backend tests**

Run: `npm run test:backend`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/storage/repository.py backend/services/planning_service.py tests/backend/helpers.py tests/backend/test_repository.py
git commit -m "feat: persist plan state in sqlite"
```

---

### Task 8: User Profile And Memory Store

**Files:**
- Create: `backend/profile/models.py`
- Create: `backend/profile/store.py`
- Create: `backend/profile/resolver.py`
- Modify: `backend/storage/repository.py`
- Modify: `backend/services/planning_service.py`
- Modify: `backend/orchestrator/pipeline.py`
- Modify: `backend/api/app.py`
- Test: `tests/backend/test_user_profile.py`
- Modify: `tests/contracts/weekendpilot-contracts.test.ts`

- [ ] **Step 1: Write failing user profile tests**

Create `tests/backend/test_user_profile.py`:

```python
from pathlib import Path

from backend.profile.models import UserProfile, UserPreference
from backend.profile.resolver import merge_profile_into_goal_context
from backend.profile.store import UserProfileStore
from backend.models.schemas import ParsedConstraints


def test_profile_store_persists_explicit_and_learned_preferences(tmp_path: Path):
    store = UserProfileStore(tmp_path / "profiles.sqlite")
    profile = UserProfile(
        user_id="user_1",
        explicit_preferences=[
            UserPreference("pace", "slow", "explicit", 1.0, "long_term", "用户主动选择慢节奏"),
            UserPreference("budget_level", "low", "explicit", 1.0, "long_term", "用户主动选择低预算"),
        ],
        learned_preferences=[
            UserPreference("avoid", "long_queue", "feedback", 0.82, "long_term", "连续两次反馈不想排队"),
        ],
    )

    store.save(profile)
    loaded = store.get("user_1")

    assert loaded.user_id == "user_1"
    assert loaded.preference_value("pace") == "slow"
    assert loaded.preference_value("budget_level") == "low"
    assert loaded.preferences_by_key("avoid")[0].confidence == 0.82


def test_current_goal_overrides_profile_preferences():
    profile = UserProfile(
        user_id="user_1",
        explicit_preferences=[UserPreference("budget_level", "low", "explicit", 1.0, "long_term", "用户偏好低预算")],
        learned_preferences=[UserPreference("pace", "slow", "feedback", 0.8, "long_term", "用户常反馈太赶")],
    )
    constraints = ParsedConstraints(
        scenario="date",
        origin={"type": "current_location", "label": "home", "lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 3, "flexible": True},
        people={"adults": 2, "children": [], "relationship": "date"},
        preferences={"distance": "nearby", "diet": [], "activity": ["quiet"], "budget_level": "high"},
        constraints={"radius_km": 8, "max_wait_minutes": 15, "avoid": []},
        required_actions=["send_plan_message"],
    )

    merged = merge_profile_into_goal_context(constraints, profile)

    assert merged.preferences["budget_level"] == "high"
    assert merged.preferences["pace"] == "slow"
    assert "long_queue" not in merged.constraints["avoid"]
```

- [ ] **Step 2: Run profile tests to verify they fail**

Run: `uv run pytest tests/backend/test_user_profile.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.profile'`.

- [ ] **Step 3: Add profile models**

Create `backend/profile/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserPreference:
    key: str
    value: Any
    source: str
    confidence: float
    scope: str
    evidence: str
    expires_at: str = ""
    user_editable: bool = True
    sensitive: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "scope": self.scope,
            "evidence": self.evidence,
            "expires_at": self.expires_at,
            "user_editable": self.user_editable,
            "sensitive": self.sensitive,
        }


@dataclass
class UserProfile:
    user_id: str
    explicit_preferences: list[UserPreference] = field(default_factory=list)
    learned_preferences: list[UserPreference] = field(default_factory=list)
    session_preferences: list[UserPreference] = field(default_factory=list)

    def all_preferences(self) -> list[UserPreference]:
        return [*self.learned_preferences, *self.explicit_preferences, *self.session_preferences]

    def preferences_by_key(self, key: str) -> list[UserPreference]:
        return [preference for preference in self.all_preferences() if preference.key == key]

    def preference_value(self, key: str, default=None):
        values = self.preferences_by_key(key)
        if not values:
            return default
        values.sort(key=lambda preference: source_priority(preference.source), reverse=True)
        return values[-1].value

    def as_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "explicit_preferences": [item.as_dict() for item in self.explicit_preferences],
            "learned_preferences": [item.as_dict() for item in self.learned_preferences],
            "session_preferences": [item.as_dict() for item in self.session_preferences],
        }


def source_priority(source: str) -> int:
    return {"feedback": 1, "learned": 2, "explicit": 3, "session": 4}.get(source, 0)
```

The `preference_value()` implementation must choose the highest priority value. Keep this exact implementation:

```python
    def preference_value(self, key: str, default=None):
        values = self.preferences_by_key(key)
        if not values:
            return default
        values.sort(key=lambda preference: (source_priority(preference.source), preference.confidence), reverse=True)
        return values[0].value
```

- [ ] **Step 4: Add SQLite profile store**

Create `backend/profile/store.py`:

```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.profile.models import UserPreference, UserProfile


class UserProfileStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute("create table if not exists user_profiles (user_id text primary key, profile_json text not null)")

    def save(self, profile: UserProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                "insert or replace into user_profiles(user_id, profile_json) values (?, ?)",
                (profile.user_id, json.dumps(profile.as_dict(), ensure_ascii=False)),
            )

    def get(self, user_id: str) -> UserProfile:
        with self._connect() as conn:
            row = conn.execute("select profile_json from user_profiles where user_id = ?", (user_id,)).fetchone()
        if not row:
            return UserProfile(user_id=user_id)
        return profile_from_dict(json.loads(row[0]))


def profile_from_dict(data: dict) -> UserProfile:
    return UserProfile(
        user_id=data["user_id"],
        explicit_preferences=[preference_from_dict(item) for item in data.get("explicit_preferences", [])],
        learned_preferences=[preference_from_dict(item) for item in data.get("learned_preferences", [])],
        session_preferences=[preference_from_dict(item) for item in data.get("session_preferences", [])],
    )


def preference_from_dict(data: dict) -> UserPreference:
    return UserPreference(
        key=data["key"],
        value=data.get("value"),
        source=data.get("source", "learned"),
        confidence=float(data.get("confidence", 0.5)),
        scope=data.get("scope", "long_term"),
        evidence=data.get("evidence", ""),
        expires_at=data.get("expires_at", ""),
        user_editable=bool(data.get("user_editable", True)),
        sensitive=bool(data.get("sensitive", False)),
    )
```

- [ ] **Step 5: Add profile resolver**

Create `backend/profile/resolver.py`:

```python
from __future__ import annotations

from copy import deepcopy

from backend.models.schemas import ParsedConstraints
from backend.profile.models import UserProfile


def merge_profile_into_goal_context(constraints: ParsedConstraints, profile: UserProfile | None) -> ParsedConstraints:
    if profile is None:
        return constraints
    merged = deepcopy(constraints)
    apply_if_missing(merged.preferences, "pace", profile.preference_value("pace"))
    apply_if_missing(merged.preferences, "transport", profile.preference_value("transport"))
    apply_if_missing(merged.preferences, "diet", list_values(profile, "diet"))
    avoid_values = list_values(profile, "avoid")
    if avoid_values and not merged.constraints.get("avoid"):
        merged.constraints["avoid"] = avoid_values
    if not merged.preferences.get("budget_level"):
        budget = profile.preference_value("budget_level")
        if budget:
            merged.preferences["budget_level"] = budget
    return merged


def apply_if_missing(target: dict, key: str, value) -> None:
    if value in (None, "", []):
        return
    if key not in target or target.get(key) in (None, "", []):
        target[key] = value


def list_values(profile: UserProfile, key: str) -> list:
    return [preference.value for preference in profile.preferences_by_key(key) if preference.confidence >= 0.65]
```

- [ ] **Step 6: Wire profile into PlanningService**

Modify `backend/services/planning_service.py` constructor:

```python
from backend.profile.store import UserProfileStore

    def __init__(..., repository_path: Path | str | None = None, profile_store_path: Path | str | None = None) -> None:
        ...
        default_profile_path = Path(".weekendpilot/profiles.sqlite")
        self.profile_store = UserProfileStore(profile_store_path or default_profile_path)
```

Modify `build_plan` signature:

```python
    def build_plan(self, goal: str, on_progress: Callable[[str, str], None] | None = None, on_token: Callable[[str], None] | None = None, user_id: str = "local_demo_user") -> dict:
        if not goal.strip():
            raise ValueError("validation_error")
        profile = self.profile_store.get(user_id) if self.profile_store else None
        state = self.pipeline.build(goal, on_progress=on_progress, on_token=on_token, profile=profile)
        self._save(state)
        response = state_response(state)
        if profile:
            response["user_profile"] = profile.as_dict()
        return response
```

Add service methods:

```python
    def get_user_profile(self, user_id: str) -> dict:
        if not self.profile_store:
            return {"user_id": user_id, "explicit_preferences": [], "learned_preferences": [], "session_preferences": []}
        return self.profile_store.get(user_id).as_dict()

    def save_user_profile(self, profile: UserProfile) -> dict:
        if not self.profile_store:
            raise ValueError("profile_store_not_configured")
        self.profile_store.save(profile)
        return profile.as_dict()
```

- [ ] **Step 7: Wire profile into pipeline**

Modify `BuildGraphState` in `backend/orchestrator/pipeline.py`:

```python
    profile: Any | None
```

Modify `PlanningPipeline.build`:

```python
    def build(self, goal: str, overrides: dict | None = None, on_progress: Callable[[str, str], None] | None = None, on_token: Callable[[str], None] | None = None, profile=None) -> PlanState:
        state = PlanState(goal=goal, plan_id=f"plan_{uuid4().hex[:10]}", status="input_received")
        result = self.graph.invoke({"state": state, "overrides": overrides, "on_progress": on_progress, "on_token": on_token, "profile": profile})
        return result["state"]
```

Import and use resolver in `_parse_intent_node`:

```python
from backend.profile.resolver import merge_profile_into_goal_context

        profile = graph_state.get("profile")
        if profile:
            constraints = merge_profile_into_goal_context(constraints, profile)
            state.context["user_profile"] = profile.as_dict()
```

- [ ] **Step 8: Add profile API endpoints**

Modify `backend/api/app.py` imports:

```python
from backend.profile.models import UserPreference, UserProfile
```

Add routes:

```python
    @api.get("/api/users/{user_id}/profile")
    async def get_user_profile(user_id: str, request: Request) -> dict[str, Any]:
        return planning_service(request).get_user_profile(user_id)

    @api.post("/api/users/{user_id}/profile")
    async def save_user_profile(user_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        profile = UserProfile(
            user_id=user_id,
            explicit_preferences=[UserPreference(**item) for item in body.get("explicit_preferences", [])],
            learned_preferences=[UserPreference(**item) for item in body.get("learned_preferences", [])],
            session_preferences=[UserPreference(**item) for item in body.get("session_preferences", [])],
        )
        return planning_service(request).save_user_profile(profile)
```

- [ ] **Step 9: Run profile tests**

Run: `uv run pytest tests/backend/test_user_profile.py -q`

Expected: PASS.

- [ ] **Step 10: Run backend tests**

Run: `npm run test:backend`

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add backend/profile backend/storage/repository.py backend/services/planning_service.py backend/orchestrator/pipeline.py backend/api/app.py tests/backend/test_user_profile.py tests/contracts/weekendpilot-contracts.test.ts
git commit -m "feat: add user profile memory layer"
```

---

### Task 9: Plan Feedback And Revision Loop

**Files:**
- Create: `backend/revision/models.py`
- Create: `backend/revision/parser.py`
- Create: `backend/revision/diff.py`
- Modify: `backend/models/schemas.py`
- Modify: `backend/services/planning_service.py`
- Modify: `backend/orchestrator/pipeline.py`
- Modify: `backend/api/app.py`
- Test: `tests/backend/test_plan_revision.py`
- Modify: `tests/contracts/weekendpilot-contracts.test.ts`

- [ ] **Step 1: Write failing revision tests**

Create `tests/backend/test_plan_revision.py`:

```python
from tests.backend.helpers import planning_service_with_fake_llm


def test_revision_applies_natural_language_feedback_and_returns_diff():
    service = planning_service_with_fake_llm()
    built = service.build_plan("今天下午朋友4个人出去玩，先活动再吃饭，预算适中")
    plan_id = built["plan"]["id"]
    restaurant_ids = [step["place_id"] for step in built["plan"]["itinerary"] if step["type"] == "restaurant"]
    assert restaurant_ids

    revised = service.revise_plan(
        plan_id,
        {
            "feedback_text": "太赶了，餐厅不想去了，换成轻松一点的散步和咖啡",
            "selected_issue_codes": ["too_rushed", "remove_restaurant"],
            "locked_nodes": [],
            "removed_nodes": restaurant_ids,
            "preference_updates": {"pace": "slow", "meal_required": False},
            "save_to_profile": True,
            "user_id": "user_1",
        },
    )

    assert revised["revision"]["revision_id"].startswith("rev_")
    assert "restaurant" not in [step["type"] for step in revised["plan"]["itinerary"]]
    assert revised["diff"]["removed"]
    assert revised["diff"]["changed_constraints"]["pace"] == ["medium", "slow"]
    assert revised["learned_preferences"][0]["key"] == "pace"


def test_revision_preserves_locked_nodes():
    service = planning_service_with_fake_llm()
    built = service.build_plan("想带狗狗找个能散步的地方，别太吵")
    plan_id = built["plan"]["id"]
    activity = next(step for step in built["plan"]["itinerary"] if step["type"] == "activity")

    revised = service.revise_plan(
        plan_id,
        {
            "feedback_text": "预算低一点，但这个活动保留",
            "selected_issue_codes": ["cheaper"],
            "locked_nodes": [activity["place_id"]],
            "removed_nodes": [],
            "preference_updates": {"budget_level": "low"},
            "save_to_profile": False,
            "user_id": "user_1",
        },
    )

    revised_activity = next(step for step in revised["plan"]["itinerary"] if step["type"] == "activity")
    assert revised_activity["place_id"] == activity["place_id"]
```

- [ ] **Step 2: Run revision tests to verify they fail**

Run: `uv run pytest tests/backend/test_plan_revision.py -q`

Expected: FAIL because `PlanningService` has no `revise_plan`.

- [ ] **Step 3: Add revision models**

Create `backend/revision/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class PlanFeedback:
    feedback_text: str
    selected_issue_codes: list[str] = field(default_factory=list)
    locked_nodes: list[str] = field(default_factory=list)
    removed_nodes: list[str] = field(default_factory=list)
    preference_updates: dict[str, Any] = field(default_factory=dict)
    save_to_profile: bool = False
    user_id: str = "local_demo_user"


@dataclass
class RevisionDelta:
    revision_id: str
    feedback_text: str
    constraint_updates: dict[str, Any]
    locked_nodes: list[str]
    removed_nodes: list[str]
    save_to_profile: bool
    user_id: str


def new_revision_delta(feedback: PlanFeedback) -> RevisionDelta:
    return RevisionDelta(
        revision_id=f"rev_{uuid4().hex[:10]}",
        feedback_text=feedback.feedback_text,
        constraint_updates=dict(feedback.preference_updates),
        locked_nodes=list(feedback.locked_nodes),
        removed_nodes=list(feedback.removed_nodes),
        save_to_profile=feedback.save_to_profile,
        user_id=feedback.user_id,
    )
```

- [ ] **Step 4: Add feedback parser**

Create `backend/revision/parser.py`:

```python
from __future__ import annotations

from backend.revision.models import PlanFeedback, RevisionDelta, new_revision_delta


def parse_feedback(body: dict) -> PlanFeedback:
    return PlanFeedback(
        feedback_text=str(body.get("feedback_text", "")),
        selected_issue_codes=[str(item) for item in body.get("selected_issue_codes", [])],
        locked_nodes=[str(item) for item in body.get("locked_nodes", [])],
        removed_nodes=[str(item) for item in body.get("removed_nodes", [])],
        preference_updates=dict(body.get("preference_updates", {})),
        save_to_profile=bool(body.get("save_to_profile", False)),
        user_id=str(body.get("user_id", "local_demo_user")),
    )


def feedback_to_delta(body: dict) -> RevisionDelta:
    feedback = parse_feedback(body)
    updates = dict(feedback.preference_updates)
    text = feedback.feedback_text
    if "太赶" in text or "轻松" in text or "慢" in text:
        updates["pace"] = "slow"
        updates["duration_hours"] = max(float(updates.get("duration_hours", 4.0)), 4.0)
    if "不想吃" in text or "餐厅不想去" in text or "不要餐厅" in text:
        updates["meal_required"] = False
    if "预算低" in text or "便宜" in text or "省钱" in text:
        updates["budget_level"] = "low"
    feedback.preference_updates = updates
    return new_revision_delta(feedback)
```

- [ ] **Step 5: Add plan diff builder**

Create `backend/revision/diff.py`:

```python
from __future__ import annotations


def build_plan_diff(before: dict, after: dict, changed_constraints: dict) -> dict:
    before_steps = {step.get("place_id"): step for step in before.get("itinerary", []) if step.get("place_id")}
    after_steps = {step.get("place_id"): step for step in after.get("itinerary", []) if step.get("place_id")}
    kept = [step["title"] for place_id, step in after_steps.items() if place_id in before_steps]
    removed = [{"id": place_id, "title": step["title"], "reason": "user_feedback"} for place_id, step in before_steps.items() if place_id not in after_steps]
    added = [{"id": place_id, "title": step["title"]} for place_id, step in after_steps.items() if place_id not in before_steps]
    return {
        "kept": kept,
        "removed": removed,
        "added": added,
        "changed_constraints": changed_constraints,
    }
```

- [ ] **Step 6: Add pipeline revision method**

Modify `backend/orchestrator/pipeline.py`:

```python
from copy import deepcopy
from backend.revision.models import RevisionDelta
```

Add method to `PlanningPipeline`:

```python
    def revise(self, state: PlanState, delta: RevisionDelta, profile=None) -> PlanState:
        updates = dict(delta.constraint_updates)
        if updates.get("meal_required") is False:
            updates["required_actions"] = [
                action for action in as_list(require_constraints(state).required_actions)
                if action not in {"restaurant_reservation", "claim_coupon", "create_order"}
            ]
        rebuilt = self.build(state.goal, updates, profile=profile)
        locked = set(delta.locked_nodes)
        if locked:
            for index, step in enumerate(rebuilt.itinerary):
                previous = next((old for old in state.itinerary if old.place_id == step.place_id or old.place_id in locked), None)
                if previous and previous.place_id in locked:
                    rebuilt.itinerary[index] = previous
        if delta.removed_nodes:
            rebuilt.itinerary = [step for step in rebuilt.itinerary if step.place_id not in set(delta.removed_nodes)]
            rebuilt.pending_actions = [action for action in rebuilt.pending_actions if action.payload.get("place_id") not in set(delta.removed_nodes) and action.payload.get("shop_id") not in set(delta.removed_nodes)]
            rebuilt.actions = list(rebuilt.pending_actions)
        rebuilt.plan_id = state.plan_id
        rebuilt.status = "pending_confirmation"
        rebuilt.context["revision"] = {
            "revision_id": delta.revision_id,
            "feedback_text": delta.feedback_text,
            "constraint_updates": delta.constraint_updates,
        }
        return rebuilt
```

Extend `apply_constraint_overrides`:

```python
    if "pace" in overrides:
        constraints.preferences["pace"] = str(overrides["pace"])
    if "meal_required" in overrides and overrides["meal_required"] is False:
        constraints.required_actions = [
            action for action in constraints.required_actions
            if action not in {"restaurant_reservation", "claim_coupon", "create_order"}
        ]
    if "required_actions" in overrides:
        constraints.required_actions = as_list(overrides["required_actions"])
```

- [ ] **Step 7: Add PlanningService.revise_plan**

Modify `backend/services/planning_service.py`:

```python
from backend.profile.models import UserPreference
from backend.revision.diff import build_plan_diff
from backend.revision.parser import feedback_to_delta
```

Add method:

```python
    def revise_plan(self, plan_id: str, body: dict) -> dict:
        state = self._require_plan(plan_id)
        before = state.plan_dict()
        delta = feedback_to_delta(body)
        profile = self.profile_store.get(delta.user_id) if self.profile_store else None
        revised = self.pipeline.revise(state, delta, profile=profile)
        after = revised.plan_dict()
        diff = build_plan_diff(before, after, {
            key: [state.constraints.preferences.get(key, "medium") if state.constraints else "medium", value]
            for key, value in delta.constraint_updates.items()
            if key in {"pace", "budget_level", "meal_required", "duration_hours"}
        })
        learned = []
        if delta.save_to_profile and self.profile_store:
            profile = self.profile_store.get(delta.user_id)
            for key, value in delta.constraint_updates.items():
                pref = UserPreference(key, value, "feedback", 0.72, "long_term", delta.feedback_text)
                profile.learned_preferences.append(pref)
                learned.append(pref.as_dict())
            self.profile_store.save(profile)
        self._save(revised)
        response = state_response(revised)
        response["revision"] = {
            "revision_id": delta.revision_id,
            "feedback_text": delta.feedback_text,
            "constraint_updates": delta.constraint_updates,
        }
        response["diff"] = diff
        response["learned_preferences"] = learned
        return response
```

- [ ] **Step 8: Add feedback and revise API routes**

Modify `backend/api/app.py`:

```python
    @api.post("/api/plans/{plan_id}/feedback")
    async def plan_feedback(plan_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        return planning_service(request).revise_plan(plan_id, body)

    @api.post("/api/plans/{plan_id}/revise")
    async def revise_plan(plan_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        return planning_service(request).revise_plan(plan_id, body)

    @api.get("/api/plans/{plan_id}/revisions")
    async def plan_revisions(plan_id: str, request: Request) -> dict[str, Any]:
        plan = planning_service(request).get_plan(plan_id)
        revision = plan.get("plan", {}).get("context", {}).get("revision", {})
        return {"plan_id": plan_id, "revisions": [revision] if revision else []}
```

- [ ] **Step 9: Run revision tests**

Run: `uv run pytest tests/backend/test_plan_revision.py -q`

Expected: PASS.

- [ ] **Step 10: Add TypeScript revision contract test**

Append to `tests/contracts/weekendpilot-contracts.test.ts`:

```ts
test('Plan revision response includes diff and learned preferences', () => {
  const response = PlanRevisionResponseSchema.parse({
    revision: {
      revision_id: 'rev_001',
      feedback_text: '太赶了，餐厅不想去了',
      constraint_updates: { pace: 'slow', meal_required: false },
    },
    diff: {
      kept: ['宠物友好河岸公园'],
      removed: [{ id: 'poi_019', title: '绿荫轻食餐厅', reason: 'user_feedback' }],
      added: [{ id: 'poi_008', title: '自习咖啡馆' }],
      changed_constraints: { pace: ['medium', 'slow'] },
    },
    learned_preferences: [{
      key: 'pace',
      value: 'slow',
      source: 'feedback',
      confidence: 0.72,
      scope: 'long_term',
      evidence: '太赶了',
      user_editable: true,
      sensitive: false,
    }],
  });

  assert.equal(response.revision.revision_id, 'rev_001');
});
```

Add schemas to `lib/contracts/schemas.ts`:

```ts
export const UserPreferenceSchema = z.object({
  key: z.string(),
  value: JsonSchema,
  source: z.string(),
  confidence: z.number(),
  scope: z.string(),
  evidence: z.string(),
  expires_at: z.string().optional(),
  user_editable: z.boolean().default(true),
  sensitive: z.boolean().default(false),
});

export const PlanRevisionResponseSchema = z.object({
  revision: z.object({
    revision_id: z.string(),
    feedback_text: z.string(),
    constraint_updates: z.record(z.string(), JsonSchema),
  }),
  diff: z.object({
    kept: z.array(z.string()).default([]),
    removed: z.array(z.record(z.string(), JsonSchema)).default([]),
    added: z.array(z.record(z.string(), JsonSchema)).default([]),
    changed_constraints: z.record(z.string(), JsonSchema).default({}),
  }),
  learned_preferences: z.array(UserPreferenceSchema).default([]),
}).passthrough();
```

- [ ] **Step 11: Run contract and backend tests**

Run: `npm run test:contracts && npm run test:backend`

Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add backend/revision backend/models/schemas.py backend/services/planning_service.py backend/orchestrator/pipeline.py backend/api/app.py tests/backend/test_plan_revision.py lib/contracts/schemas.ts tests/contracts/weekendpilot-contracts.test.ts
git commit -m "feat: add plan feedback revision loop"
```

---

### Task 10: Clarification State For Underspecified Goals

**Files:**
- Modify: `backend/models/schemas.py`
- Modify: `backend/orchestrator/pipeline.py`
- Modify: `backend/services/planning_service.py`
- Modify: `backend/api/app.py`
- Test: `tests/backend/test_pipeline.py`
- Modify: `tests/contracts/weekendpilot-contracts.test.ts`

- [ ] **Step 1: Write failing clarification test**

Append to `tests/backend/test_pipeline.py`:

```python
def test_underspecified_goal_returns_clarification_instead_of_low_confidence_plan(self):
    result = self.service.build_plan("周末安排一下")

    self.assertEqual(result["status"], "needs_clarification")
    self.assertGreaterEqual(len(result["clarifying_questions"]), 2)
    self.assertIn("time_window", result["missing_fields"])
    self.assertNotIn("plan", result)
```

- [ ] **Step 2: Run clarification test to verify it fails**

Run: `uv run pytest tests/backend/test_pipeline.py::PlanningPipelineTest::test_underspecified_goal_returns_clarification_instead_of_low_confidence_plan -q`

Expected: FAIL because current service returns a plan.

- [ ] **Step 3: Add clarification helpers**

Modify `backend/orchestrator/pipeline.py`:

```python
def missing_required_fields(goal: str, constraints: ParsedConstraints) -> list[str]:
    missing: list[str] = []
    if len(goal.strip()) < 8 or goal.strip() in {"周末安排一下", "帮我安排一下"}:
        missing.extend(["time_window", "activity_intent"])
    if not constraints.preferences.get("activity"):
        missing.append("activity_intent")
    if constraints.people.get("adults", 0) <= 0:
        missing.append("people")
    return list(dict.fromkeys(missing))


def clarifying_questions_for(missing: list[str]) -> list[dict[str, str]]:
    questions = []
    if "time_window" in missing:
        questions.append({"field": "time_window", "question": "你想安排今天、周六还是周日？大概几小时？"})
    if "activity_intent" in missing:
        questions.append({"field": "activity_intent", "question": "你更想户外走走、室内放松、吃饭聚会，还是亲子活动？"})
    if "people" in missing:
        questions.append({"field": "people", "question": "这次几个人一起去？有没有孩子、老人或宠物？"})
    return questions
```

Modify `_parse_intent_node` after constraints:

```python
        missing = missing_required_fields(state.goal, constraints)
        if missing:
            state.status = "needs_clarification"
            state.context["missing_fields"] = missing
            state.context["clarifying_questions"] = clarifying_questions_for(missing)
            state.add_trace(TraceStep("IntentParserAgent", "clarify_goal", "warning", "目标信息不足，返回澄清问题。", {}, {"missing_fields": missing}, 80))
            return {"state": state}
```

Add conditional graph routing:

```python
        graph.add_conditional_edges("parse_intent", should_continue_after_parse, {"continue": "build_context", "clarify": END})
```

Replace direct `graph.add_edge("parse_intent", "build_context")`.

Add:

```python
def should_continue_after_parse(graph_state: BuildGraphState) -> str:
    return "clarify" if graph_state["state"].status == "needs_clarification" else "continue"
```

- [ ] **Step 4: Return clarification response from service**

Modify `backend/models/schemas.py` `state_response(state)`:

```python
    if state.status == "needs_clarification":
        return {
            "status": "needs_clarification",
            "plan_id": state.plan_id,
            "missing_fields": state.context.get("missing_fields", []),
            "clarifying_questions": state.context.get("clarifying_questions", []),
            "trace": [to_dict(step) for step in state.trace],
            "tool_calls": [to_dict(call) for call in state.tool_calls],
        }
```

- [ ] **Step 5: Run clarification test**

Run: `uv run pytest tests/backend/test_pipeline.py::PlanningPipelineTest::test_underspecified_goal_returns_clarification_instead_of_low_confidence_plan -q`

Expected: PASS.

- [ ] **Step 6: Add TypeScript contract test and schema**

Append to `tests/contracts/weekendpilot-contracts.test.ts`:

```ts
test('ClarificationResponse represents underspecified goals', () => {
  const parsed = ClarificationResponseSchema.parse({
    status: 'needs_clarification',
    plan_id: 'plan_clarify_001',
    missing_fields: ['time_window', 'activity_intent'],
    clarifying_questions: [
      { field: 'time_window', question: '你想安排今天、周六还是周日？大概几小时？' },
      { field: 'activity_intent', question: '你更想户外走走、室内放松、吃饭聚会，还是亲子活动？' },
    ],
    trace: [],
    tool_calls: [],
  });

  assert.equal(parsed.status, 'needs_clarification');
});
```

Add to `lib/contracts/schemas.ts`:

```ts
export const ClarificationResponseSchema = z.object({
  status: z.literal('needs_clarification'),
  plan_id: z.string(),
  missing_fields: z.array(z.string()).default([]),
  clarifying_questions: z.array(z.object({
    field: z.string(),
    question: z.string(),
  })).default([]),
  trace: z.array(TraceSpanSchema).default([]),
  tool_calls: z.array(ToolCallSchema).default([]),
});
```

- [ ] **Step 7: Run contract and backend tests**

Run: `npm run test:contracts && npm run test:backend`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/models/schemas.py backend/orchestrator/pipeline.py tests/backend/test_pipeline.py lib/contracts/schemas.ts tests/contracts/weekendpilot-contracts.test.ts
git commit -m "feat: return clarification for underspecified goals"
```

---

### Task 11: Normalized Observability Spans

**Files:**
- Create: `backend/observability/spans.py`
- Modify: `backend/models/schemas.py`
- Modify: `backend/orchestrator/pipeline.py`
- Modify: `backend/services/planning_service.py`
- Test: `tests/backend/test_pipeline.py`

- [ ] **Step 1: Write failing span test**

Append to `tests/backend/test_pipeline.py`:

```python
def test_trace_spans_include_kind_timing_model_and_provider_context(self):
    result = self.service.build_plan("想带狗狗找个能散步的地方，别太吵")

    span = result["trace"][0]
    self.assertIn("span_id", span)
    self.assertIn("kind", span)
    self.assertIn(span["kind"], {"llm", "tool", "validation", "planning", "execution", "recovery"})
    self.assertIn("duration_ms", span)
    self.assertIn("metadata", span)
```

- [ ] **Step 2: Run span test to verify it fails**

Run: `uv run pytest tests/backend/test_pipeline.py::PlanningPipelineTest::test_trace_spans_include_kind_timing_model_and_provider_context -q`

Expected: FAIL because trace does not include `span_id` and `kind`.

- [ ] **Step 3: Add span helper**

Create `backend/observability/spans.py`:

```python
from __future__ import annotations

from uuid import uuid4

from backend.models.schemas import TraceStep


def span(agent: str, tool: str, status: str, message: str, kind: str, input_summary: dict | None = None, output_summary: dict | None = None, duration_ms: int = 0, metadata: dict | None = None) -> TraceStep:
    trace = TraceStep(agent, tool, status, message, input_summary or {}, output_summary or {}, duration_ms)
    trace.output_summary = {
        **trace.output_summary,
        "_span": {
            "span_id": f"span_{uuid4().hex[:10]}",
            "kind": kind,
            "metadata": metadata or {},
        },
    }
    return trace
```

Modify `backend/models/schemas.py` trace serialization:

```python
def trace_dict(step: TraceStep) -> dict[str, Any]:
    data = to_dict(step)
    span_data = {}
    if isinstance(data.get("output_summary"), dict):
        span_data = data["output_summary"].pop("_span", {}) or {}
    data["span_id"] = span_data.get("span_id", "")
    data["kind"] = span_data.get("kind", "planning")
    data["metadata"] = span_data.get("metadata", {})
    return data
```

Use in `state_response`:

```python
        "trace": [trace_dict(step) for step in state.trace],
```

- [ ] **Step 4: Convert key trace writes**

In `backend/orchestrator/pipeline.py`, import:

```python
from backend.observability.spans import span
```

Change each `state.add_trace(TraceStep(...))` call touched in build path to `state.add_trace(span(...))` with kind:

```python
state.add_trace(span("IntentParserAgent", "parse_user_goal", "ok", "解析自然语言目标为结构化约束。", "llm", {"goal_length": len(state.goal)}, {"scenario": constraints.scenario, "llm_fallback": llm_fallback}, 140, {"model": self.llm_config.model}))
```

For tool nodes use kind `"tool"`, validation node use `"validation"`, confirmation node use `"planning"`, execution node use `"execution"`, recovery node use `"recovery"`.

- [ ] **Step 5: Run span test**

Run: `uv run pytest tests/backend/test_pipeline.py::PlanningPipelineTest::test_trace_spans_include_kind_timing_model_and_provider_context -q`

Expected: PASS.

- [ ] **Step 6: Run full backend tests**

Run: `npm run test:backend`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/observability/spans.py backend/models/schemas.py backend/orchestrator/pipeline.py tests/backend/test_pipeline.py
git commit -m "feat: normalize backend trace spans"
```

---

### Task 12: Full Verification And Release Readiness

**Files:**
- Modify: none unless verification reveals a failing test.

- [ ] **Step 1: Run backend tests**

Run: `npm run test:backend`

Expected: PASS with all backend tests passing.

- [ ] **Step 2: Run contract tests**

Run: `npm run test:contracts`

Expected: PASS with all contract tests passing.

- [ ] **Step 3: Run frontend tests**

Run: `npm run test:frontend`

Expected: PASS with all frontend tests passing.

- [ ] **Step 4: Run full test command**

Run: `npm run test:all`

Expected: PASS for contracts, frontend, and backend.

- [ ] **Step 5: Run production build**

Run: `npm run build`

Expected: `✓ Compiled successfully` and route output for `/`.

- [ ] **Step 6: Inspect git diff**

Run: `git status --short`

Expected: only files from this plan are modified.

- [ ] **Step 7: Commit verification fixes if any were required**

If Step 1-5 required code changes, run:

```bash
git add backend tests lib app components
git commit -m "test: verify open-domain backend hardening"
```

If no code changes were required, do not create an empty commit.

---

## Self-Review

**Spec coverage:** The plan covers grounded provider interfaces, retrieval/ranking, candidate generation, validation, selected action execution, persistence, user profile memory, natural-language feedback revision, clarification, and observability. These map to the core backend problems identified in the product review and the later personalization/refinement requirements.

**Placeholder scan:** The plan avoids placeholder markers and includes concrete file paths, tests, implementation snippets, commands, and expected results for each task.

**Type consistency:** The plan consistently uses `ParsedConstraints`, `GroundedPlace`, `RankedCandidateSet`, `ValidationReport`, `ActionLedger`, `PlanRepository`, `UserProfile`, `UserPreference`, `PlanFeedback`, `RevisionDelta`, and existing `PlanState`/`PlanAction` names. Response fields are snake_case to match the current Python API contract.
