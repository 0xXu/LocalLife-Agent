import pytest
from pydantic import ValidationError

from app.domain.models import Constraint, POI, UserIntent


def test_intent_normalizes_empty_categories() -> None:
    intent = UserIntent(query="今晚约会", city="上海", preferred_categories=None)
    assert intent.preferred_categories == []


def test_poi_requires_rating_in_valid_range() -> None:
    POI(id="p1", name="Cafe", category="RESTAURANT", city="上海", rating=4.5)


def test_poi_rejects_rating_outside_valid_range() -> None:
    with pytest.raises(ValidationError):
        POI(id="p1", name="Cafe", category="RESTAURANT", city="上海", rating=5.1)


def test_constraint_factories_preserve_budget_and_hard_time_window() -> None:
    assert Constraint.budget(200, weight=2).value == 200
    time_window = Constraint.time_window("15:00", "18:00")
    assert time_window.value == "15:00-18:00"
    assert time_window.is_hard is True
