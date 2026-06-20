from fastapi.testclient import TestClient
import pytest

from app.api.deps import build_in_memory_services
from app.main import create_app
from app.security.jwt import create_access_token


SECRET = "acceptance-test-secret-that-is-longer-than-thirty-two-characters"


def _client() -> TestClient:
    return TestClient(create_app(services=build_in_memory_services(jwt_secret=SECRET)))


def _plan(client: TestClient, query: str, city: str) -> object:
    token = create_access_token("competition-user", SECRET)
    return client.post(
        "/api/route/plan",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "city": city},
    )


def test_tc01_date_route_returns_route_options() -> None:
    with _client() as client:
        response = _plan(client, "今晚想在上海静安约会，人均 200，想安静一点。", "上海")

    assert response.status_code == 200
    assert response.json()["routes"]


def test_tc02_shanghai_afternoon_outing_returns_route_options() -> None:
    with _client() as client:
        response = _plan(client, "周末下午想在上海静安逛逛，顺便吃饭和喝咖啡。", "上海")

    assert response.status_code == 200
    assert response.json()["routes"]


@pytest.mark.parametrize(
    ("case_id", "query", "city"),
    [
        ("TC03", "今晚上海静安约会，人均 100 以内，不想排队。", "上海"),
        ("TC04", "今晚 9 点后想在上海静安吃饭，再找个地方坐坐。", "上海"),
        ("TC05", "北京三里屯两个人约会，预算 300。", "北京"),
        ("TC06", "上海周末亲子活动，预算 500。", "上海"),
        ("TC07", "北京下午逛街喝咖啡。", "北京"),
        ("TC08", "上海静安吃饭喝咖啡。", "上海"),
        ("TC09", "北京朋友聚会，不想排队。", "北京"),
        ("TC10", "上海一日游，预算 400。", "上海"),
        ("TC11", "北京安静看展再吃饭。", "北京"),
        ("TC12", "上海情侣约会，评分高一点。", "上海"),
        ("TC13", "北京步行路线，少走路。", "北京"),
        ("TC14", "上海晚间娱乐和晚餐。", "上海"),
        ("TC15", "北京低预算吃饭。", "北京"),
        ("TC16", "上海静安朋友聚会。", "上海"),
        ("TC17", "北京周末文化活动。", "北京"),
        ("TC18", "上海多地点路线推荐。", "上海"),
    ],
)
def test_remaining_competition_cases_return_a_valid_route(case_id: str, query: str, city: str) -> None:
    with _client() as client:
        response = _plan(client, query, city)

    assert response.status_code == 200, case_id
    assert response.json()["routes"], case_id
