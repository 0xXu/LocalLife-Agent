import time
import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.api.app import create_app
from backend.application.run_service import RunService
from backend.data.catalog import LocalDataCatalog
from backend.tools.registry import LocalToolRegistry


class CompleteBackendTest(unittest.TestCase):
    def test_local_catalog_has_full_seed_data(self):
        catalog = LocalDataCatalog()

        self.assertGreaterEqual(len(catalog.pois), 80)
        self.assertLessEqual(len(catalog.pois), 120)
        self.assertGreaterEqual(len(catalog.coupons), 20)
        self.assertGreaterEqual(len(catalog.failure_scenarios), 4)
        required = {"id", "name", "category", "lat", "lng", "source", "tags", "open_hours", "reason", "risk_tags"}
        for poi in catalog.pois:
            self.assertTrue(required.issubset(poi.keys()), poi)

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
                "get_poi_details",
                "check_weather",
                "check_opening_hours",
                "search_alternatives",
                "estimate_cost",
            },
        )
        side_effect_tools = {schema["name"] for schema in schemas if schema["side_effect"]}
        self.assertEqual(side_effect_tools, {"reserve_activity", "create_reservation", "claim_coupon", "create_order", "send_plan_message", "create_calendar_event"})


class CompleteApiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.run_service = RunService(
            database_path=f"{self._tmp.name}/workflow.sqlite",
            runtime=OpenAIAgentsRuntime(dry_run=True),
        )
        self.client = TestClient(create_app(run_service=self.run_service))

    def tearDown(self):
        self._tmp.cleanup()

    def request(self, method, path, body=None):
        response = self.client.request(method, path, json=body)
        return response.status_code, response.json()

    def wait_for_status(self, run_id, expected):
        for _ in range(20):
            response = self.client.get(f"/api/runs/{run_id}")
            response.raise_for_status()
            data = response.json()
            if data["status"] == expected:
                return data
            time.sleep(0.05)
        self.fail(f"run {run_id} did not reach {expected}")

    def test_expanded_api_flow(self):
        status, schemas = self.request("GET", "/api/tool-schemas")
        self.assertEqual(status, 200)
        self.assertEqual(len(schemas["tools"]), 20)

        status, built = self.request("POST", "/api/runs", {"goal": "friends afternoon, four adults, activity before dinner", "user_id": "user_1"})
        self.assertEqual(status, 200)
        self.wait_for_status(built["run_id"], "needs_clarification")
        status, clarification = self.request(
            "POST",
            f"/api/runs/{built['run_id']}/clarifications",
            {"question_id": "time_window", "answer": "today afternoon 2pm"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(clarification["accepted_question_id"], "time_window")
        self.wait_for_status(built["run_id"], "approval_required")
        plan_id = built["plan_id"]

        status, fetched = self.request("GET", f"/api/plans/{plan_id}")
        self.assertEqual(status, 200)
        self.assertEqual(fetched["plan_id"], plan_id)
        self.assertEqual(fetched["run_id"], built["run_id"])
        self.assertEqual(fetched["plan"]["id"], plan_id)
        self.assertEqual(fetched["status"], "approval_required")
        self.assertGreater(len(fetched["actions"]), 0)

    def test_api_errors_are_stable_json(self):
        status, data = self.request("GET", "/api/plans/missing-plan")
        self.assertEqual(status, 404)
        self.assertEqual(data["error"]["code"], "plan_not_found")

        status, data = self.request("PATCH", "/api/plans/missing-plan/constraints", {"radius_km": -1})
        self.assertEqual(status, 404)
        self.assertEqual(data["error"]["code"], "not_found")
