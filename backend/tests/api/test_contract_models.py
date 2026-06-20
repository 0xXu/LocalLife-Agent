from app.domain.models import PlanResponse


def test_plan_response_preserves_legacy_response_fields() -> None:
    assert set(PlanResponse.model_fields) >= {
        "routes",
        "warning",
        "recommendedRoute",
        "explanation",
        "sessionId",
    }
