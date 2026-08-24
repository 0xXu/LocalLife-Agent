from scripts.run_generalization_acceptance import evaluate


def test_attempted_provider_reads_count_as_selected_supply_routing() -> None:
    case = {
        "mode": "clarify_after_supply",
        "capabilities": ["dining", "experiences"],
        "verticals": [],
    }
    payload = {
        "phase": "clarifying",
        "question": {"options": [{"id": "a"}, {"id": "b"}]},
        "tool_traces": [
            {"tool": "food.search", "status": "failed"},
            {"tool": "activity.search", "status": "succeeded"},
        ],
    }

    assert evaluate(case, payload) == []


def test_case_can_accept_direct_constraint_reasoning_or_grounded() -> None:
    case = {
        "mode": "clarify_after_supply",
        "capabilities": ["experiences"],
        "capability_routes": [[], ["experiences"]],
        "verticals": [],
    }
    payload = {
        "phase": "clarifying",
        "question": {"options": [{"id": "a"}, {"id": "b"}]},
        "tool_traces": [],
    }

    assert evaluate(case, payload) == []


def test_outcome_clarification_may_ground_counterfactual_supply() -> None:
    case = {
        "mode": "clarify",
        "capabilities": [],
        "verticals": [],
    }
    payload = {
        "phase": "clarifying",
        "question": {"options": [{"id": "a"}, {"id": "b"}]},
        "tool_traces": [
            {"tool": "food.search"},
            {"tool": "activity.search"},
        ],
    }

    assert evaluate(case, payload) == []
