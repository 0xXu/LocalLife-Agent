from fastapi.testclient import TestClient

from app.api.deps import build_in_memory_services
from app.main import create_app
from app.security.jwt import create_access_token


SECRET = "test-secret-that-is-longer-than-thirty-two-characters"


def test_favorites_are_scoped_to_jwt_subject_for_save_list_and_delete() -> None:
    app = create_app(services=build_in_memory_services(jwt_secret=SECRET))
    token = create_access_token("owner", SECRET)
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        saved = client.post(
            "/api/favorites",
            headers=headers,
            json={"userId": "attacker", "routeJson": "{}", "routeName": "周末路线", "poiCount": 2},
        )
        listed = client.get("/api/favorites?userId=attacker", headers=headers)
        deleted = client.delete(f"/api/favorites/{saved.json()['id']}?userId=attacker", headers=headers)

    assert saved.status_code == 200
    assert saved.json()["userId"] == "owner"
    assert listed.status_code == 200
    assert [item["userId"] for item in listed.json()] == ["owner"]
    assert deleted.status_code == 200
    assert deleted.json() == {"success": True, "id": saved.json()["id"]}
