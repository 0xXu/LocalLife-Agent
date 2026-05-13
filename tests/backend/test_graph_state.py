import pytest

from backend.graph.state import (
    PHASE_APPROVED,
    PHASE_CANCELLED,
    PHASE_COMPLETED,
    PHASE_DRAFT,
    PHASE_EXECUTING,
    PHASE_NEEDS_CLARIFICATION,
    PHASE_PENDING_APPROVAL,
    PHASE_PLANNING,
    PHASE_VALIDATION_FAILED,
    WorkflowTransitionError,
    assert_transition_allowed,
    new_action_id,
    new_plan_id,
    new_revision_id,
    new_run_id,
    new_thread_id,
)


def test_allowed_workflow_transitions_cover_happy_path():
    assert_transition_allowed(PHASE_DRAFT, PHASE_PLANNING)
    assert_transition_allowed(PHASE_PLANNING, PHASE_PENDING_APPROVAL)
    assert_transition_allowed(PHASE_PENDING_APPROVAL, PHASE_APPROVED)
    assert_transition_allowed(PHASE_APPROVED, PHASE_EXECUTING)
    assert_transition_allowed(PHASE_EXECUTING, PHASE_COMPLETED)


def test_validation_failed_cannot_be_approved_or_executed():
    with pytest.raises(WorkflowTransitionError, match="validation_failed->approved"):
        assert_transition_allowed(PHASE_VALIDATION_FAILED, PHASE_APPROVED)
    with pytest.raises(WorkflowTransitionError, match="validation_failed->executing"):
        assert_transition_allowed(PHASE_VALIDATION_FAILED, PHASE_EXECUTING)


def test_completed_and_cancelled_are_terminal_for_execution():
    with pytest.raises(WorkflowTransitionError, match="completed->pending_approval"):
        assert_transition_allowed(PHASE_COMPLETED, PHASE_PENDING_APPROVAL)
    with pytest.raises(WorkflowTransitionError, match="cancelled->executing"):
        assert_transition_allowed(PHASE_CANCELLED, PHASE_EXECUTING)


def test_clarification_can_resume_planning():
    assert_transition_allowed(PHASE_DRAFT, PHASE_NEEDS_CLARIFICATION)
    assert_transition_allowed(PHASE_NEEDS_CLARIFICATION, PHASE_PLANNING)


def test_unknown_phases_fail_even_for_noop_transition():
    with pytest.raises(WorkflowTransitionError, match="unknown_phase:typo"):
        assert_transition_allowed("typo", "typo")


def test_unknown_next_phase_fails_before_transition_check():
    with pytest.raises(WorkflowTransitionError, match="unknown_phase:typo"):
        assert_transition_allowed(PHASE_DRAFT, "typo")


def test_generated_ids_have_stable_prefixes_and_are_unique():
    ids = {new_plan_id(), new_revision_id(), new_run_id(), new_thread_id(), new_action_id()}
    assert len(ids) == 5
    assert all("_" in value for value in ids)
    assert new_plan_id().startswith("plan_")
    assert new_revision_id().startswith("rev_")
    assert new_run_id().startswith("run_")
    assert new_thread_id().startswith("thread_")
    assert new_action_id().startswith("act_")
