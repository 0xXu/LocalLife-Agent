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

    # FakeLLM lacks bind_tools, so ReAct graph construction fails → deterministic fallback
    assert "a1" in [item["id"] for item in result["activities"]]
    assert "fallback" in agent.last_reasoning.lower()


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


from backend.agents.validator import ValidatorAgent
from backend.models.schemas import ItineraryStep


def test_validator_agent_approves_good_plan():
    itinerary = [
        ItineraryStep("14:00", "14:15", "transport", "出发", "origin_home", "", "约 35 元", "打车 12 分钟"),
        ItineraryStep("14:15", "15:45", "activity", "Park A", "a1", "quiet outdoor", "约 0 元", "到达", 92),
        ItineraryStep("16:00", "17:00", "restaurant", "Cafe C", "r1", "good food", "约 80 元", "步行 10 分钟", 88),
    ]
    constraints_data = {"scenario": "date", "budget_level": "medium", "duration_hours": 3}
    weather = {"condition": "sunny"}

    llm_response = {"valid": True, "issues": [], "suggestions": [], "overall_score": 90}
    llm = FakeLLM(llm_response)
    agent = ValidatorAgent(llm)

    result = agent.validate(itinerary, constraints_data, weather)

    assert result["valid"] is True
    assert result["overall_score"] == 90


def test_validator_agent_rejects_bad_plan():
    itinerary = [
        ItineraryStep("14:00", "14:15", "transport", "出发", "origin_home", "", "约 35 元", "打车 12 分钟"),
        ItineraryStep("14:15", "15:45", "activity", "Outdoor Park", "a1", "outdoor", "约 0 元", "到达", 60),
    ]
    constraints_data = {"scenario": "rainy_indoor", "budget_level": "low"}
    weather = {"condition": "rain"}

    llm_response = {
        "valid": False,
        "issues": [{"code": "weather_mismatch", "detail": "Outdoor activity during rain", "severity": "blocking"}],
        "suggestions": ["Switch to indoor activity"],
        "overall_score": 35,
    }
    llm = FakeLLM(llm_response)
    agent = ValidatorAgent(llm)

    result = agent.validate(itinerary, constraints_data, weather)

    assert result["valid"] is False
    assert len(result["issues"]) == 1
    assert result["issues"][0]["code"] == "weather_mismatch"


def test_validator_agent_falls_back_to_rules_on_llm_failure():
    itinerary = [
        ItineraryStep("14:00", "14:15", "transport", "出发", "origin_home", "", "约 35 元", "打车 12 分钟"),
        ItineraryStep("14:15", "15:45", "activity", "Park A", "a1", "outdoor", "约 0 元", "到达", 92),
    ]
    constraints_data = {"scenario": "family", "budget_level": "medium", "duration_hours": 3}
    weather = {"condition": "sunny"}

    class BrokenLLM:
        def chat_stream(self, messages):
            raise RuntimeError("LLM down")

    agent = ValidatorAgent(BrokenLLM())
    result = agent.validate(itinerary, constraints_data, weather)

    # Fallback uses rule-based validation
    assert "valid" in result
    assert "issues" in result


from backend.agents.recovery import RecoveryAgent


def test_recovery_agent_decides_to_replace_restaurant():
    issues = [{"code": "closed_at_visit_time", "detail": "Restaurant closes at 15:00", "severity": "blocking"}]
    itinerary_summary = [
        {"type": "activity", "place_id": "a1", "title": "Park A"},
        {"type": "restaurant", "place_id": "r1", "title": "Closed Cafe"},
    ]
    alternatives = {
        "restaurants": [
            {"id": "r2", "name": "Open Cafe", "rating": 4.5},
            {"id": "r3", "name": "Another Cafe", "rating": 4.0},
        ]
    }

    llm_response = {
        "action": "replace",
        "target_type": "restaurant",
        "target_id": "r1",
        "replacement_id": "r2",
        "reason": "Restaurant is closed, switching to Open Cafe which is nearby and well-rated.",
    }
    llm = FakeLLM(llm_response)
    agent = RecoveryAgent(llm)

    result = agent.recover(issues, itinerary_summary, alternatives)

    assert result["action"] == "replace"
    assert result["replacement_id"] == "r2"


def test_recovery_agent_decides_plan_is_recoverable_with_minor_changes():
    issues = [{"code": "budget_overrun", "detail": "Budget too high", "severity": "warning"}]
    itinerary_summary = [{"type": "activity", "place_id": "a1", "title": "Expensive Activity"}]
    alternatives = {}

    llm_response = {
        "action": "adjust",
        "target_type": "activity",
        "target_id": "a1",
        "adjustment": "Keep activity but skip restaurant to reduce budget",
        "reason": "Budget slightly over, can be fixed by removing optional components.",
    }
    llm = FakeLLM(llm_response)
    agent = RecoveryAgent(llm)

    result = agent.recover(issues, itinerary_summary, alternatives)

    assert result["action"] == "adjust"


def test_recovery_agent_falls_back_on_llm_failure():
    issues = [{"code": "closed_at_visit_time", "severity": "blocking"}]
    itinerary_summary = [{"type": "restaurant", "place_id": "r1", "title": "Closed"}]
    alternatives = {"restaurants": [{"id": "r2", "name": "Backup"}]}

    class BrokenLLM:
        def chat_stream(self, messages):
            raise RuntimeError("LLM down")

    agent = RecoveryAgent(BrokenLLM())
    result = agent.recover(issues, itinerary_summary, alternatives)

    assert result["action"] == "replace"
    assert result["target_type"] == "restaurant"
