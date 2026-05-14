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


from backend.agents.ranker import RankerAgent
from backend.models.schemas import ParsedConstraints


def test_ranker_agent_selects_top_candidates():
    candidates = {
        "activities": [
            {"id": "a1", "name": "Park A", "rating": 4.8, "tags": ["outdoor", "quiet"], "distance_km": 1.2, "avg_price": 0, "wait_minutes": 0},
            {"id": "a2", "name": "Museum B", "rating": 4.2, "tags": ["indoor", "art"], "distance_km": 3.5, "avg_price": 80, "wait_minutes": 15},
        ],
        "restaurants": [
            {"id": "r1", "name": "Cafe C", "rating": 4.5, "tags": ["quiet", "cafe"], "distance_km": 0.8, "avg_price": 60, "wait_minutes": 5},
        ],
        "walks": [],
    }
    constraints = ParsedConstraints(
        scenario="date",
        origin={"lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 3},
        people={"adults": 2, "children": [], "relationship": "date"},
        preferences={"activity": ["quiet", "romantic"], "budget_level": "medium"},
        constraints={"radius_km": 8, "max_wait_minutes": 15},
        required_actions=["send_plan_message"],
    )

    llm_response = {
        "ranked": {
            "activities": [{"id": "a1", "reason": "Best match for quiet date"}],
            "restaurants": [{"id": "r1", "reason": "Close and quiet"}],
            "walks": [],
        },
        "reasoning": "Prioritized quiet and close venues for a date scenario.",
    }
    llm = FakeLLM(llm_response)
    agent = RankerAgent(llm)

    result = agent.rank(candidates, constraints)

    assert "a1" in [item["id"] for item in result["activities"]]
    assert agent.last_reasoning == "Prioritized quiet and close venues for a date scenario."


def test_ranker_agent_falls_back_to_deterministic_on_llm_failure():
    candidates = {
        "activities": [
            {"id": "a1", "name": "Park A", "rating": 4.8, "tags": ["outdoor"], "distance_km": 1.2, "avg_price": 0, "wait_minutes": 0},
        ],
        "restaurants": [],
        "walks": [],
    }
    constraints = ParsedConstraints(
        scenario="family",
        origin={"lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 3},
        people={"adults": 2, "children": [{"age": 5}], "relationship": "family"},
        preferences={"activity": ["child_friendly"], "budget_level": "medium"},
        constraints={"radius_km": 8, "max_wait_minutes": 15},
        required_actions=["send_plan_message"],
    )

    class BrokenLLM:
        def chat_stream(self, messages):
            raise RuntimeError("LLM down")

    agent = RankerAgent(BrokenLLM())
    result = agent.rank(candidates, constraints)

    # Falls back to deterministic ranking — still returns candidates
    assert len(result["activities"]) == 1
    assert result["activities"][0]["id"] == "a1"
