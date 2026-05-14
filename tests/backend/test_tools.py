import unittest
from backend.data.catalog import LocalDataCatalog
from backend.tools.registry import LocalToolRegistry


class TestNewToolMethods(unittest.TestCase):
    def setUp(self):
        self.catalog = LocalDataCatalog()
        self.registry = LocalToolRegistry(self.catalog)

    def test_get_poi_details_returns_full_poi(self):
        poi_id = self.catalog.pois[0]["id"]
        result = self.registry.get_poi_details(poi_id)
        self.assertEqual(result.output["id"], poi_id)
        self.assertIn("open_hours", result.output)
        self.assertIn("risk_tags", result.output)
        self.assertIn("avg_price", result.output)

    def test_get_poi_details_raises_on_missing(self):
        with self.assertRaises(KeyError):
            self.registry.get_poi_details("nonexistent_poi")

    def test_check_weather_returns_weather(self):
        result = self.registry.check_weather("today")
        self.assertIn("condition", result.output)
        self.assertIn("temperature", result.output)

    def test_check_weather_rainy(self):
        result = self.registry.check_weather("rainy")
        self.assertEqual(result.output["condition"], "rain")

    def test_check_opening_hours_returns_status(self):
        poi_id = self.catalog.pois[0]["id"]
        result = self.registry.check_opening_hours(poi_id, "14:00")
        self.assertIn("is_open", result.output)
        self.assertIn("poi_id", result.output)
        self.assertIsInstance(result.output["is_open"], bool)
        self.assertEqual(result.output["poi_id"], poi_id)
        self.assertEqual(result.output["time"], "14:00")

    def test_check_weather_default_argument(self):
        result = self.registry.check_weather()
        self.assertIn("condition", result.output)
        self.assertIn("temperature", result.output)

    def test_search_alternatives_excludes_specified_ids(self):
        all_pois = self.catalog.pois[:5]
        exclude_ids = [all_pois[0]["id"], all_pois[1]["id"]]
        category = all_pois[0]["category"]
        result = self.registry.search_alternatives(category, exclude_ids, 8, [])
        returned_ids = [p["id"] for p in result.output["items"]]
        for eid in exclude_ids:
            self.assertNotIn(eid, returned_ids)

    def test_estimate_cost_sums_avg_prices(self):
        poi = self.catalog.pois[0]
        result = self.registry.estimate_cost(poi["id"], 2)
        self.assertIn("total_cost", result.output)
        self.assertIn("per_person", result.output)
        self.assertEqual(result.output["per_person"], int(poi.get("avg_price", 100)))
        self.assertEqual(result.output["total_cost"], result.output["per_person"] * 2)
        self.assertEqual(result.output["party_size"], 2)


if __name__ == "__main__":
    unittest.main()
