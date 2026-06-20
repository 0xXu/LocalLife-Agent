from fastapi.testclient import TestClient

from app.api.deps import build_in_memory_services
from app.main import create_app


def test_me_returns_authenticated_user_shape() -> None:
    services = build_in_memory_services(jwt_secret="x" * 32)
    app = create_app(services=services)
    client = TestClient(app)
    registration = client.post(
        "/api/auth/register",
        json={"name": "Mia", "password": "strong-password", "city": "上海"},
    )

    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {registration.json()['token']}"}
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["userId"] == registration.json()["userId"]


def test_models_exposes_openai_only_provider() -> None:
    response = TestClient(create_app()).get("/api/auth/models")

    assert response.status_code == 200
    assert response.json() == [{"id": "openai", "name": "OpenAI", "region": "global"}]
