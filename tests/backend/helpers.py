import json

from backend.llm.config import LLMConfig
from backend.models.schemas import to_dict
from backend.orchestrator.pipeline import deterministic_constraints
from backend.services.workflow_service import WorkflowService


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
        system = messages[0]["content"] if messages else ""
        lower = system.lower()

        # Ranker agent prompt
        if "ranker" in lower or "planning ranker" in lower:
            # Return no "ranked" key -> triggers deterministic fallback in RankerAgent
            yield json.dumps({"reasoning": "test: using deterministic fallback"}, ensure_ascii=False)
            return

        # Validator agent prompt
        if "validator" in lower or "plan validator" in lower:
            yield json.dumps({"valid": True, "issues": [], "suggestions": [], "overall_score": 88})
            return

        # Recovery agent prompt
        if "recovery" in lower:
            yield json.dumps({"action": "adjust", "reason": "Minor fix"})
            return

        # Default: intent parsing (existing behavior)
        goal = messages[-1]["content"] if len(messages) > 1 else ""
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


def workflow_service_with_fake_llm(repository_path=None, profile_store_path=None) -> WorkflowService:
    service = WorkflowService(
        llm_config=configured_test_llm_config(),
        repository_path=repository_path,
        profile_store_path=profile_store_path,
    )
    service.pipeline.llm = RuleBasedLLMClient()
    return service
