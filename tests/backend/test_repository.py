from pathlib import Path

from tests.backend.helpers import planning_service_with_fake_llm


def test_plan_survives_service_recreation(tmp_path: Path):
    db_path = tmp_path / "weekendpilot.sqlite"
    service = planning_service_with_fake_llm(db_path=db_path)
    built = service.build_plan("今天下午朋友4个人出去玩，先活动再吃饭")
    plan_id = built["plan"]["id"]

    recreated = planning_service_with_fake_llm(db_path=db_path)
    fetched = recreated.get_plan(plan_id)

    assert fetched["plan"]["id"] == plan_id
    assert fetched["plan"]["title"] == built["plan"]["title"]
