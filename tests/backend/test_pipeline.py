import json
import unittest

from backend.llm.config import LLMConfig
from backend.orchestrator.pipeline import PlanningPipeline, constraints_from_dict


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


class OneHourLLMClient:
    def chat_stream(self, _messages):
        yield """
        {
          "scenario": "date",
          "origin": {"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
          "time_window": {"date": "today", "start": "14:00", "duration_hours": 1, "flexible": true},
          "people": {"adults": 1, "children": [], "relationship": "solo"},
          "preferences": {"distance": "nearby", "diet": [], "activity": ["quiet"], "budget_level": "low"},
          "constraints": {"radius_km": 3, "max_wait_minutes": 10, "avoid": ["long_queue"]},
          "required_actions": ["send_plan_message"]
        }
        """


class MisclassifiedHikingLLMClient:
    def chat_stream(self, _messages):
        yield """
        {
          "scenario": "family",
          "origin": {"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
          "time_window": {"date": "today", "start": "09:00", "duration_hours": 4.5, "flexible": true},
          "people": {"adults": 3, "children": [], "relationship": "family"},
          "preferences": {"distance": "nearby", "diet": [], "activity": [], "budget_level": "medium"},
          "constraints": {"radius_km": 5, "max_wait_minutes": 15, "avoid": []},
          "required_actions": ["activity_reservation", "restaurant_reservation", "claim_coupon", "create_order", "send_plan_message", "create_calendar_event"]
        }
        """


class OpenDomainLLMClient:
    def __init__(self, scenario: str, label: str, activity_tags: list[str], goal_actions: list[str] | None = None):
        self.scenario = scenario
        self.label = label
        self.activity_tags = activity_tags
        self.goal_actions = goal_actions or ["send_plan_message", "create_calendar_event"]

    def chat_stream(self, _messages):
        yield json.dumps(
            {
                "scenario": self.scenario,
                "origin": {"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
                "time_window": {"date": "today", "start": "14:00", "duration_hours": 3, "flexible": True},
                "people": {"adults": 1, "children": [], "relationship": "solo"},
                "preferences": {
                    "distance": "nearby",
                    "diet": [],
                    "activity": self.activity_tags,
                    "budget_level": "medium",
                    "intent_label": self.label,
                },
                "constraints": {"radius_km": 8, "max_wait_minutes": 15, "avoid": ["long_queue"]},
                "required_actions": self.goal_actions,
            },
            ensure_ascii=False,
        )


class PlanningPipelineTest(unittest.TestCase):
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

    def test_pipeline_build_invokes_compiled_langgraph_workflow(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        pipeline.llm = FakeLLMClient()

        self.assertTrue(hasattr(pipeline, "graph"))
        graph_nodes = set(pipeline.graph.get_graph().nodes)
        self.assertIn("parse_intent", graph_nodes)
        self.assertIn("prepare_confirmation", graph_nodes)

        result = pipeline.build("quiet date plan")

        self.assertIn(result.status, {"pending_confirmation", "recovering"})
        self.assertEqual(result.trace[0].agent, "IntentParserAgent")
        self.assertEqual(result.trace[-1].agent, "ConfirmationAgent")

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

    def test_constraints_from_llm_accepts_open_domain_scenario(self):
        constraints = constraints_from_dict(
            {
                "scenario": "pet_friendly_walk",
                "people": {"adults": 1, "children": [], "relationship": "solo"},
                "preferences": {"activity": ["pet", "walkable"], "intent_label": "宠物散步"},
                "constraints": {"radius_km": 5, "max_wait_minutes": 15, "avoid": []},
                "time_window": {"date": "today", "start": "14:00", "duration_hours": 2, "flexible": True},
            }
        )

        self.assertEqual(constraints.scenario, "pet_friendly_walk")
        self.assertEqual(constraints.preferences["intent_label"], "宠物散步")

    def test_constraints_from_llm_normalizes_action_aliases(self):
        constraints = constraints_from_dict(
            {
                "scenario": "dining",
                "people": {"adults": 2, "children": [], "relationship": "friends"},
                "preferences": {"activity": ["restaurant"], "intent_label": "外出就餐"},
                "constraints": {"radius_km": 5, "max_wait_minutes": 15, "avoid": []},
                "time_window": {"date": "today", "start": "12:00", "duration_hours": 2, "flexible": True},
                "required_actions": ["restaurant_search", "coupon_search", "order_food", "send_plan_message"],
            }
        )

        self.assertEqual(
            constraints.required_actions,
            ["restaurant_reservation", "claim_coupon", "create_order", "send_plan_message"],
        )

    def test_overview_duration_reflects_llm_time_window(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        pipeline.llm = OneHourLLMClient()

        result = pipeline.build("quiet bookstore for one hour")

        self.assertEqual(result.overview.total_duration, "1 小时")

    def test_short_quiet_plan_omits_restaurant_walk_and_commercial_food_actions(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        pipeline.llm = OneHourLLMClient()

        result = pipeline.build("quiet bookstore for one hour")

        step_types = [step.type for step in result.itinerary]
        action_types = [action.type for action in result.pending_actions]
        self.assertEqual(step_types, ["transport", "activity"])
        self.assertNotIn("restaurant_reservation", action_types)
        self.assertNotIn("coupon", action_types)
        self.assertNotIn("order", action_types)

    def test_short_quiet_plan_title_matches_actual_itinerary(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        pipeline.llm = OneHourLLMClient()

        result = pipeline.build("quiet bookstore for one hour")
        title = result.plan_dict()["title"]

        self.assertIn("短计划", title)
        self.assertNotIn("晚餐", title)
        self.assertNotIn("半日", title)

    def test_explicit_hiking_goal_uses_outdoor_candidates_not_family_or_dessert_template(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        pipeline.llm = MisclassifiedHikingLLMClient()

        result = pipeline.build("3个人去爬山")

        self.assertEqual(result.constraints.scenario, "friends")
        self.assertEqual(result.constraints.people["adults"], 3)
        self.assertIn("hiking", result.constraints.preferences["activity"])
        self.assertLessEqual(result.constraints.time_window["duration_hours"], 3.5)
        self.assertIn("hiking", result.ranked["activities"][0]["tags"])
        self.assertNotIn("dessert_walk", [step.type for step in result.itinerary])
        self.assertNotIn("restaurant", [step.type for step in result.itinerary])
        self.assertIn("户外", result.plan_dict()["title"])

    def test_open_domain_pet_walk_generates_grounded_plan_without_enum_mapping(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        pipeline.llm = OpenDomainLLMClient("pet_friendly_walk", "宠物散步", ["pet", "outdoor", "walkable"])

        result = pipeline.build("想带狗狗找个能散步的地方，别太吵")

        self.assertEqual(result.constraints.scenario, "pet_friendly_walk")
        self.assertIn("pet", result.constraints.preferences["activity"])
        self.assertIn("pet", result.ranked["activities"][0]["tags"])
        self.assertIn("宠物", result.plan_dict()["title"])

    def test_open_domain_work_cafe_generates_grounded_plan_without_enum_mapping(self):
        pipeline = PlanningPipeline(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        pipeline.llm = OpenDomainLLMClient("deep_work_cafe", "写代码自习", ["work", "quiet", "cafe", "wifi"])

        result = pipeline.build("我想找个地方写代码三小时，顺便喝咖啡")

        self.assertEqual(result.constraints.scenario, "deep_work_cafe")
        self.assertTrue({"work", "cafe"} <= set(result.ranked["activities"][0]["tags"]))
        self.assertIn("写代码", result.plan_dict()["title"])


if __name__ == "__main__":
    unittest.main()
