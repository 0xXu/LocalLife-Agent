import json
import unittest

from backend.agents.memory import MemoryItem, MemoryStore
from backend.agents.ranker import RankerAgent, RANKER_SYSTEM_PROMPT
from backend.agents.recovery import RecoveryAgent, RECOVERY_SYSTEM_PROMPT
from backend.agents.tools import AgentContext, build_ranker_tools, build_recovery_tools, build_validator_tools
from backend.agents.validator import ValidatorAgent, VALIDATOR_SYSTEM_PROMPT
from backend.data.catalog import LocalDataCatalog
from backend.tools.registry import LocalToolRegistry


class FakeLLMForReact:
    """Fake LLM that returns tool_calls or final answers based on message count."""
    def __init__(self, final_answer):
        self.final_answer = final_answer
        self.call_count = 0
        self.tool_calls_made = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, **kwargs):
        self.call_count += 1
        # First call: make a tool call
        if self.call_count == 1:
            class FakeMessage:
                def __init__(self):
                    self.content = ""
                    self.tool_calls = [{"id": "call_1", "name": "search_places", "args": {"scenario": "family", "radius_km": 8, "tags": ["child_friendly"]}}]
                    self.type = "ai"
            return FakeMessage()
        # Second call: return final answer
        class FakeFinalMessage:
            def __init__(self, content):
                self.content = content
                self.tool_calls = []
                self.type = "ai"
        return FakeFinalMessage(self.final_answer)


class TestRankerAgentReact(unittest.TestCase):
    def test_ranker_has_system_prompt(self):
        self.assertIn("RankerAgent", RANKER_SYSTEM_PROMPT)
        self.assertIn("search_places", RANKER_SYSTEM_PROMPT)
        self.assertIn("JSON", RANKER_SYSTEM_PROMPT)

    def test_ranker_deterministic_fallback(self):
        catalog = LocalDataCatalog()
        registry = LocalToolRegistry(catalog)
        # Use a failing LLM
        class FailingLLM:
            def bind_tools(self, tools): return self
            def invoke(self, messages, **kwargs): raise RuntimeError("LLM failed")

        agent = RankerAgent(FailingLLM(), registry=registry)
        candidates = {"activities": catalog.pois[:3], "restaurants": [], "walks": []}
        from backend.models.schemas import ParsedConstraints
        constraints = ParsedConstraints(
            scenario="family",
            origin={"type": "current_location", "label": "home", "lat": 39.9, "lng": 116.4},
            time_window={"date": "today", "start": "14:00", "duration_hours": 3, "flexible": True},
            people={"adults": 2, "children": [], "relationship": "family"},
            preferences={"distance": "nearby", "diet": [], "activity": ["child_friendly"], "budget_level": "medium"},
            constraints={"radius_km": 8, "max_wait_minutes": 15, "avoid": []},
            required_actions=["send_plan_message"],
        )
        result = agent.rank(candidates, constraints)
        self.assertIn("activities", result)
        self.assertGreater(len(result["activities"]), 0)
        self.assertIn("fallback", agent.last_reasoning.lower())


class TestValidatorAgentReact(unittest.TestCase):
    def test_validator_has_system_prompt(self):
        self.assertIn("ValidatorAgent", VALIDATOR_SYSTEM_PROMPT)
        self.assertIn("check_weather", VALIDATOR_SYSTEM_PROMPT)

    def test_validator_fallback(self):
        catalog = LocalDataCatalog()
        registry = LocalToolRegistry(catalog)
        class FailingLLM:
            def bind_tools(self, tools): return self
            def invoke(self, messages, **kwargs): raise RuntimeError("LLM failed")

        agent = ValidatorAgent(FailingLLM(), registry=registry)
        from backend.models.schemas import ItineraryStep
        itinerary = [ItineraryStep("14:00", "15:30", "activity", "Test", "poi_001", "reason", "100元", "walk", 85)]
        result = agent.validate(itinerary, {"scenario": "family"}, {})
        self.assertIn("valid", result)


class TestRecoveryAgentReact(unittest.TestCase):
    def test_recovery_has_system_prompt(self):
        self.assertIn("RecoveryAgent", RECOVERY_SYSTEM_PROMPT)
        self.assertIn("search_alternatives", RECOVERY_SYSTEM_PROMPT)

    def test_recovery_fallback(self):
        catalog = LocalDataCatalog()
        registry = LocalToolRegistry(catalog)
        class FailingLLM:
            def bind_tools(self, tools): return self
            def invoke(self, messages, **kwargs): raise RuntimeError("LLM failed")

        agent = RecoveryAgent(FailingLLM(), registry=registry)
        issues = [{"code": "restaurant_closed", "severity": "blocking"}]
        result = agent.recover(issues, [], {"restaurants": catalog.pois[:3]})
        self.assertIn("action", result)


class TestMemoryStore(unittest.TestCase):
    def test_build_context_message(self):
        store = MemoryStore()
        store.put_preference("user_1", {"diet": "low_fat"})
        store.add_history("user_1", {"poi_id": "poi_001", "action": "selected"})
        msg = store.build_context_message("user_1")
        self.assertIn("low_fat", msg)
        self.assertIn("poi_001", msg)


if __name__ == "__main__":
    unittest.main()
