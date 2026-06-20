from fastapi.testclient import TestClient

from app.api.deps import build_in_memory_services
from app.main import create_app
from app.security.jwt import create_access_token


SECRET = "test-secret-that-is-longer-than-thirty-two-characters"


def _client() -> tuple[TestClient, object]:
    services = build_in_memory_services(jwt_secret=SECRET)
    return TestClient(create_app(services=services)), services


def test_public_route_endpoints_are_available_without_bearer_token() -> None:
    client, _ = _client()
    with client:
        health = client.get("/api/route/health")
        profiles = client.get("/api/route/profiles")
        pois = client.get("/api/route/pois?city=上海")

    assert health.status_code == 200
    assert health.json() == {"status": "UP", "service": "AI Route Planner"}
    assert profiles.status_code == 200
    assert isinstance(profiles.json(), list)
    assert pois.status_code == 200
    assert pois.json()[0]["avgCost"] >= 0


def test_plan_uses_jwt_subject_and_returns_a_session_id() -> None:
    client, services = _client()
    token = create_access_token("token-user", SECRET)

    with client:
        response = client.post(
            "/api/route/plan",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "上海晚餐", "city": "上海", "userId": "body-attacker"},
        )

    assert response.status_code == 200
    session_id = response.json()["sessionId"]
    assert session_id
    assert response.json()["routes"]
    assert services.sessions.items[session_id].user_id == "token-user"


def test_smart_plan_has_legacy_stage_summary_intent_and_routes_fields() -> None:
    client, _ = _client()
    token = create_access_token("user-1", SECRET)

    with client:
        response = client.post(
            "/api/route/smart-plan",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "上海晚餐", "city": "上海"},
        )

    assert response.status_code == 200
    assert {"stage", "summaryText", "intent", "routes"} <= set(response.json())
    assert response.json()["stage"] == "ready"


def test_smart_plan_returns_no_routes_when_injected_intent_analysis_requests_followup() -> None:
    class FollowupIntentAnalyzer:
        async def analyze(self, *, query: str, city: str, session_id: str | None) -> dict[str, object]:
            return {
                "stage": "followup",
                "summaryText": "还需要更多信息",
                "intent": {"query": query, "city": city},
                "followupQuestions": [{"id": "budget", "label": "预算？", "options": ["¥80"]}],
                "conflicts": [],
                "missingFields": ["budget"],
            }

    services = build_in_memory_services(jwt_secret=SECRET)
    services.intent_analyzer = FollowupIntentAnalyzer()
    client = TestClient(create_app(services=services))
    token = create_access_token("user-1", SECRET)

    with client:
        response = client.post(
            "/api/route/smart-plan",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "帮我安排", "city": "上海"},
        )

    assert response.status_code == 200
    assert response.json()["routes"] is None
    assert response.json()["followupQuestions"]
    assert response.json()["conflicts"] == []
    assert response.json()["missingFields"] == ["budget"]


def test_agent_plan_requires_jwt_and_invokes_only_the_injected_agent_runner() -> None:
    class FakeRouteAgentRunner:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        async def run(self, *, query: str, city: str, user_id: str) -> object:
            self.calls.append({"query": query, "city": city, "user_id": user_id})
            return {"status": "completed"}

    services = build_in_memory_services(jwt_secret=SECRET)
    runner = FakeRouteAgentRunner()
    services.agent_runner = runner
    client = TestClient(create_app(services=services))

    with client:
        unauthorized = client.post("/api/route/agent-plan", json={"query": "上海晚餐", "city": "上海"})
        authorized = client.post(
            "/api/route/agent-plan",
            headers={"Authorization": f"Bearer {create_access_token('token-user', SECRET)}"},
            json={"query": "上海晚餐", "city": "上海"},
        )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["routes"]
    assert runner.calls == [{"query": "上海晚餐", "city": "上海", "user_id": "token-user"}]


def test_compare_rejects_invalid_bearer_token() -> None:
    client, _ = _client()
    with client:
        response = client.get("/api/route/compare/not-a-session", headers={"Authorization": "Bearer invalid"})

    assert response.status_code == 401
