import unittest

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.data.catalog import LocalDataCatalog
from backend.llm.config import LLMConfig
from backend.services.planning_service import PlanningService
from backend.tools.registry import LocalToolRegistry


class CompleteBackendTest(unittest.TestCase):
    def setUp(self):
        self.service = PlanningService(llm_config=LLMConfig(api_key="", base_url="", model="MiMo-V2.5-Pro"))

    def test_local_catalog_has_full_seed_data(self):
        catalog = LocalDataCatalog()

        self.assertGreaterEqual(len(catalog.pois), 80)
        self.assertLessEqual(len(catalog.pois), 120)
        self.assertGreaterEqual(len(catalog.coupons), 20)
        self.assertGreaterEqual(len(catalog.failure_scenarios), 4)
        required = {"id", "name", "category", "lat", "lng", "source", "tags", "open_hours", "reason", "risk_tags"}
        for poi in catalog.pois:
            self.assertTrue(required.issubset(poi.keys()), poi)

    def test_builds_five_core_scenarios_with_variants_and_pending_actions(self):
        cases = [
            ("family", "今天下午想和老婆孩子出去玩几个小时，孩子5岁，老婆减脂，别太远"),
            ("friends", "今天下午朋友4个人出去玩，2男2女，先活动再吃饭，想拍照聊天，预算适中"),
            ("date", "下午想和对象约会，安静一点，有氛围，排队少，饭前饭后都顺"),
            ("rainy_indoor", "今天下雨，想安排室内活动，别太累，附近吃点健康的"),
            ("family", "孩子5岁，老婆减脂，先帮我安排，顺便模拟餐厅无位后的恢复"),
        ]

        for expected_scenario, goal in cases:
            result = self.service.build_plan(goal)
            self.assertEqual(result["constraints"]["scenario"], expected_scenario)
            self.assertEqual(result["plan"]["status"], "pending_confirmation")
            self.assertGreaterEqual(len(result["plan"]["variants"]), 3)
            self.assertGreaterEqual(len(result["pending_actions"]), 5)
            self.assertTrue(all(action["requiresConfirmation"] for action in result["pending_actions"]))
            self.assertGreaterEqual(len(result["trace"]), 7)

    def test_confirmation_gate_and_full_receipts(self):
        result = self.service.build_plan("今天下午朋友4个人出去玩，2男2女，先活动再吃饭，预算适中")
        plan_id = result["plan"]["id"]

        with self.assertRaises(PermissionError):
            self.service.execute_plan(plan_id, confirmed=False)

        confirmed = self.service.confirm_plan(plan_id, confirmed=True)
        self.assertEqual(confirmed["plan"]["status"], "confirmed")

        executed = self.service.execute_plan(plan_id, confirmed=True)
        receipt_ids = {receipt["id"] for receipt in executed["receipts"]}
        self.assertTrue(any(item.startswith("TKT-") for item in receipt_ids))
        self.assertTrue(any(item.startswith("RES-") for item in receipt_ids))
        self.assertTrue(any(item.startswith("CPN-") for item in receipt_ids))
        self.assertTrue(any(item.startswith("ORD-") for item in receipt_ids))
        self.assertTrue(any(item.startswith("MSG-") for item in receipt_ids))
        self.assertTrue(any(item.startswith("CAL-") for item in receipt_ids))
        self.assertEqual(executed["plan"]["status"], "completed")

    def test_patch_constraints_alternatives_checkpoint_and_recovery(self):
        result = self.service.build_plan("今天下午想和老婆孩子出去玩几个小时，孩子5岁，老婆减脂，别太远")
        plan_id = result["plan"]["id"]

        patched = self.service.patch_constraints(plan_id, {"radius_km": 3, "budget_level": "low"})
        self.assertEqual(patched["constraints"]["constraints"]["radius_km"], 3)
        self.assertEqual(patched["constraints"]["preferences"]["budget_level"], "low")

        alternatives = self.service.build_alternatives(plan_id)
        self.assertEqual({item["kind"] for item in alternatives["alternatives"]}, {"main", "budget", "comfort", "child_first"})

        checkpoint = self.service.get_plan(plan_id)
        self.assertEqual(checkpoint["checkpoint"]["plan_id"], plan_id)
        self.assertGreaterEqual(len(checkpoint["checkpoint"]["trace"]), 1)

        recovered = self.service.recover_plan(plan_id, "restaurant_unavailable")
        self.assertEqual(recovered["plan"]["status"], "recovered_pending_confirmation")
        self.assertEqual(recovered["diff"]["changed"], "restaurant")
        self.assertIn("重新确认", recovered["adjustment"]["primaryAction"])

    def test_llm_fallback_is_traced_when_remote_disabled(self):
        service = PlanningService(llm_config=LLMConfig(api_key="", base_url="", model="MiMo-V2.5-Pro"))
        result = service.build_plan("今天下午朋友4个人出去玩，2男2女，别太远")

        intent_trace = next(step for step in result["trace"] if step["agent"] == "IntentParserAgent")
        self.assertTrue(intent_trace["output_summary"]["llm_fallback"])

    def test_tool_schemas_cover_all_mcp_ready_tools(self):
        schemas = LocalToolRegistry(LocalDataCatalog()).schemas()
        names = {schema["name"] for schema in schemas}

        self.assertEqual(
            names,
            {
                "parse_user_goal",
                "get_weather",
                "search_places",
                "search_restaurants",
                "check_availability",
                "optimize_route",
                "build_itinerary",
                "validate_plan",
                "compare_alternatives",
                "reserve_activity",
                "create_reservation",
                "claim_coupon",
                "create_order",
                "send_plan_message",
                "create_calendar_event",
            },
        )
        side_effect_tools = {schema["name"] for schema in schemas if schema["side_effect"]}
        self.assertEqual(side_effect_tools, {"reserve_activity", "create_reservation", "claim_coupon", "create_order", "send_plan_message", "create_calendar_event"})


class CompleteApiTest(unittest.TestCase):
    def setUp(self):
        service = PlanningService(llm_config=LLMConfig(api_key="", base_url="", model="MiMo-V2.5-Pro"))
        self.client = TestClient(create_app(service))

    def request(self, method, path, body=None):
        response = self.client.request(method, path, json=body)
        return response.status_code, response.json()

    def test_expanded_api_flow(self):
        status, schemas = self.request("GET", "/api/tool-schemas")
        self.assertEqual(status, 200)
        self.assertEqual(len(schemas["tools"]), 15)

        status, built = self.request("POST", "/api/plans/build", {"goal": "今天下午朋友4个人出去玩，2男2女，别太远"})
        self.assertEqual(status, 200)
        plan_id = built["plan"]["id"]

        status, fetched = self.request("GET", f"/api/plans/{plan_id}")
        self.assertEqual(status, 200)
        self.assertEqual(fetched["plan"]["id"], plan_id)

        status, patched = self.request("PATCH", f"/api/plans/{plan_id}/constraints", {"radius_km": 3})
        self.assertEqual(status, 200)
        self.assertEqual(patched["constraints"]["constraints"]["radius_km"], 3)

        status, alternatives = self.request("POST", f"/api/plans/{plan_id}/alternatives", {})
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(alternatives["variants"]), 3)
        self.assertGreaterEqual(len(alternatives["alternatives"]), 3)

        status, rejected = self.request("POST", f"/api/plans/{plan_id}/execute", {"confirmed": False})
        self.assertEqual(status, 403)
        self.assertEqual(rejected["error"]["code"], "confirmation_required")

        status, confirmed = self.request("POST", f"/api/plans/{plan_id}/confirm", {"confirmed": True})
        self.assertEqual(status, 200)
        self.assertEqual(confirmed["plan"]["status"], "confirmed")

        status, executed = self.request("POST", f"/api/plans/{plan_id}/execute", {"confirmed": True})
        self.assertEqual(status, 200)
        self.assertEqual(executed["plan"]["status"], "completed")

    def test_api_errors_are_stable_json(self):
        status, data = self.request("GET", "/api/plans/missing-plan")
        self.assertEqual(status, 404)
        self.assertEqual(data["error"]["code"], "plan_not_found")

        status, data = self.request("PATCH", "/api/plans/missing-plan/constraints", {"radius_km": -1})
        self.assertEqual(status, 404)
        self.assertEqual(data["error"]["code"], "plan_not_found")
