from app.domain.constraints import ConstraintEngine
from app.domain.models import Constraint, UserIntent


def test_time_window_rejects_a_segment_outside_the_available_interval(sample_route) -> None:
    constraints = [Constraint.time_window("09:00", "17:00")]

    result = ConstraintEngine().validate(sample_route, constraints)

    assert result.has_hard_violations is True
    assert [constraint.id for constraint in result.hard_violations] == ["time_window"]


def test_soft_budget_reduces_score_without_rejecting_route(sample_route) -> None:
    constraints = [Constraint.budget(100)]

    result = ConstraintEngine().validate(sample_route, constraints)
    score = ConstraintEngine().score_route(sample_route, constraints)

    assert result.has_hard_violations is False
    assert 0 <= score < 100


def test_build_constraints_keeps_budget_soft_and_categories_hard() -> None:
    intent = UserIntent(
        query="晚餐",
        budget=200,
        preferred_categories=["RESTAURANT"],
        start_time="18:00",
        end_time="21:00",
    )

    constraints = ConstraintEngine().build_constraints(intent)

    assert next(c for c in constraints if c.id == "budget").is_hard is False
    assert all(c.is_hard for c in constraints if c.id in {"category", "time_window"})


def test_relaxing_can_remove_soft_budget_unless_it_is_preserved() -> None:
    constraints = [Constraint.budget(100), Constraint(id="min_rating", value=4.5, weight=2)]
    engine = ConstraintEngine()

    relaxed = engine.relax_constraints(constraints)
    budget_preserved = engine.relax_constraints(constraints, preserve_budget=True)

    assert any(all(constraint.id != "budget" for constraint in level) for level in relaxed)
    assert all(any(constraint.id == "budget" for constraint in level) for level in budget_preserved)
