from app.api.deps import build_in_memory_services
from app.main import create_app


def test_required_legacy_api_routes_are_exposed() -> None:
    app = create_app(
        services=build_in_memory_services(
            jwt_secret="contract-test-secret-that-is-longer-than-thirty-two-characters"
        )
    )
    paths = set(app.openapi()["paths"])

    assert {
        "/api/auth/register",
        "/api/auth/login",
        "/api/route/health",
        "/api/route/plan",
        "/api/route/smart-plan",
        "/api/favorites",
    } <= paths
