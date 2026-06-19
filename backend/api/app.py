from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.routes.runs import router as runs_router
from backend.api.schemas.plans import PlanDetailResponse
from backend.application.approval_service import ApprovalService
from backend.application.run_service import RunService
from backend.llm import LLMConfig
from backend.profile.models import UserPreference, UserProfile
from backend.profile.store import UserProfileStore
from backend.tools.registry import LocalToolRegistry


def create_app(
    run_service: RunService | None = None,
    profile_store: UserProfileStore | None = None,
    tool_registry: LocalToolRegistry | None = None,
) -> FastAPI:
    api = FastAPI(
        title="WeekendPilot Backend",
        description="FastAPI backend for the WeekendPilot local-life planning workflow.",
        version="0.1.0",
    )
    api.state.run_service = run_service or RunService()
    api.state.approval_service = ApprovalService(api.state.run_service)
    api.state.profile_store = profile_store or UserProfileStore(".weekendpilot/profiles.sqlite")
    api.state.tool_registry = tool_registry or LocalToolRegistry()
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @api.exception_handler(PermissionError)
    async def permission_error_handler(_request: Request, exc: PermissionError) -> JSONResponse:
        return error_response(str(exc) or "confirmation_required", 403)

    @api.exception_handler(KeyError)
    async def key_error_handler(_request: Request, exc: KeyError) -> JSONResponse:
        return error_response(str(exc.args[0]) if exc.args else "plan_not_found", 404)

    @api.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        return error_response(str(exc) or "validation_error", 400)

    @api.exception_handler(RequestValidationError)
    async def request_validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        if any(error.get("type") == "json_invalid" for error in exc.errors()):
            return error_response("invalid_json", 400)
        return error_response("validation_error", 400)

    @api.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return error_response("not_found", 404)
        return error_response(str(exc.detail), exc.status_code)

    @api.exception_handler(Exception)
    async def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "tool_failed", "message": str(exc) or "Unknown error"}},
            status_code=500,
        )

    @api.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "service": "weekendpilot-planner", "mode": "fastapi-python-service", "agents": 9}

    @api.get("/api/llm/status")
    async def llm_status() -> dict[str, Any]:
        return LLMConfig.from_env_file().safe_status()

    @api.get("/api/tool-schemas")
    async def tool_schemas(request: Request) -> dict[str, Any]:
        return {"tools": request.app.state.tool_registry.schemas()}

    @api.get("/api/users/{user_id}/profile")
    async def get_user_profile(user_id: str, request: Request) -> dict[str, Any]:
        return request.app.state.profile_store.get(user_id).as_dict()

    @api.post("/api/users/{user_id}/profile")
    async def save_user_profile(user_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        profile = UserProfile(
            user_id=user_id,
            explicit_preferences=[UserPreference(**item) for item in body.get("explicit_preferences", [])],
            learned_preferences=[UserPreference(**item) for item in body.get("learned_preferences", [])],
            session_preferences=[UserPreference(**item) for item in body.get("session_preferences", [])],
        )
        request.app.state.profile_store.save(profile)
        return profile.as_dict()

    @api.get("/api/plans/{plan_id}", response_model=PlanDetailResponse)
    async def get_plan(plan_id: str, request: Request) -> PlanDetailResponse:
        return PlanDetailResponse(**request.app.state.run_service.get_plan(plan_id))

    api.include_router(runs_router)

    return api


async def read_json_object(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(data, dict):
        raise ValueError("validation_error")
    return data


def error_response(error: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": error, "message": error}}, status_code=status_code)


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("backend.api.app:app", host="127.0.0.1", port=8787)


if __name__ == "__main__":
    main()
