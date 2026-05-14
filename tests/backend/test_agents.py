from backend.models.schemas import PlanState


def test_plan_state_has_recovery_tracking():
    state = PlanState(goal="test")
    assert state.recovery_attempts == 0
    assert state.agent_decisions == {}


def test_plan_state_increment_recovery():
    state = PlanState(goal="test")
    state.recovery_attempts += 1
    assert state.recovery_attempts == 1
