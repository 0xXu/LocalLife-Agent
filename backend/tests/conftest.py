import pytest

from app.domain.models import POI, Route, RouteSegment, UserIntent


@pytest.fixture
def sample_pois() -> list[POI]:
    return [
        POI(
            id="p1",
            name="上海餐厅",
            category="RESTAURANT",
            city="上海",
            rating=4.5,
            avg_cost=100,
        ),
        POI(
            id="p2",
            name="上海景点",
            category="ATTRACTION",
            city="上海",
            rating=4.2,
            avg_cost=0,
        ),
    ]


@pytest.fixture
def sample_intent() -> UserIntent:
    return UserIntent(query="上海晚餐", city="上海", budget=200)


@pytest.fixture
def sample_route(sample_pois: list[POI]) -> Route:
    return Route(
        id="route-1",
        name="上海晚餐路线",
        segments=[
            RouteSegment(
                poi=sample_pois[0], arrival_time="15:00", departure_time="18:00"
            )
        ],
    )
