import asyncio

import pytest

from app.agents.tools import FinalRouteValidator, build_route_tools
from app.domain.constraints import ConstraintEngine
from app.domain.models import PlanResponse, POI, Route, RouteSegment, UserIntent


class FakePlanningService:
    def __init__(self) -> None:
        self._constraint_engine = ConstraintEngine()

    async def plan(
        self,
        query: str,
        city: str,
        user_id: str | None,
        session_id: str | None = None,
        intent: UserIntent | None = None,
    ) -> PlanResponse:
        assert user_id is None
        assert session_id is None
        poi = POI(
            id="poi-1",
            name="Noodle shop",
            category="RESTAURANT",
            city=city,
            rating=4.8,
            avgCost=35,
        )
        route = Route(
            id="route-1",
            name="Dinner",
            segments=[RouteSegment(poi=poi)],
            totalCost=35,
        )
        return PlanResponse(routes=[route], recommendedRoute=route)


class FakeProfileService:
    async def get(self, user_id: str) -> object:
        return {
            "user_id": user_id,
            "preference_tags": {"noodles": 1.0},
            "database_url": "postgresql://unsafe:unsafe@example.test/app",
        }


def test_generate_routes_returns_typed_json_without_persistence() -> None:
    async def scenario() -> None:
        tools = build_route_tools(FakePlanningService())

        result = await tools.generate_routes("晚餐", "上海")

        assert result["routes"]
        assert result["recommendedRoute"]["id"] == "route-1"
        assert isinstance(result["routes"][0]["totalCost"], float)

    asyncio.run(scenario())


def test_profile_tool_never_returns_database_url() -> None:
    async def scenario() -> None:
        tools = build_route_tools(FakePlanningService(), FakeProfileService())

        result = await tools.get_user_profile("user-1")

        assert "database_url" not in result
        assert "postgresql://" not in str(result)

    asyncio.run(scenario())


def test_final_validator_rejects_a_route_with_a_hard_violation() -> None:
    poi = POI(
        id="poi-1",
        name="Noodle shop",
        category="RESTAURANT",
        city="上海",
        rating=4.8,
        avgCost=35,
    )
    invalid_route = Route(
        id="route-1",
        name="Dinner",
        segments=[RouteSegment(poi=poi)],
        totalCost=35,
    )
    response = PlanResponse(routes=[invalid_route], recommendedRoute=invalid_route)
    validator = FinalRouteValidator(ConstraintEngine())

    with pytest.raises(ValueError, match="hard constraint"):
        validator.finalize(
            response,
            UserIntent(query="museum", city="上海", preferredCategories=["ATTRACTION"]),
        )
