import unittest

from backend.llm.config import LLMConfig
from backend.orchestrator.pipeline import PlanningPipeline, constraints_from_dict
from tests.backend.helpers import planning_service_with_fake_llm


class FakeLLMClient:
    def __init__(self):
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return {
            "choices": [
                {
                    "message": {
                        "content": """
                        ```json
                        {
                          "scenario": "date",
                          "origin": {"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
                          "time_window": {"date": "today", "start": "14:00", "duration_hours": 4.5, "flexible": true},
                          "people": {"adults": 2, "children": [], "relationship": "date"},
                          "preferences": {"distance": "nearby", "diet": [], "activity": ["quiet", "romantic"], "budget_level": "medium"},
                          "constraints": {"radius_km": 6, "max_wait_minutes": 15, "avoid": ["long_queue"]},
                          "required_actions": ["restaurant_reservation", "send_plan_message"]
                        }
                        ```
                        """
                    }
                }
            ]
        }

    def chat_stream(self, messages):
        response = self.chat(messages)
        yield response["choices"][0]["message"]["content"]


class FailingLLMClient:
    def chat_stream(self, _messages):
        raise RuntimeError("LLM request timed out after 30 seconds.")


class InvalidJsonLLMClient:
    def chat_stream(self, _messages):
        yield "not-json"


class PlanningPipelineTest(unittest.TestCase):
    def setUp(self):
        self.service = planning_service_with_fake_llm()

    def test_build_plan_runs_layered_pipeline_and_returns_trace(self):
        result = self.service.build_plan(
            "今天下午想和老婆孩子出去玩几个小时，孩子 5 岁，老婆减脂，别太远"
        )

        self.assertEqual(result["plan"]["status"], "pending_confirmation")
        self.assertEqual(result["constraints"]["people"]["children"][0]["age"], 5)
        self.assertEqual(result["constraints"]["constraints"]["radius_km"], 5)
        self.assertGreaterEqual(len(result["plan"]["itinerary"]), 4)
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
            ["activity_reservation", "restaurant_reservation", "coupon", "order", "message", "calendar"],
        )
        self.assertRegex(executed["receipts"][0]["id"], r"^TKT-")
        self.assertRegex(executed["receipts"][1]["id"], r"^RES-")
        self.assertTrue(any(receipt["id"].startswith("MSG-") for receipt in executed["receipts"]))

    def test_recover_plan_replaces_only_unavailable_restaurant(self):
        result = self.service.build_plan("家庭 5 岁孩子 减脂 附近")
        original = result["plan"]

        recovered = self.service.recover_plan(
            original["id"],
            reason="restaurant_unavailable",
        )

        self.assertEqual(recovered["plan"]["status"], "recovered_pending_confirmation")
        self.assertEqual(recovered["diff"]["changed"], "restaurant")
        original_restaurant = next(step for step in original["itinerary"] if step["type"] == "restaurant")
        recovered_restaurant = next(step for step in recovered["plan"]["itinerary"] if step["type"] == "restaurant")
        original_activity = next(step for step in original["itinerary"] if step["type"] == "activity")
        recovered_activity = next(step for step in recovered["plan"]["itinerary"] if step["type"] == "activity")

        self.assertEqual(recovered_activity["place_id"], original_activity["place_id"])
        self.assertNotEqual(recovered_restaurant["place_id"], original_restaurant["place_id"])

    def test_friends_goal_builds_friend_plan_for_four_adults(self):
        result = self.service.build_plan("今天下午朋友4个人出去玩，2男2女，别太远")

        self.assertEqual(result["constraints"]["scenario"], "friends")
        self.assertEqual(result["constraints"]["people"]["adults"], 4)
        self.assertEqual(result["constraints"]["people"]["children"], [])
        self.assertIn("朋友", result["plan"]["title"])
        self.assertNotIn("亲子", result["plan"]["title"])
        message_action = next(action for action in result["pending_actions"] if action["type"] == "message")
        self.assertEqual(message_action["target"], "朋友群聊")

    def test_multiple_builds_keep_independent_plan_state(self):
        family = self.service.build_plan("今天下午想和老婆孩子出去玩几个小时，孩子5岁，老婆减脂，别太远")
        friends = self.service.build_plan("今天下午朋友4个人出去玩，2男2女，别太远")

        self.assertNotEqual(family["plan"]["id"], friends["plan"]["id"])

        executed_family = self.service.execute_plan(family["plan"]["id"], confirmed=True)
        executed_friends = self.service.execute_plan(friends["plan"]["id"], confirmed=True)

        self.assertEqual(executed_family["constraints"]["scenario"], "family")
        self.assertEqual(executed_friends["constraints"]["scenario"], "friends")

    def test_pipeline_uses_configured_openai_compatible_llm_for_constraints(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        fake_llm = FakeLLMClient()
        pipeline.llm = fake_llm

        result = pipeline.build("下午想和对象约会，安静一点，排队少")

        self.assertEqual(result.constraints.scenario, "date")
        self.assertEqual(result.constraints.constraints["radius_km"], 6)
        self.assertEqual(len(fake_llm.calls), 1)
        intent_trace = next(step for step in result.trace if step.agent == "IntentParserAgent")
        self.assertFalse(intent_trace.output_summary["llm_fallback"])

    def test_configured_llm_failure_interrupts_build_without_template_fallback(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        pipeline.llm = FailingLLMClient()

        with self.assertRaisesRegex(RuntimeError, "LLM intent parsing failed"):
            pipeline.build("friends dinner this afternoon")

    def test_configured_llm_invalid_json_interrupts_build_without_template_fallback(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        pipeline.llm = InvalidJsonLLMClient()

        with self.assertRaisesRegex(RuntimeError, "LLM intent parsing failed"):
            pipeline.build("date plan this afternoon")

    def test_missing_or_disabled_remote_llm_interrupts_build_without_template_fallback(self):
        missing_config = PlanningPipeline(llm_config=LLMConfig(api_key="", base_url="", model="MiMo-V2.5-Pro"))
        disabled_config = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=False,
            )
        )

        with self.assertRaisesRegex(RuntimeError, "Remote LLM is required"):
            missing_config.build("family plan")
        with self.assertRaisesRegex(RuntimeError, "Remote LLM is required"):
            disabled_config.build("family plan")

    def test_constraints_from_llm_normalizes_children_count_to_list(self):
        constraints = constraints_from_dict(
            {
                "scenario": "date",
                "people": {"adults": "2", "children": 0, "relationship": "date"},
                "constraints": {"radius_km": "5", "max_wait_minutes": "15", "avoid": "long_queue"},
                "time_window": {"date": "today", "start": "14:00", "duration_hours": "4.5", "flexible": True},
            }
        )

        self.assertEqual(constraints.people["adults"], 2)
        self.assertEqual(constraints.people["children"], [])
        self.assertEqual(constraints.constraints["radius_km"], 5.0)
        self.assertEqual(constraints.constraints["max_wait_minutes"], 15)
        self.assertEqual(constraints.constraints["avoid"], ["long_queue"])


if __name__ == "__main__":
    unittest.main()
