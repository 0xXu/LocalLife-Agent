import json

from backend.llm.config import LLMConfig
from backend.models.schemas import to_dict
from backend.orchestrator.pipeline import deterministic_constraints
from backend.services.planning_service import PlanningService


def configured_test_llm_config() -> LLMConfig:
    return LLMConfig(
        base_url="https://token-plan-sgp.xiaomimimo.com/v1",
        api_key="secret-key-value",
        model="mimo-v2.5-pro",
        remote_enabled=True,
    )


class RuleBasedLLMClient:
    def __init__(self):
        self.calls = []

    def chat_stream(self, messages):
        self.calls.append(messages)
        goal = messages[-1]["content"]
        constraints = deterministic_constraints(goal)
        normalized = goal.lower()
        if "friends" in normalized:
            constraints.scenario = "friends"
            constraints.people = {"adults": 4, "children": [], "relationship": "friends"}
            constraints.preferences["activity"] = ["social", "photo", "indoor"]
        elif "date" in normalized:
            constraints.scenario = "date"
            constraints.people = {"adults": 2, "children": [], "relationship": "date"}
            constraints.preferences["activity"] = ["quiet", "romantic"]
        elif "rain" in normalized or "indoor" in normalized:
            constraints.scenario = "rainy_indoor"
            constraints.preferences["activity"] = ["indoor", "rain_safe"]
        elif "child" in normalized or "family" in normalized:
            constraints.scenario = "family"
            constraints.people = {"adults": 2, "children": [{"age": 5}], "relationship": "family"}
            constraints.preferences["activity"] = ["child_friendly", "not_too_tiring"]
        yield json.dumps(to_dict(constraints), ensure_ascii=False)


def planning_service_with_fake_llm(db_path=None, profile_store_path=None) -> PlanningService:
    service = PlanningService(llm_config=configured_test_llm_config(), repository_path=db_path, profile_store_path=profile_store_path)
    service.pipeline.llm = RuleBasedLLMClient()
    return service
