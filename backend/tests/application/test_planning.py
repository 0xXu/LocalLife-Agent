import asyncio

from app.application.planning import PlanningService
from app.domain.constraints import ConstraintEngine
from app.domain.models import UserIntent
from app.domain.solver import GraphSearchSolver
from app.infrastructure.data_sources import MockDataSource


def test_planning_service_returns_hard_feasible_shanghai_routes() -> None:
    async def scenario() -> None:
        engine = ConstraintEngine()
        service = PlanningService(MockDataSource(), engine, GraphSearchSolver(engine))

        response = await service.plan(query="上海晚餐", city="上海", user_id="user-1")

        assert response.routes
        assert response.recommendedRoute == response.routes[0]
        assert response.model_dump(by_alias=True)["recommendedRoute"]
        constraints = engine.build_constraints(UserIntent(query="上海晚餐", city="上海"))
        assert all(
            not engine.validate(route, constraints).has_hard_violations
            for route in response.routes
        )

    asyncio.run(scenario())


def test_planning_service_returns_warning_when_hard_time_window_is_impossible() -> None:
    async def scenario() -> None:
        engine = ConstraintEngine()
        service = PlanningService(MockDataSource(), engine, GraphSearchSolver(engine))

        response = await service.plan(
            query="上海早晨", city="上海", user_id="user-1",
            intent=UserIntent(
                query="上海早晨", city="上海", start_time="09:00", end_time="09:00"
            ),
        )

        assert response.routes == []
        assert response.warning is not None
        assert "可行" in response.warning

    asyncio.run(scenario())
