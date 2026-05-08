import unittest

from backend.services.planning_service import PlanningService


class PlanningPipelineTest(unittest.TestCase):
    def setUp(self):
        self.service = PlanningService()

    def test_build_plan_runs_layered_pipeline_and_returns_trace(self):
        result = self.service.build_plan(
            "今天下午想和老婆孩子出去玩几个小时，孩子 5 岁，老婆减脂，别太远"
        )

        self.assertEqual(result["plan"]["status"], "ready_for_confirmation")
        self.assertEqual(result["constraints"]["people"]["children"][0]["age"], 5)
        self.assertEqual(result["constraints"]["constraints"]["radius_km"], 5)
        self.assertEqual(len(result["plan"]["itinerary"]), 3)
        self.assertGreaterEqual(len(result["trace"]), 6)
        self.assertIn("IntentParserAgent", {step["agent"] for step in result["trace"]})
        self.assertIn("PlanValidatorAgent", {step["agent"] for step in result["trace"]})

    def test_execute_plan_requires_confirmation_and_returns_receipts(self):
        result = self.service.build_plan("家庭 5 岁孩子 减脂 附近")
        plan_id = result["plan"]["id"]

        with self.assertRaises(PermissionError):
            self.service.execute_plan(plan_id, confirmed=False)

        executed = self.service.execute_plan(plan_id, confirmed=True)
        receipt_types = [receipt["type"] for receipt in executed["receipts"]]

        self.assertEqual(
            receipt_types,
            ["activity_reservation", "restaurant_reservation", "message"],
        )
        self.assertRegex(executed["receipts"][0]["id"], r"^TKT-")
        self.assertRegex(executed["receipts"][1]["id"], r"^RES-")
        self.assertRegex(executed["receipts"][2]["id"], r"^MSG-")

    def test_recover_plan_replaces_only_unavailable_restaurant(self):
        result = self.service.build_plan("家庭 5 岁孩子 减脂 附近")
        original = result["plan"]

        recovered = self.service.recover_plan(
            original["id"],
            reason="restaurant_unavailable",
        )

        self.assertEqual(recovered["plan"]["status"], "recovered_pending_confirmation")
        self.assertEqual(recovered["diff"]["changed"], "restaurant")
        self.assertEqual(
            recovered["plan"]["itinerary"][0]["place_id"],
            original["itinerary"][0]["place_id"],
        )
        self.assertNotEqual(
            recovered["plan"]["itinerary"][1]["place_id"],
            original["itinerary"][1]["place_id"],
        )


if __name__ == "__main__":
    unittest.main()

