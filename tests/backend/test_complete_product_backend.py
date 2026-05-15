import json
import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.data.catalog import LocalDataCatalog
from backend.llm.config import LLMConfig
from backend.services.workflow_service import WorkflowService
from backend.tools.registry import LocalToolRegistry
from tests.backend.helpers import RuleBasedChatModel, configured_test_llm_config


class _FakeMsg:
    def __init__(self, content: str):
        self.content = content
        self.tool_calls = []
        self.additional_kwargs = {}


class OpenDomainChatModel:
    def __init__(self, scenario: str, label: str, activity_tags: list[str], duration_hours: float = 3, required_actions: list[str] | None = None):
        self._intent_json = json.dumps({
            "scenario": scenario,
            "origin": {"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
            "time_window": {"date": "today", "start": "14:00", "duration_hours": duration_hours, "flexible": True},
            "people": {"adults": 1, "children": [], "relationship": "solo"},
            "preferences": {"distance": "nearby", "diet": [], "activity": activity_tags, "budget_level": "medium", "intent_label": label},
            "constraints": {"radius_km": 8, "max_wait_minutes": 15, "avoid": ["long_queue"]},
            "required_actions": required_actions or ["send_plan_message", "create_calendar_event"],
        }, ensure_ascii=False)

    def invoke(self, _messages, **kwargs):
        return _FakeMsg(self._intent_json)

    def bind_tools(self, tools):
        return self


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
        workflow = WorkflowService(
            repository_path=f"{self._tmp.name}/workflow.sqlite",
            llm_config=LLMConfig(
                base_url="https://example.test/v1",
                api_key="secret",
                model="test-model",
                remote_enabled=True,
            ),
        )
        workflow.pipeline.chat_model = RuleBasedChatModel()
        self.client = TestClient(create_app(workflow))

    def tearDown(self):
        self._tmp.cleanup()

    def request(self, method, path, body=None):
        response = self.client.request(method, path, json=body)
        return response.status_code, response.json()

    def test_expanded_api_flow(self):
        status, schemas = self.request("GET", "/api/tool-schemas")
        self.assertEqual(status, 200)
        self.assertEqual(len(schemas["tools"]), 20)

        status, built = self.request("POST", "/api/plans/runs", {"goal": "friends afternoon, four adults, activity before dinner", "user_id": "user_1"})
        self.assertEqual(status, 200)
        plan_id = built["plan_id"]

        status, fetched = self.request("GET", f"/api/plans/{plan_id}")
        self.assertEqual(status, 200)
        self.assertEqual(fetched["plan_id"], plan_id)
        self.assertEqual(fetched["plan"]["id"], plan_id)

        status, versions = self.request("GET", f"/api/plans/{plan_id}/versions")
        self.assertEqual(status, 200)
        self.assertEqual(versions["plan_id"], plan_id)
        self.assertEqual(len(versions["versions"]), 1)

    def test_api_errors_are_stable_json(self):
        status, data = self.request("GET", "/api/plans/missing-plan")
        self.assertEqual(status, 404)
        self.assertEqual(data["error"]["code"], "plan_not_found")

        status, data = self.request("PATCH", "/api/plans/missing-plan/constraints", {"radius_km": -1})
        self.assertEqual(status, 404)
        self.assertEqual(data["error"]["code"], "not_found")
