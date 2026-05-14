from backend.models.schemas import PlanState


def test_plan_state_has_recovery_tracking():
    state = PlanState(goal="test")
    assert state.recovery_attempts == 0
    assert state.agent_decisions == {}


def test_plan_state_increment_recovery():
    state = PlanState(goal="test")
    state.recovery_attempts += 1
    assert state.recovery_attempts == 1


import json
from backend.agents.base import BaseAgent


class FakeLLM:
    def __init__(self, response: dict):
        self._response = response
        self.calls = []

    def chat_stream(self, messages):
        self.calls.append(messages)
        yield json.dumps(self._response, ensure_ascii=False)


def test_base_agent_calls_llm_and_parses_json():
    llm = FakeLLM({"decision": "approve", "reason": "looks good"})
    agent = BaseAgent("TestAgent", llm)

    result = agent.run_llm("test prompt", {"key": "value"})

    assert result == {"decision": "approve", "reason": "looks good"}
    assert len(llm.calls) == 1
    assert "test prompt" in llm.calls[0][0]["content"]


def test_base_agent_returns_none_on_llm_failure():
    class BrokenLLM:
        def chat_stream(self, messages):
            raise RuntimeError("LLM down")

    agent = BaseAgent("TestAgent", BrokenLLM())
    result = agent.run_llm("test", {})

    assert result is None


def test_base_agent_build_trace():
    llm = FakeLLM({"result": "ok"})
    agent = BaseAgent("TestAgent", llm)
    agent.run_llm("test", {})
    trace = agent.build_trace("ok", "did something", {"input": 1}, {"result": "ok"})

    assert trace.agent == "TestAgent"
    assert trace.status == "ok"
    assert trace.message == "did something"
