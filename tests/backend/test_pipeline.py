import json
import unittest

from backend.llm.config import LLMConfig
from backend.orchestrator.pipeline import PlanningPipeline, constraints_from_dict


class _FakeMsg:
    def __init__(self, content: str):
        self.content = content
        self.tool_calls = []
        self.additional_kwargs = {}


def _agent_dispatch(messages, intent_json: str) -> str:
    """Dispatch based on agent system prompt content. Returns a JSON string."""
    system = ""
    for m in messages:
        role = getattr(m, "type", "") or (m.get("role", "") if isinstance(m, dict) else "")
        if role in ("system",):
            system = getattr(m, "content", "") or (m.get("content", "") if isinstance(m, dict) else "")
            break
    lower = system.lower()
    if "ranker" in lower or "planning ranker" in lower:
        return json.dumps({"reasoning": "test: using deterministic fallback"})
    if "validator" in lower or "plan validator" in lower:
        return json.dumps({"valid": True, "issues": [], "suggestions": [], "overall_score": 90})
    if "recovery" in lower:
        return json.dumps({"action": "adjust", "reason": "No blocking issues, minor adjustments only."})
    return intent_json


class FakeChatModel:
    def __init__(self, intent_json: str | None = None):
        self.calls = []
        self._intent_json = intent_json or json.dumps({
            "scenario": "date",
            "origin": {"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
            "time_window": {"date": "today", "start": "14:00", "duration_hours": 4.5, "flexible": True},
            "people": {"adults": 2, "children": [], "relationship": "date"},
            "preferences": {"distance": "nearby", "diet": [], "activity": ["quiet", "romantic"], "budget_level": "medium"},
            "constraints": {"radius_km": 6, "max_wait_minutes": 15, "avoid": ["long_queue"]},
            "required_actions": ["restaurant_reservation", "send_plan_message"],
        }, ensure_ascii=False)

    def invoke(self, messages, **kwargs):
        self.calls.append(messages)
        content = _agent_dispatch(messages, self._intent_json)
        return _FakeMsg(content)

    def bind_tools(self, tools):
        return self


class FailingChatModel:
    def invoke(self, messages, **kwargs):
        raise RuntimeError("LLM request timed out after 30 seconds.")

    def bind_tools(self, tools):
        return self


class InvalidJsonChatModel:
    def invoke(self, messages, **kwargs):
        return _FakeMsg("not-json")

    def bind_tools(self, tools):
        return self


class OneHourChatModel:
    _intent_json = json.dumps({
        "scenario": "date",
        "origin": {"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
        "time_window": {"date": "today", "start": "14:00", "duration_hours": 1, "flexible": True},
        "people": {"adults": 1, "children": [], "relationship": "solo"},
        "preferences": {"distance": "nearby", "diet": [], "activity": ["quiet"], "budget_level": "low"},
        "constraints": {"radius_km": 3, "max_wait_minutes": 10, "avoid": ["long_queue"]},
        "required_actions": ["send_plan_message"],
    }, ensure_ascii=False)

    def invoke(self, messages, **kwargs):
        return _FakeMsg(_agent_dispatch(messages, self._intent_json))

    def bind_tools(self, tools):
        return self


class MisclassifiedHikingChatModel:
    _intent_json = json.dumps({
        "scenario": "family",
        "origin": {"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
        "time_window": {"date": "today", "start": "09:00", "duration_hours": 4.5, "flexible": True},
        "people": {"adults": 3, "children": [], "relationship": "family"},
        "preferences": {"distance": "nearby", "diet": [], "activity": [], "budget_level": "medium"},
        "constraints": {"radius_km": 5, "max_wait_minutes": 15, "avoid": []},
        "required_actions": ["activity_reservation", "restaurant_reservation", "claim_coupon", "create_order", "send_plan_message", "create_calendar_event"],
    }, ensure_ascii=False)

    def invoke(self, messages, **kwargs):
        return _FakeMsg(_agent_dispatch(messages, self._intent_json))

    def bind_tools(self, tools):
        return self


class OpenDomainChatModel:
    def __init__(self, scenario: str, label: str, activity_tags: list[str], goal_actions: list[str] | None = None):
        self._intent_json = json.dumps({
            "scenario": scenario,
            "origin": {"type": "current_location", "label": "home", "lat": 38.2601, "lng": 140.8824},
            "time_window": {"date": "today", "start": "14:00", "duration_hours": 3, "flexible": True},
            "people": {"adults": 1, "children": [], "relationship": "solo"},
            "preferences": {"distance": "nearby", "diet": [], "activity": activity_tags, "budget_level": "medium", "intent_label": label},
            "constraints": {"radius_km": 8, "max_wait_minutes": 15, "avoid": ["long_queue"]},
            "required_actions": goal_actions or ["send_plan_message", "create_calendar_event"],
        }, ensure_ascii=False)

    def invoke(self, messages, **kwargs):
        return _FakeMsg(_agent_dispatch(messages, self._intent_json))

    def bind_tools(self, tools):
        return self


def _make_pipeline(mock_model):
    pipeline = PlanningPipeline(
        llm_config=LLMConfig(
            base_url="https://token-plan-sgp.xiaomimimo.com/v1",
            api_key="secret-key-value",
            model="MiMo-V2.5-Pro",
            remote_enabled=True,
        )
    )
    pipeline.chat_model = mock_model
    return pipeline


class PlanningPipelineTest(unittest.TestCase):
    def test_pipeline_uses_configured_openai_compatible_llm_for_constraints(self):
        fake_model = FakeChatModel()
        pipeline = _make_pipeline(fake_model)

        result = pipeline.build("下午想和对象约会，安静一点，排队少")

        self.assertEqual(result.constraints.scenario, "date")
        self.assertEqual(result.constraints.constraints["radius_km"], 6)
        self.assertEqual(len(fake_model.calls), 1)

    def test_pipeline_build_invokes_compiled_langgraph_workflow(self):
        pipeline = _make_pipeline(FakeChatModel())

        self.assertTrue(hasattr(pipeline, "graph"))
        graph_nodes = set(pipeline.graph.get_graph().nodes)
        self.assertIn("parse_intent", graph_nodes)
        self.assertIn("prepare_confirmation", graph_nodes)

        result = pipeline.build("quiet date plan")

        self.assertIn(result.status, {"pending_confirmation", "recovering"})
        self.assertEqual(result.trace[0].agent, "IntentParserAgent")
        self.assertEqual(result.trace[-1].agent, "ConfirmationAgent")

    def test_configured_llm_failure_interrupts_build_without_template_fallback(self):
        pipeline = _make_pipeline(FailingChatModel())

        with self.assertRaisesRegex(RuntimeError, "LLM intent parsing failed"):
            pipeline.build("friends dinner this afternoon")

    def test_configured_llm_invalid_json_interrupts_build_without_template_fallback(self):
        pipeline = _make_pipeline(InvalidJsonChatModel())

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
        pipeline = _make_pipeline(OneHourChatModel())

        result = pipeline.build("quiet bookstore for one hour")

        self.assertEqual(result.overview.total_duration, "1 小时")

    def test_short_quiet_plan_omits_restaurant_walk_and_commercial_food_actions(self):
        pipeline = _make_pipeline(OneHourChatModel())

        result = pipeline.build("quiet bookstore for one hour")

        step_types = [step.type for step in result.itinerary]
        action_types = [action.type for action in result.pending_actions]
        self.assertEqual(step_types, ["transport", "activity"])
        self.assertNotIn("restaurant_reservation", action_types)
        self.assertNotIn("coupon", action_types)
        self.assertNotIn("order", action_types)

    def test_short_quiet_plan_title_matches_actual_itinerary(self):
        pipeline = _make_pipeline(OneHourChatModel())

        result = pipeline.build("quiet bookstore for one hour")
        title = result.plan_dict()["title"]

        self.assertIn("短计划", title)
        self.assertNotIn("晚餐", title)
        self.assertNotIn("半日", title)

    def test_explicit_hiking_goal_uses_outdoor_candidates_not_family_or_dessert_template(self):
        pipeline = _make_pipeline(MisclassifiedHikingChatModel())

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
        pipeline = _make_pipeline(OpenDomainChatModel("pet_friendly_walk", "宠物散步", ["pet", "outdoor", "walkable"]))

        result = pipeline.build("想带狗狗找个能散步的地方，别太吵")

        self.assertEqual(result.constraints.scenario, "pet_friendly_walk")
        self.assertIn("pet", result.constraints.preferences["activity"])
        self.assertIn("pet", result.ranked["activities"][0]["tags"])
        self.assertIn("宠物", result.plan_dict()["title"])

    def test_open_domain_work_cafe_generates_grounded_plan_without_enum_mapping(self):
        pipeline = _make_pipeline(OpenDomainChatModel("deep_work_cafe", "写代码自习", ["work", "quiet", "cafe", "wifi"]))

        result = pipeline.build("我想找个地方写代码三小时，顺便喝咖啡")

        self.assertEqual(result.constraints.scenario, "deep_work_cafe")
        self.assertTrue({"work", "cafe"} <= set(result.ranked["activities"][0]["tags"]))
        self.assertIn("写代码", result.plan_dict()["title"])


if __name__ == "__main__":
    unittest.main()
