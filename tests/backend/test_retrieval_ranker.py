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

    result = rank_candidates(search.items, constraints, top_k=20)

    risky_positions = [index for index, item in enumerate(result.items) if "weekend_queue" in item.place.risk_tags]
    safe_positions = [index for index, item in enumerate(result.items) if "weekend_queue" not in item.place.risk_tags]
    assert risky_positions
    assert safe_positions
    assert min(safe_positions) < min(risky_positions)
