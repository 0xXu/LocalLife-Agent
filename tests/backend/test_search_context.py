"""Tests for weather filtering and user-preference boosting in search functions."""
from __future__ import annotations

import unittest

from backend.data.catalog import LocalDataCatalog
from backend.models.schemas import ParsedConstraints
from backend.orchestrator.search import (
    _is_weather_safe,
    _preference_boost,
    search_activities,
    search_restaurants,
    search_walks,
)


def _make_constraints(scenario: str = "friends", radius_km: float = 8.0) -> ParsedConstraints:
    return ParsedConstraints(
        scenario=scenario,
        origin={"type": "current_location", "label": "home", "lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 4.5, "flexible": True},
        people={"adults": 2, "children": [], "relationship": "friends"},
        preferences={"distance": "nearby", "diet": [], "activity": ["social", "photo"], "budget_level": "medium"},
        constraints={"radius_km": radius_km, "max_wait_minutes": 15, "avoid": []},
        required_actions=["send_plan_message"],
    )


class TestIsWeatherSafe(unittest.TestCase):
    """Helper: _is_weather_safe should filter outdoor-only POIs in rain."""

    def test_none_weather_returns_true(self):
        poi = {"tags": ["outdoor", "hiking"]}
        self.assertTrue(_is_weather_safe(poi, None))

    def test_clear_weather_keeps_outdoor(self):
        poi = {"tags": ["outdoor", "hiking"]}
        weather = {"condition": "clear", "temperature": 24, "rain_probability": 0.1}
        self.assertTrue(_is_weather_safe(poi, weather))

    def test_rain_filters_outdoor_only(self):
        poi = {"tags": ["outdoor", "hiking", "nature"]}
        weather = {"condition": "rain", "temperature": 20, "rain_probability": 0.85}
        self.assertFalse(_is_weather_safe(poi, weather))

    def test_rain_keeps_indoor(self):
        poi = {"tags": ["indoor", "cafe", "quiet"]}
        weather = {"condition": "rain", "temperature": 20, "rain_probability": 0.85}
        self.assertTrue(_is_weather_safe(poi, weather))

    def test_rain_keeps_outdoor_with_rain_safe(self):
        poi = {"tags": ["outdoor", "rain_safe", "walkable"]}
        weather = {"condition": "rain", "temperature": 20, "rain_probability": 0.85}
        self.assertTrue(_is_weather_safe(poi, weather))

    def test_rain_keeps_outdoor_with_indoor(self):
        poi = {"tags": ["outdoor", "indoor"]}
        weather = {"condition": "rain", "temperature": 20, "rain_probability": 0.85}
        self.assertTrue(_is_weather_safe(poi, weather))


class TestPreferenceBoost(unittest.TestCase):
    """Helper: _preference_boost should score POI/user-preference tag overlap."""

    def test_none_preferences_returns_zero(self):
        poi = {"tags": ["indoor", "quiet"]}
        self.assertEqual(_preference_boost(poi, None), 0.0)

    def test_no_overlap_returns_zero(self):
        poi = {"tags": ["outdoor", "hiking"]}
        prefs = {"activity": ["cafe", "quiet"], "diet": []}
        self.assertEqual(_preference_boost(poi, prefs), 0.0)

    def test_activity_overlap(self):
        poi = {"tags": ["indoor", "quiet", "cafe"]}
        prefs = {"activity": ["quiet", "cafe"], "diet": []}
        self.assertEqual(_preference_boost(poi, prefs), 2.0)

    def test_diet_overlap(self):
        poi = {"tags": ["low_fat", "healthy", "booking_supported"]}
        prefs = {"activity": [], "diet": ["low_fat"]}
        self.assertEqual(_preference_boost(poi, prefs), 1.0)


class TestSearchActivitiesWithWeather(unittest.TestCase):
    """search_activities should filter outdoor POIs in rain and boost preferred ones."""

    def setUp(self):
        self.catalog = LocalDataCatalog()
        self.constraints = _make_constraints()

    def test_rain_excludes_outdoor_activities(self):
        rain = {"condition": "rain", "temperature": 20, "rain_probability": 0.85}
        items = search_activities(self.catalog, self.constraints, weather=rain)
        for poi in items:
            tags = set(poi.get("tags", []))
            if "outdoor" in tags:
                self.assertIn("indoor", tags | set(poi.get("tags", [])) | {"rain_safe"} & tags,
                              f"Outdoor POI {poi['id']} should have indoor or rain_safe in rain")

    def test_clear_weather_keeps_outdoor(self):
        clear = {"condition": "clear", "temperature": 24, "rain_probability": 0.1}
        outdoor_constraints = ParsedConstraints(
            scenario="friends",
            origin={"type": "current_location", "label": "home", "lat": 38.26, "lng": 140.88},
            time_window={"date": "today", "start": "14:00", "duration_hours": 4.5, "flexible": True},
            people={"adults": 2, "children": [], "relationship": "friends"},
            preferences={"distance": "nearby", "diet": [], "activity": ["hiking", "outdoor", "nature"], "budget_level": "medium"},
            constraints={"radius_km": 8.0, "max_wait_minutes": 15, "avoid": []},
            required_actions=["send_plan_message"],
        )
        items = search_activities(self.catalog, outdoor_constraints, weather=clear)
        has_outdoor = any("outdoor" in poi.get("tags", []) for poi in items)
        self.assertTrue(has_outdoor, "Clear weather should keep outdoor activities")

    def test_no_weather_returns_unfiltered(self):
        items_none = search_activities(self.catalog, self.constraints, weather=None)
        items_default = search_activities(self.catalog, self.constraints)
        self.assertEqual(len(items_none), len(items_default))

    def test_preference_boost_sorts_matching_first(self):
        prefs = {"activity": ["cafe", "work", "wifi"], "diet": []}
        items = search_activities(self.catalog, self.constraints, user_preferences=prefs)
        if len(items) >= 2:
            first_tags = set(items[0].get("tags", []))
            preferred = set(prefs["activity"])
            first_overlap = len(first_tags & preferred)
            last_tags = set(items[-1].get("tags", []))
            last_overlap = len(last_tags & preferred)
            self.assertGreaterEqual(first_overlap, last_overlap)


class TestSearchRestaurantsWithWeather(unittest.TestCase):
    """Restaurants should be unaffected by weather filtering (they are indoor)."""

    def setUp(self):
        self.catalog = LocalDataCatalog()
        self.constraints = _make_constraints()

    def test_rain_does_not_remove_restaurants(self):
        rain = {"condition": "rain", "temperature": 20, "rain_probability": 0.85}
        clear = {"condition": "clear", "temperature": 24, "rain_probability": 0.1}
        items_rain = search_restaurants(self.catalog, self.constraints, weather=rain)
        items_clear = search_restaurants(self.catalog, self.constraints, weather=clear)
        self.assertEqual(len(items_rain), len(items_clear),
                         "Restaurant count should be the same in rain vs clear")


class TestSearchWalksWithWeather(unittest.TestCase):
    """Walks (dessert_walk) should be filtered by weather when outdoor-only."""

    def setUp(self):
        self.catalog = LocalDataCatalog()
        self.constraints = _make_constraints()

    def test_walks_return_results(self):
        items = search_walks(self.catalog, self.constraints)
        self.assertIsInstance(items, list)

    def test_walks_with_weather(self):
        rain = {"condition": "rain", "temperature": 20, "rain_probability": 0.85}
        items = search_walks(self.catalog, self.constraints, weather=rain)
        for poi in items:
            tags = set(poi.get("tags", []))
            if "outdoor" in tags:
                self.assertTrue("indoor" in tags or "rain_safe" in tags,
                                f"Walk POI {poi['id']} is outdoor-only but it's raining")

    def test_walks_backward_compatible(self):
        items = search_walks(self.catalog, self.constraints)
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)


class TestBackwardCompatibility(unittest.TestCase):
    """All search functions must work without weather/user_preferences."""

    def test_search_activities_no_kwargs(self):
        catalog = LocalDataCatalog()
        constraints = _make_constraints()
        items = search_activities(catalog, constraints)
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)

    def test_search_restaurants_no_kwargs(self):
        catalog = LocalDataCatalog()
        constraints = _make_constraints()
        items = search_restaurants(catalog, constraints)
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)

    def test_search_walks_no_kwargs(self):
        catalog = LocalDataCatalog()
        constraints = _make_constraints()
        items = search_walks(catalog, constraints)
        self.assertIsInstance(items, list)


if __name__ == "__main__":
    unittest.main()
