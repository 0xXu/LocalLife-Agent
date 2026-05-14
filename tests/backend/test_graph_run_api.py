import json

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.graph.events import sse_event
from backend.llm.config import LLMConfig
from backend.services.workflow_service import WorkflowService
from tests.backend.helpers import RuleBasedLLMClient


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
    client = TestClient(create_app(workflow), raise_server_exceptions=False)
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


def test_sse_event_serializes_sorted_unicode_raw_payload():
    assert sse_event("evt_000001", "graph_update", {"z": 1, "a": "中文"}) == (
        'id: evt_000001\nevent: graph_update\ndata: {"a":"中文","z":1}\n\n'
    )


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


def test_run_stream_returns_stable_graph_update_without_creating_new_revision(tmp_path):
    client = make_client(tmp_path)
    start = client.post("/api/plans/runs", json={"goal": "family with child wants low fat lunch", "user_id": "user_1"})
    run_id = start.json()["run_id"]
    thread_id = start.json()["thread_id"]
    plan_id = start.json()["plan_id"]
    versions_before = client.get(f"/api/plans/{plan_id}/versions").json()["versions"]
    latest_revision_before = versions_before[0]

    first = client.get(f"/api/plans/runs/{run_id}/stream")
    second = client.get(f"/api/plans/runs/{run_id}/stream")

    assert first.status_code == 200
    assert first.headers["content-type"].startswith("text/event-stream")
    assert second.status_code == 200
    assert second.headers["content-type"].startswith("text/event-stream")
    first_events = parse_sse_events(first.text)
    second_events = parse_sse_events(second.text)
    assert first_events[0]["id"] == "evt_000001"
    assert second_events[0]["id"] == "evt_000001"
    assert second_events[0] == first_events[0]
    assert first_events[0]["event"] == "graph_update"
    assert first_events[0]["data"]["run_id"] == run_id
    assert first_events[0]["data"]["thread_id"] == thread_id
    assert first_events[0]["data"]["plan_id"] == plan_id
    assert first_events[0]["data"]["revision_id"] == latest_revision_before["revision_id"]
    assert first_events[0]["data"]["phase"] == latest_revision_before["phase"]
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


def test_legacy_direct_confirm_and_execute_are_removed(tmp_path):
    client = make_client(tmp_path)

    confirm = client.post("/api/plans/plan_1/confirm", json={"confirmed": True})
    execute = client.post("/api/plans/plan_1/execute", json={"confirmed": True})

    assert confirm.status_code == 404
    assert confirm.json()["error"]["code"] == "not_found"
    assert execute.status_code == 404
    assert execute.json()["error"]["code"] == "not_found"
