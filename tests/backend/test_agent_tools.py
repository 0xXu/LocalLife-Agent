import unittest
from backend.agents.tools import (
    build_ranker_tools,
    build_validator_tools,
    build_recovery_tools,
    AgentContext,
)
from backend.data.catalog import LocalDataCatalog
from backend.tools.registry import LocalToolRegistry


class TestToolFactories(unittest.TestCase):
    def setUp(self):
        self.catalog = LocalDataCatalog()
        self.registry = LocalToolRegistry(self.catalog)
        self.context = AgentContext(user_id="test_user", locale="zh-CN")

    def test_ranker_tools_count(self):
        tools = build_ranker_tools(self.registry, self.context)
        self.assertEqual(len(tools), 4)
        names = {t.name for t in tools}
        self.assertEqual(names, {"search_places", "get_poi_details", "check_availability", "compare_pois"})

    def test_validator_tools_count(self):
        tools = build_validator_tools(self.registry, self.context)
        self.assertEqual(len(tools), 4)
        names = {t.name for t in tools}
        self.assertEqual(names, {"check_weather", "check_opening_hours", "check_availability", "check_route_time"})

    def test_recovery_tools_count(self):
        tools = build_recovery_tools(self.registry, self.context)
        self.assertEqual(len(tools), 4)
        names = {t.name for t in tools}
        self.assertEqual(names, {"search_alternatives", "check_availability", "compare_options", "estimate_cost"})

    def test_search_places_tool_returns_results(self):
        tools = build_ranker_tools(self.registry, self.context)
        search_fn = next(t for t in tools if t.name == "search_places")
        result = search_fn.invoke({"scenario": "family", "radius_km": 8, "tags": ["child_friendly"]})
        self.assertIn("items", result)
        self.assertIsInstance(result["items"], list)

    def test_get_poi_details_tool_returns_details(self):
        tools = build_ranker_tools(self.registry, self.context)
        details_fn = next(t for t in tools if t.name == "get_poi_details")
        poi_id = self.catalog.pois[0]["id"]
        result = details_fn.invoke({"poi_id": poi_id})
        self.assertEqual(result["id"], poi_id)

    def test_check_weather_tool_returns_weather(self):
        tools = build_validator_tools(self.registry, self.context)
        weather_fn = next(t for t in tools if t.name == "check_weather")
        result = weather_fn.invoke({"date_key": "today"})
        self.assertIn("condition", result)


if __name__ == "__main__":
    unittest.main()
