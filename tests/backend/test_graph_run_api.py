import json

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.llm.config import LLMConfig
from backend.services.workflow_service import WorkflowService
from tests.backend.helpers import RuleBasedLLMClient, planning_service_with_fake_llm


def make_workflow_service(tmp_path):
    workflow = WorkflowService(
        repository_path=tmp_path / "workflow.sqlite",
        llm_config=LLMConfig(
            base_url="https://example.test/v1",
            api_key="secret",
            model="test-model",
            remote_enabled=True,
        ),
    )
    workflow.pipeline.llm = RuleBasedLLMClient()
    return workflow


def make_client(tmp_path):
    workflow = make_workflow_service(tmp_path)
    client = TestClient(create_app(workflow_service=workflow), raise_server_exceptions=False)
    return client


def parse_sse_events(body: str) -> list[dict[str, object]]:
    events = []
    for chunk in body.strip().split("\n\n"):
        event: dict[str, object] = {"data": ""}
        for line in chunk.splitlines():
            field, value = line.split(": ", 1)
            if field == "data":
                event[field] = json.loads(value)
            else:
                event[field] = value
        events.append(event)
    return events


def test_create_app_preserves_positional_planning_service_argument(tmp_path):
    planning_service = planning_service_with_fake_llm(db_path=tmp_path / "plans.sqlite")

    client = TestClient(create_app(planning_service), raise_server_exceptions=False)

    response = client.get("/api/tool-schemas")
    assert response.status_code == 200
    assert response.json()["tools"]


def test_start_run_get_plan_versions_list_and_resume(tmp_path):
    client = make_client(tmp_path)

    start = client.post("/api/plans/runs", json={"goal": "family with child wants low fat lunch", "user_id": "user_1"})
    assert start.status_code == 200
    plan_id = start.json()["plan_id"]
    assert start.json()["run_id"].startswith("run_")

    loaded = client.get(f"/api/plans/{plan_id}")
    assert loaded.status_code == 200
    payload = loaded.json()
    assert payload["plan_id"] == plan_id
    assert payload["plan"]["id"] == plan_id
    assert payload["revision"]["phase"] == "pending_approval"
    actions = payload["actions"]
    assert actions

    versions = client.get(f"/api/plans/{plan_id}/versions")
    assert versions.status_code == 200
    assert versions.json()["plan_id"] == plan_id
    assert [revision["revision_id"] for revision in versions.json()["versions"]] == [payload["revision"]["revision_id"]]

    listed = client.get("/api/plans")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["plans"][0]["id"] == plan_id
    assert listed.json()["plans"][0]["status"] == "pending_approval"
    assert listed.json()["plans"][0]["created_at"]
    assert listed.json()["plans"][0]["phase"] == "pending_approval"

    resumed = client.post(
        f"/api/plans/{plan_id}/resume",
        json={"decision": "approve", "selected_action_ids": [actions[0]["action_id"]]},
    )
    assert resumed.status_code == 200
    assert resumed.json()["revision"]["phase"] == "partially_completed"
    assert len(resumed.json()["receipts"]) == 1


def test_build_endpoint_creates_workflow_readable_plan(tmp_path):
    client = make_client(tmp_path)

    built = client.post("/api/plans/build", json={"goal": "family with child wants low fat lunch", "user_id": "user_1"})

    assert built.status_code == 200
    plan_id = built.json()["plan"]["id"]
    assert built.json()["plan_id"] == plan_id
    loaded = client.get(f"/api/plans/{plan_id}")
    assert loaded.status_code == 200
    assert loaded.json()["plan_id"] == plan_id
    assert loaded.json()["plan"]["id"] == plan_id


def test_run_stream_returns_stable_graph_update_without_creating_new_revision(tmp_path):
    client = make_client(tmp_path)
    start = client.post("/api/plans/runs", json={"goal": "family with child wants low fat lunch", "user_id": "user_1"})
    run_id = start.json()["run_id"]
    plan_id = start.json()["plan_id"]
    versions_before = client.get(f"/api/plans/{plan_id}/versions").json()["versions"]

    first = client.get(f"/api/plans/runs/{run_id}/stream")
    second = client.get(f"/api/plans/runs/{run_id}/stream")

    assert first.status_code == 200
    assert first.headers["content-type"].startswith("text/event-stream")
    first_events = parse_sse_events(first.text)
    second_events = parse_sse_events(second.text)
    assert first_events[0]["id"].startswith("evt_")
    assert first_events[0]["id"] == second_events[0]["id"]
    assert first_events[0]["event"] == "graph_update"
    assert first_events[0]["data"]["run_id"] == run_id
    assert first_events[0]["data"]["plan_id"] == plan_id
    assert client.get(f"/api/plans/{plan_id}/versions").json()["versions"] == versions_before
    assert client.get("/api/plans").json()["total"] == 1


def test_unknown_run_stream_returns_not_found(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/plans/runs/run_missing/stream")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"


def test_missing_plan_versions_returns_not_found(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/plans/plan_missing/versions")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "plan_not_found"


def test_legacy_direct_confirm_and_execute_are_disabled(tmp_path):
    client = make_client(tmp_path)

    confirm = client.post("/api/plans/plan_1/confirm", json={"confirmed": True})
    execute = client.post("/api/plans/plan_1/execute", json={"confirmed": True})

    assert confirm.status_code == 410
    assert confirm.json()["error"]["code"] == "legacy_endpoint_disabled"
    assert execute.status_code == 410
    assert execute.json()["error"]["code"] == "legacy_endpoint_disabled"
