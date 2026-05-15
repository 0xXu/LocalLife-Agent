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


class _FakeMessage:
    """Mimics langchain AIMessage for test mocks."""
    def __init__(self, content: str):
        self.content = content
        self.tool_calls = []
        self.additional_kwargs = {}


class RuleBasedChatModel:
    """Mock chat model that returns rule-based responses via invoke()."""

    def __init__(self):
        self.calls = []

    def invoke(self, messages, **kwargs):
        self.calls.append(messages)
        system = ""
        for m in messages:
            mtype = getattr(m, "type", None)
            if mtype == "system":
                system = getattr(m, "content", "")
                break
            if isinstance(m, dict) and m.get("role") == "system":
                system = m.get("content", "")
                break
        lower = system.lower()

        # Intent parsing (default)
        goal = ""
        for m in reversed(messages):
            mtype = getattr(m, "type", None)
            if mtype == "human":
                goal = getattr(m, "content", "")
                break
            if isinstance(m, dict) and m.get("role") == "user":
                goal = m.get("content", "")
                break
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
        return _FakeMessage(json.dumps(to_dict(constraints), ensure_ascii=False))

    def bind_tools(self, tools):
        return self

    def stream(self, messages, **kwargs):
        result = self.invoke(messages, **kwargs)
        yield _FakeMessageChunk(result.content)


class _FakeMessageChunk:
    def __init__(self, content: str):
        self.content = content
        self.tool_calls = []
        self.additional_kwargs = {}


class FailingChatModel:
    """Mock chat model that always raises."""

    def invoke(self, messages, **kwargs):
        raise RuntimeError("LLM request timed out after 30 seconds.")

    def bind_tools(self, tools):
        return self


def workflow_service_with_fake_llm(repository_path=None, profile_store_path=None) -> WorkflowService:
    service = WorkflowService(
        llm_config=configured_test_llm_config(),
        repository_path=repository_path,
        profile_store_path=profile_store_path,
    )
    service.pipeline.chat_model = RuleBasedChatModel()
    return service
