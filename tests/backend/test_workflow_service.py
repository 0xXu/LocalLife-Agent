from pathlib import Path

from backend.llm.config import LLMConfig
from backend.services.workflow_service import WorkflowService
from tests.backend.helpers import RuleBasedLLMClient


def make_service(tmp_path: Path, repository_path: Path | None = None) -> WorkflowService:
    service = WorkflowService(
        repository_path=repository_path or tmp_path / "workflow.sqlite",
        llm_config=LLMConfig(
            base_url="https://token-plan-sgp.xiaomimimo.com/v1",
            api_key="secret-key-value",
            model="mimo-v2.5-pro",
            remote_enabled=True,
        ),
    )
    service.pipeline.llm = RuleBasedLLMClient()
    return service


def _step_by_type(itinerary: list[dict], step_type: str) -> dict:
    return next(step for step in itinerary if step["type"] == step_type)


def test_start_run_creates_durable_ids_and_latest_revision(tmp_path: Path):
    service = make_service(tmp_path)

    result = service.start_run("family with child wants low fat lunch", user_id="user_1")

    assert result["run_id"].startswith("run_")
    assert result["thread_id"].startswith("thread_")
    assert result["plan_id"].startswith("plan_")

    plan = service.get_plan(result["plan_id"])

    assert plan["plan_id"] == result["plan_id"]
    assert plan["revision"]["revision_id"].startswith("rev_")
    assert plan["revision"]["phase"] == "pending_approval"
    assert plan["revision"]["validation"] == {"valid": True, "blocking": [], "warnings": []}
    assert {action["tool"] for action in plan["actions"]} >= {
        "reserve_activity",
        "create_reservation",
        "claim_coupon",
        "create_order",
    }
    for action in plan["actions"]:
        if action["tool"] in {"reserve_activity", "create_reservation", "create_order"}:
            assert action["payload"]["party_size"] == 3
    ledger_actions_by_id = {action["action_id"]: action for action in plan["actions"]}
    for persisted_action in plan["revision"]["plan"]["actions"]:
        ledger_action = ledger_actions_by_id[persisted_action["action_id"]]
        assert persisted_action["tool"] == ledger_action["tool"]
        assert persisted_action["payload"] == ledger_action["payload"]
        assert persisted_action["status"] == ledger_action["status"]
    assert {action["tool"] for action in plan["revision"]["plan"]["actions"]} == {
        "reserve_activity",
        "create_reservation",
        "claim_coupon",
        "create_order",
    }

    plan_constraints = plan["revision"]["plan"]["constraints"]
    normalized_date = plan["revision"]["constraints"]["time_window"]["date"]
    assert plan_constraints["time_window"]["date"] == normalized_date
    assert normalized_date != "today"
    assert "user_id" not in plan_constraints

    route = plan["revision"]["plan"]["route"]
    route_total = sum(leg["duration_minutes"] for leg in route["legs"])
    assert route["total_travel_minutes"] == route_total
    assert route["drive_time_minutes"] == route_total
    assert plan["revision"]["plan"]["overview"]["driveTime"] == f"约 {route_total} 分钟"

    itinerary = plan["revision"]["plan"]["itinerary"]
    restaurant = _step_by_type(itinerary, "restaurant")
    dessert = _step_by_type(itinerary, "dessert_walk")
    assert restaurant["start"] == "15:45"
    assert restaurant["end"] == "16:45"
    assert dessert["start"] == "17:00"
    assert dessert["end"] == "17:35"
    for variant in plan["revision"]["plan"]["variants"]:
        variant_restaurant = _step_by_type(variant["itinerary"], "restaurant")
        variant_dessert = _step_by_type(variant["itinerary"], "dessert_walk")
        assert variant_restaurant["start"] == restaurant["start"]
        assert variant_restaurant["end"] == restaurant["end"]
        assert variant_dessert["start"] == dessert["start"]
        assert variant_dessert["end"] == dessert["end"]

    plans = service.list_plans()
    assert plans["total"] == 1
    assert plans["plans"] == [
        {
            "id": result["plan_id"],
            "revision_id": plan["revision"]["revision_id"],
            "phase": "pending_approval",
            "title": plan["revision"]["plan"]["title"],
            "summary": plan["revision"]["plan"]["summary"],
        }
    ]


def test_clarification_run_is_not_listed_as_executable_plan(tmp_path: Path):
    service = make_service(tmp_path)

    result = service.start_run("周末安排一下")
    plan = service.get_plan(result["plan_id"])

    assert plan["revision"]["phase"] == "needs_clarification"
    assert service.list_plans() == {"plans": [], "total": 0}


def test_validation_failed_run_has_no_pending_actions_and_is_not_listed(tmp_path: Path):
    service = make_service(tmp_path)

    result = service.start_run("friends 10人 lunch", user_id="user_1")
    plan = service.get_plan(result["plan_id"])

    assert plan["revision"]["phase"] == "validation_failed"
    assert plan["revision"]["validation"]["valid"] is False
    assert plan["actions"] == []
    assert plan["revision"]["plan"]["actions"] == []
    assert service.list_plans() == {"plans": [], "total": 0}


def test_get_plan_reads_latest_revision_and_actions_after_restart(tmp_path: Path):
    repository_path = tmp_path / "workflow.sqlite"
    service = make_service(tmp_path, repository_path=repository_path)
    result = service.start_run("family with child wants low fat lunch", user_id="user_1")
    original = service.get_plan(result["plan_id"])

    restarted = WorkflowService(repository_path=repository_path)
    restored = restarted.get_plan(result["plan_id"])

    assert restored["revision"]["revision_id"] == original["revision"]["revision_id"]
    assert restored["revision"]["phase"] == "pending_approval"
    assert restored["actions"] == original["actions"]


def test_validation_failed_revision_cannot_be_approved(tmp_path: Path):
    service = make_service(tmp_path)
    result = service.start_run("friends 10人 lunch", user_id="user_1")
    plan = service.get_plan(result["plan_id"])

    assert plan["revision"]["phase"] == "validation_failed"

    try:
        service.resume(result["plan_id"], {"decision": "approve", "selected_action_ids": []})
    except ValueError as exc:
        assert str(exc) == "validation_failed"
    else:
        raise AssertionError("validation_failed revision was approved")


def test_resume_approve_executes_selected_actions_and_appends_receipts(tmp_path: Path):
    service = make_service(tmp_path)
    result = service.start_run("family with child wants low fat lunch", user_id="user_1")
    plan = service.get_plan(result["plan_id"])
    selected = [action["action_id"] for action in plan["actions"][:2]]

    resumed = service.resume(result["plan_id"], {"decision": "approve", "selected_action_ids": selected})
    loaded = service.get_plan(result["plan_id"])

    assert resumed["revision"]["phase"] == "partially_completed"
    assert loaded["revision"]["phase"] == "partially_completed"
    assert [receipt["action_id"] for receipt in loaded["receipts"]] == selected
    action_statuses = {action["action_id"]: action["status"] for action in loaded["actions"]}
    assert {action_statuses[action_id] for action_id in selected} == {"succeeded"}
    assert any(status == "pending" for action_id, status in action_statuses.items() if action_id not in selected)
    embedded_statuses = {action["action_id"]: action["status"] for action in loaded["revision"]["plan"]["actions"]}
    assert embedded_statuses == action_statuses
    assert service.list_plans()["plans"][0]["phase"] == "partially_completed"


def test_resume_approve_requires_selected_actions(tmp_path: Path):
    service = make_service(tmp_path)
    result = service.start_run("family with child wants low fat lunch", user_id="user_1")

    try:
        service.resume(result["plan_id"], {"decision": "approve", "selected_action_ids": []})
    except ValueError as exc:
        assert str(exc) == "selected_action_ids_required"
    else:
        raise AssertionError("empty approval changed workflow phase")

    loaded = service.get_plan(result["plan_id"])
    assert loaded["revision"]["phase"] == "pending_approval"
    assert loaded["receipts"] == []
    assert {action["status"] for action in loaded["actions"]} == {"pending"}


def test_resume_partial_plan_can_execute_remaining_actions(tmp_path: Path):
    service = make_service(tmp_path)
    result = service.start_run("family with child wants low fat lunch", user_id="user_1")
    plan = service.get_plan(result["plan_id"])
    first = [plan["actions"][0]["action_id"]]
    remaining = [action["action_id"] for action in plan["actions"][1:]]

    partial = service.resume(result["plan_id"], {"decision": "approve", "selected_action_ids": first})
    completed = service.resume(result["plan_id"], {"decision": "approve", "selected_action_ids": remaining})

    assert partial["revision"]["phase"] == "partially_completed"
    assert completed["revision"]["phase"] == "completed"
    assert [receipt["action_id"] for receipt in completed["receipts"]] == [*first, *remaining]
    assert {action["status"] for action in completed["actions"]} == {"succeeded"}


def test_resume_approve_completes_when_all_actions_succeed(tmp_path: Path):
    service = make_service(tmp_path)
    result = service.start_run("family with child wants low fat lunch", user_id="user_1")
    plan = service.get_plan(result["plan_id"])
    selected = [action["action_id"] for action in plan["actions"]]

    resumed = service.resume(result["plan_id"], {"decision": "approve", "selected_action_ids": selected})

    assert resumed["revision"]["phase"] == "completed"
    assert [receipt["action_id"] for receipt in resumed["receipts"]] == selected
    assert {action["status"] for action in resumed["actions"]} == {"succeeded"}


def test_completed_revision_cannot_be_approved_again(tmp_path: Path):
    service = make_service(tmp_path)
    result = service.start_run("family with child wants low fat lunch", user_id="user_1")
    plan = service.get_plan(result["plan_id"])
    selected = [action["action_id"] for action in plan["actions"]]
    service.resume(result["plan_id"], {"decision": "approve", "selected_action_ids": selected})

    try:
        service.resume(result["plan_id"], {"decision": "approve", "selected_action_ids": selected})
    except ValueError as exc:
        assert str(exc) == "completed"
    else:
        raise AssertionError("completed revision was approved again")


def test_reject_is_only_allowed_from_pending_approval(tmp_path: Path):
    service = make_service(tmp_path)
    failed = service.start_run("friends 10人 lunch", user_id="user_1")
    pending = service.start_run("family with child wants low fat lunch", user_id="user_1")
    plan = service.get_plan(pending["plan_id"])
    service.resume(pending["plan_id"], {"decision": "approve", "selected_action_ids": [plan["actions"][0]["action_id"]]})

    for plan_id, expected_phase in (
        (failed["plan_id"], "validation_failed"),
        (pending["plan_id"], "partially_completed"),
    ):
        try:
            service.resume(plan_id, {"decision": "reject"})
        except ValueError as exc:
            assert str(exc) == expected_phase
        else:
            raise AssertionError(f"{expected_phase} revision was rejected")


def test_resume_reject_cancels_without_executing_actions(tmp_path: Path):
    service = make_service(tmp_path)
    result = service.start_run("family with child wants low fat lunch", user_id="user_1")

    resumed = service.resume(result["plan_id"], {"decision": "reject"})

    assert resumed["revision"]["phase"] == "cancelled"
    assert resumed["receipts"] == []
    assert {action["status"] for action in resumed["actions"]} == {"pending"}


def test_resume_does_not_mutate_immutable_revision_snapshot(tmp_path: Path):
    service = make_service(tmp_path)
    result = service.start_run("family with child wants low fat lunch", user_id="user_1")
    plan_id = result["plan_id"]
    original = service.repository.get_latest_revision(plan_id)
    assert original is not None
    selected = [action["action_id"] for action in service.get_plan(plan_id)["actions"][:1]]

    resumed = service.resume(plan_id, {"decision": "approve", "selected_action_ids": selected})
    stored = service.repository.get_latest_revision(plan_id)

    assert resumed["revision"]["phase"] == "partially_completed"
    assert stored == original
    assert len(service.repository.list_revisions(plan_id)) == 1
    assert service.repository.get_thread_by_plan(plan_id)["status"] == "partially_completed"


def test_resume_rejects_unsupported_decisions(tmp_path: Path):
    service = make_service(tmp_path)
    result = service.start_run("family with child wants low fat lunch", user_id="user_1")

    try:
        service.resume(result["plan_id"], {"decision": "maybe"})
    except ValueError as exc:
        assert str(exc) == "unsupported_decision"
    else:
        raise AssertionError("unsupported decision was accepted")
