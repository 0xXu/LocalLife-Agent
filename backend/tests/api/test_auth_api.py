from fastapi.testclient import TestClient

from app.api.deps import build_in_memory_services
from app.main import create_app


def test_register_and_login_expose_legacy_auth_response() -> None:
    app = create_app(services=build_in_memory_services(jwt_secret="test-secret-that-is-longer-than-thirty-two-characters"))

    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={"name": "alice", "password": "correct horse battery staple", "city": "上海"},
        )
        login = client.post(
            "/api/auth/login",
            json={"name": "alice", "password": "correct horse battery staple"},
        )

    assert registered.status_code == 200
    assert registered.json()["success"] is True
    assert {"userId", "name", "token"} <= set(registered.json())
    assert login.status_code == 200
    assert login.json()["userId"] == registered.json()["userId"]


def test_invalid_login_returns_legacy_error_payload() -> None:
    app = create_app(services=build_in_memory_services(jwt_secret="test-secret-that-is-longer-than-thirty-two-characters"))

    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"name": "missing", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["success"] is False
    assert "error" in response.json()


def test_me_returns_legacy_profile_for_the_jwt_subject() -> None:
    secret = "test-secret-that-is-longer-than-thirty-two-characters"
    app = create_app(services=build_in_memory_services(jwt_secret=secret))

    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={"name": "alice", "password": "correct horse battery staple", "city": "上海"},
        ).json()
        response = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {registered['token']}"}
        )

    assert response.status_code == 200
    assert response.json() == {
        "success": "true",
        "userId": registered["userId"],
        "name": "alice",
        "profileName": "上海探索者",
        "preferredCity": "上海",
        "hasApiKey": "false",
    }


def test_me_keeps_legacy_unauthenticated_error_shape() -> None:
    app = create_app(services=build_in_memory_services(jwt_secret="test-secret-that-is-longer-than-thirty-two-characters"))

    with TestClient(app) as client:
        response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {"success": False, "error": "未登录"}


def test_models_exposes_only_openai_provider_models() -> None:
    app = create_app(services=build_in_memory_services(jwt_secret="test-secret-that-is-longer-than-thirty-two-characters"))

    with TestClient(app) as client:
        response = client.get("/api/auth/models")

    assert response.status_code == 200
    assert response.json()
    assert all("openai.com" in model["apiKeyUrl"] for model in response.json())
    assert not any("deepseek" in str(model).lower() for model in response.json())
