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
