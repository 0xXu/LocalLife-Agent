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
