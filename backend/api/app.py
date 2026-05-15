from __future__ import annotations

import asyncio
import json
from json import JSONDecodeError
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.graph.events import sse_event
from backend.llm import LLMConfig
from backend.profile.models import UserPreference, UserProfile
from backend.services import WorkflowService


def create_app(workflow_service: WorkflowService | None = None) -> FastAPI:
    api = FastAPI(
        title="WeekendPilot Backend",
        description="FastAPI backend for the WeekendPilot local-life planning workflow.",
        version="0.1.0",
    )
    api.state.workflow_service = workflow_service or WorkflowService()
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
        return workflow(request).tool_schemas()

    @api.get("/api/users/{user_id}/profile")
    async def get_user_profile(user_id: str, request: Request) -> dict[str, Any]:
        return workflow(request).get_user_profile(user_id)

    @api.post("/api/users/{user_id}/profile")
    async def save_user_profile(user_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        profile = UserProfile(
            user_id=user_id,
            explicit_preferences=[UserPreference(**item) for item in body.get("explicit_preferences", [])],
            learned_preferences=[UserPreference(**item) for item in body.get("learned_preferences", [])],
            session_preferences=[UserPreference(**item) for item in body.get("session_preferences", [])],
        )
        return workflow(request).save_user_profile(profile)

    @api.get("/api/plans")
    async def list_plans(request: Request) -> dict[str, Any]:
        listed = workflow(request).list_plans()
        return {
            "plans": [_workflow_summary(summary) for summary in listed["plans"]],
            "total": listed["total"],
        }

    @api.post("/api/plans/runs")
    async def start_plan_run(request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        goal = str(body.get("goal", ""))
        user_id = str(body.get("user_id", "local_demo_user"))
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: workflow(request).start_run(goal, user_id=user_id),
        )

    @api.get("/api/plans/runs/{run_id}/stream")
    async def stream_plan_run(run_id: str, request: Request) -> StreamingResponse:
        svc = workflow(request)

        # Try queue-based streaming first (real-time progress events).
        # Fall back to DB-based events if the queue doesn't exist (e.g. old
        # runs that completed before the queue infra was added, or queue was
        # already consumed and removed).
        from backend.graph.events import has_run_queue

        if has_run_queue(run_id):
            return StreamingResponse(
                svc.iter_run_events(run_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        # Fallback: DB-based events (backward compat)
        events = svc.stream_run_events(run_id)

        async def event_stream():
            for event in events:
                yield sse_event(str(event["id"]), str(event["event"]), event["data"])

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @api.get("/api/plans/{plan_id}/versions")
    async def plan_versions(plan_id: str, request: Request) -> dict[str, Any]:
        workflow(request).get_plan(plan_id)
        return {"plan_id": plan_id, "versions": workflow(request).repository.list_revisions(plan_id)}

    @api.post("/api/plans/{plan_id}/resume")
    async def resume_plan(plan_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        return workflow_plan_payload(workflow(request).resume(plan_id, body))

    @api.get("/api/plans/{plan_id}")
    async def get_plan(plan_id: str, request: Request) -> dict[str, Any]:
        return workflow_plan_payload(workflow(request).get_plan(plan_id))

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


def workflow(request: Request) -> WorkflowService:
    return request.app.state.workflow_service


def workflow_plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    revision = dict(payload["revision"])
    plan = dict(revision.get("plan", {}))
    plan_id = str(payload["plan_id"])
    phase = str(revision.get("phase", plan.get("status", "")))
    plan["id"] = plan_id
    plan["status"] = phase
    revision["plan"] = plan
    return {
        **payload,
        "revision": revision,
        "plan": plan,
        "pending_actions": payload.get("actions", []),
    }


def _workflow_summary(summary: dict[str, Any]) -> dict[str, Any]:
    phase = str(summary.get("phase", ""))
    timestamp = str(summary.get("created_at", ""))
    return {
        **summary,
        "status": phase,
        "created_at": timestamp,
        "updated_at": str(summary.get("updated_at", timestamp)),
        "tags": summary.get("tags", ["本地生活"]),
    }


def error_response(error: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": error, "message": error}}, status_code=status_code)


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("backend.api.app:app", host="127.0.0.1", port=8787)


if __name__ == "__main__":
    main()
