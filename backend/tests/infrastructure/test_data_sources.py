import asyncio

from app.infrastructure.data_sources import MockDataSource


def test_mock_data_source_filters_shanghai_restaurants_case_insensitively() -> None:
    async def scenario() -> None:
        source = MockDataSource()

        pois = [
            poi
            async for poi in source.search_by_category(
                city="sHaNgHaI", district=None, category="restaurant"
            )
        ]

        assert pois
        assert all(poi.city == "上海" for poi in pois)
        assert all(poi.category.upper() == "RESTAURANT" for poi in pois)

    asyncio.run(scenario())


def test_mock_data_source_honors_district_and_keyword_filters() -> None:
    async def scenario() -> None:
        source = MockDataSource()

        pois = [
            poi
            async for poi in source.search_by_keyword(
                city="上海", district="黄浦", keyword="本帮"
            )
        ]

        assert [poi.name for poi in pois] == ["黄浦本帮菜"]

    asyncio.run(scenario())
