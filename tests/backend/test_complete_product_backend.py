import json
import unittest

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.data.catalog import LocalDataCatalog
from backend.llm.config import LLMConfig
from backend.services.planning_service import PlanningService
from backend.tools.registry import LocalToolRegistry
from tests.backend.helpers import configured_test_llm_config, planning_service_with_fake_llm


class OpenDomainLLMClient:
    def __init__(self, scenario: str, label: str, activity_tags: list[str], duration_hours: float = 3, required_actions: list[str] | None = None):
        self.scenario = scenario
        self.label = label
        self.activity_tags = activity_tags
        self.duration_hours = duration_hours
        self.required_actions = required_actions or ["send_plan_message", "create_calendar_event"]

    def chat_stream(self, _messages):
        yield json.dumps(
            {
                "scenario": self.scenario,
                "origin": {"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
                "time_window": {"date": "today", "start": "14:00", "duration_hours": self.duration_hours, "flexible": True},
                "people": {"adults": 1, "children": [], "relationship": "solo"},
                "preferences": {
                    "distance": "nearby",
                    "diet": [],
                    "activity": self.activity_tags,
                    "budget_level": "medium",
                    "intent_label": self.label,
                },
                "constraints": {"radius_km": 8, "max_wait_minutes": 15, "avoid": ["long_queue"]},
                "required_actions": self.required_actions,
            },
            ensure_ascii=False,
        )


class CompleteBackendTest(unittest.TestCase):
    def setUp(self):
        self.service = planning_service_with_fake_llm()

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
            ("family", "family afternoon with a child age 5, low fat food, not too far"),
            ("friends", "friends afternoon, four adults, photo friendly, dinner after activity"),
            ("date", "date afternoon, quiet romantic places, low queue"),
            ("rainy_indoor", "rainy indoor afternoon, comfortable food nearby"),
            ("family", "family child age 5, simulate restaurant unavailable recovery later"),
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
        result = self.service.build_plan("friends afternoon, four adults, activity before dinner")
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
        result = self.service.build_plan("family afternoon with child age 5, low fat food nearby")
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

    def test_open_domain_response_exposes_frontend_contract_surface(self):
        service = PlanningService(llm_config=configured_test_llm_config())
        service.pipeline.llm = OpenDomainLLMClient("pet_friendly_walk", "宠物散步", ["pet", "outdoor", "walkable"])

        result = service.build_plan("想带狗狗找个能散步的地方，别太吵")

        self.assertEqual(result["constraints"]["scenario"], "pet_friendly_walk")
        self.assertIn("constraint_fit", result["plan"])
        self.assertIn("distance", result["plan"]["constraint_fit"])
        self.assertIn("route", result)
        self.assertGreaterEqual(result["route"]["total_travel_minutes"], 0)
        self.assertEqual(result["route"]["provider"], "local_seed_route_matrix")
        self.assertGreaterEqual(len(result["route"]["polyline"]["coordinates"]), 2)
        self.assertTrue(all("id" in variant for variant in result["plan"]["variants"]))
        self.assertTrue(all("constraint_fit" in variant for variant in result["plan"]["variants"]))
        self.assertTrue(all("id" in action for action in result["pending_actions"]))
        self.assertTrue(all("requires_confirmation" in action for action in result["pending_actions"]))

    def test_plan_response_includes_candidate_sets_and_score_breakdown(self):
        result = self.service.build_plan("想带狗狗找个安静散步的地方，别太吵")

        self.assertIn("candidate_sets", result)
        self.assertIn("activities", result["candidate_sets"])
        first = result["candidate_sets"]["activities"][0]
        self.assertIn("score_breakdown", first)
        self.assertIn("explanation", first)
        self.assertIn("provenance", first["place"])
        self.assertGreaterEqual(result["plan"]["constraint_fit"]["distance"], 0)

    def test_recover_short_open_domain_plan_without_restaurant(self):
        service = PlanningService(llm_config=configured_test_llm_config())
        service.pipeline.llm = OpenDomainLLMClient(
            "deep_work_cafe",
            "写代码自习",
            ["work", "quiet", "cafe", "wifi"],
            duration_hours=1,
            required_actions=["send_plan_message", "create_calendar_event"],
        )
        built = service.build_plan("我想找个地方写代码一小时")
        self.assertNotIn("restaurant", [step["type"] for step in built["plan"]["itinerary"]])

        recovered = service.recover_plan(built["plan"]["id"], "activity_full")

        self.assertEqual(recovered["plan"]["status"], "recovered_pending_confirmation")
        self.assertEqual(recovered["diff"]["changed"], "activity")
        self.assertNotIn("restaurant", [step["type"] for step in recovered["plan"]["itinerary"]])

    def test_patch_duration_hours_override_updates_plan_duration(self):
        result = self.service.build_plan("family afternoon with child age 5, low fat food nearby")
        plan_id = result["plan"]["id"]

        patched = self.service.patch_constraints(plan_id, {"duration_hours": 1})

        self.assertEqual(patched["constraints"]["time_window"]["duration_hours"], 1)
        self.assertEqual(patched["plan"]["overview"]["totalDuration"], "1 小时")

    def test_remote_llm_disabled_interrupts_plan_build(self):
        service = PlanningService(llm_config=LLMConfig(api_key="", base_url="", model="MiMo-V2.5-Pro"))

        with self.assertRaisesRegex(RuntimeError, "Remote LLM is required"):
            service.build_plan("friends plan")

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

    def test_itinerary_score_changes_with_candidate_quality(self):
        registry = LocalToolRegistry(LocalDataCatalog())
        constraints = self.service.pipeline.parse_constraints("friends afternoon, four adults")[0]
        high_quality = {
            "id": "high",
            "name": "High quality spot",
            "avg_price": 100,
            "rating": 4.9,
            "distance_km": 1.0,
            "wait_minutes": 3,
            "tags": ["social", "photo", "booking_supported"],
        }
        low_quality = {
            "id": "low",
            "name": "Low quality spot",
            "avg_price": 100,
            "rating": 3.8,
            "distance_km": 8.0,
            "wait_minutes": 45,
            "tags": [],
        }

        high_score = registry.build_itinerary(constraints, high_quality, high_quality, high_quality).output["score"]
        low_score = registry.build_itinerary(constraints, low_quality, low_quality, low_quality).output["score"]

        self.assertGreater(high_score, low_score)
        self.assertNotEqual(high_score, 91)


class CompleteApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(planning_service_with_fake_llm()))

    def request(self, method, path, body=None):
        response = self.client.request(method, path, json=body)
        return response.status_code, response.json()

    def test_expanded_api_flow(self):
        status, schemas = self.request("GET", "/api/tool-schemas")
        self.assertEqual(status, 200)
        self.assertEqual(len(schemas["tools"]), 15)

        status, built = self.request("POST", "/api/plans/build", {"goal": "friends afternoon, four adults, activity before dinner"})
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
