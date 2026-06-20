"""Route-planning compatibility endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import ServiceContainer, get_current_user_id, get_services
from app.domain.models import AdjustRequest, AnalyzeRequest, PlanRequest, UserIntent


router = APIRouter()


def _intent(query: str, city: str) -> UserIntent:
    return UserIntent(query=query, city=city)


def _analysis_payload(request: AnalyzeRequest) -> dict[str, Any]:
    intent = _intent(request.query, request.city)
    return {
        "stage": "ready",
        "summaryText": f"已理解：{request.query}",
        "intent": intent.model_dump(by_alias=True),
        "followupQuestions": [],
        "conflicts": [],
        "missingFields": [],
    }


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP", "service": "AI Route Planner"}


@router.get("/profiles")
async def profiles(services: ServiceContainer = Depends(get_services)) -> list[dict[str, Any]]:
    return services.profiles


@router.get("/pois")
async def pois(
    city: str = Query(default="北京"),
    services: ServiceContainer = Depends(get_services),
) -> list[dict[str, Any]]:
    discovered: dict[str, dict[str, Any]] = {}
    for category in ("RESTAURANT", "ATTRACTION", "SHOPPING", "ENTERTAINMENT", "CULTURE"):
        async for poi in services.data_source.search_by_category(city, None, category):
            discovered[poi.id] = poi.model_dump(by_alias=True)
    return list(discovered.values())


@router.post("/analyze")
async def analyze(
    request: AnalyzeRequest,
    _: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return _analysis_payload(request)


@router.post("/plan")
async def plan(
    request: PlanRequest,
    user_id: str = Depends(get_current_user_id),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    response = await services.planning.plan(
        request.query, request.city, user_id, request.sessionId, request.intent
    )
    return response.model_dump(by_alias=True)


@router.post("/smart-plan")
async def smart_plan(
    request: AnalyzeRequest,
    user_id: str = Depends(get_current_user_id),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    result = _analysis_payload(request)
    response = await services.planning.plan(
        request.query, request.city, user_id, request.sessionId, _intent(request.query, request.city)
    )
    result.update(response.model_dump(by_alias=True))
    return result


@router.post("/agent-plan")
async def agent_plan(
    request: AnalyzeRequest,
    user_id: str = Depends(get_current_user_id),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    if services.agent_runner is not None:
        await services.agent_runner.run(query=request.query, city=request.city, user_id=user_id)
    response = await services.planning.plan(request.query, request.city, user_id, request.sessionId)
    return response.model_dump(by_alias=True)


@router.post("/adjust")
async def adjust(
    request: AdjustRequest,
    user_id: str = Depends(get_current_user_id),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    response = await services.planning.adjust(
        request.adjustment, request.city, user_id, request.sessionId
    )
    return response.model_dump(by_alias=True)


@router.get("/compare/{session_id}")
async def compare(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    session = await services.sessions.get(session_id, user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    routes = await services.routes_for_session(session_id, user_id)
    return {
        "sessionId": session_id,
        "routes": [route.model_dump(by_alias=True) for route in routes],
        "comparisonHtml": "路线对比结果。",
    }
