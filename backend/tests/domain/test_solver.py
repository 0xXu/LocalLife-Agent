from app.domain.constraints import ConstraintEngine
from app.domain.models import UserIntent
from app.domain.solver import GraphSearchSolver


def test_generate_plans_returns_distinct_feasible_routes(sample_pois, sample_intent) -> None:
    constraints = ConstraintEngine().build_constraints(sample_intent)

    plans = GraphSearchSolver().generate_plans(sample_pois, constraints, sample_intent, limit=3)

    sequences = [tuple(segment.poi.id for segment in plan.segments) for plan in plans]
    assert plans
    assert len(plans) <= 3
    assert len(sequences) == len(set(sequences))
    assert all(0 <= plan.score <= 100 for plan in plans)


def test_generate_plans_returns_none_for_an_impossible_hard_time_window(sample_pois) -> None:
    intent = UserIntent(query="早晨", city="上海", start_time="09:00", end_time="09:00")
    constraints = ConstraintEngine().build_constraints(intent)

    plans = GraphSearchSolver().generate_plans(sample_pois, constraints, intent)

    assert plans == []
