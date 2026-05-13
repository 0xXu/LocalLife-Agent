from pathlib import Path

from backend.llm.config import LLMConfig
from backend.services.workflow_service import WorkflowService
from tests.backend.helpers import RuleBasedLLMClient


def make_service(tmp_path: Path) -> WorkflowService:
    service = WorkflowService(
        repository_path=tmp_path / "workflow.sqlite",
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
    assert plan["revision"]["phase"] in {"pending_approval", "validation_failed", "needs_clarification"}


def test_clarification_run_is_not_listed_as_executable_plan(tmp_path: Path):
    service = make_service(tmp_path)

    result = service.start_run("周末安排一下")
    plan = service.get_plan(result["plan_id"])

    assert plan["revision"]["phase"] == "needs_clarification"
    assert service.list_plans() == {"plans": [], "total": 0}
