from __future__ import annotations

import asyncio
import json
from json import JSONDecodeError
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.llm import LLMConfig
from backend.services import PlanningService


def create_app(service: PlanningService | None = None) -> FastAPI:
    api = FastAPI(
        title="WeekendPilot Backend",
        description="FastAPI backend for the WeekendPilot local-life planning workflow.",
        version="0.1.0",
    )
    api.state.planning_service = service or PlanningService()
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
        return planning_service(request).tool_schemas()

    @api.get("/api/traces/{plan_id}")
    async def traces(plan_id: str, request: Request) -> dict[str, Any]:
        service = planning_service(request)
        plan = service.get_plan(plan_id)
        return {"planId": plan_id, "trace": service.get_trace(plan_id), "tool_calls": plan.get("tool_calls", [])}

    @api.get("/api/plans/{plan_id}")
    async def get_plan(plan_id: str, request: Request) -> dict[str, Any]:
        return planning_service(request).get_plan(plan_id)

    @api.post("/api/plans/build")
    async def build_plan(request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        return planning_service(request).build_plan(str(body.get("goal", "")))

    @api.get("/api/plans/build/stream")
    async def build_plan_stream(goal: str, request: Request) -> StreamingResponse:
        svc = planning_service(request)
        queue: asyncio.Queue[tuple[str, str] | tuple[str, str, str] | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_progress(label: str, detail: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, (label, detail))

        def on_token(token: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("__token__", token))

        async def event_stream():
            result_holder: dict[str, Any] = {}
            error_holder: dict[str, str] = {}

            yield f"data: {json.dumps({'type': 'started'}, ensure_ascii=False)}\n\n"

            def run():
                try:
                    result_holder["data"] = svc.build_plan(goal, on_progress=on_progress, on_token=on_token)
                except Exception as exc:
                    error_holder["error"] = str(exc)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            loop.run_in_executor(None, run)

            while True:
                item = await queue.get()
                if item is None:
                    break
                if item[0] == "__token__":
                    yield f"data: {json.dumps({'type': 'token', 'content': item[1]}, ensure_ascii=False)}\n\n"
                else:
                    label, detail = item
                    yield f"data: {json.dumps({'type': 'progress', 'label': label, 'detail': detail}, ensure_ascii=False)}\n\n"

            if "error" in error_holder:
                yield f"data: {json.dumps({'type': 'error', 'message': error_holder['error']}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'done', 'result': result_holder['data']}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @api.post("/api/plans/{plan_id}/alternatives")
    async def build_alternatives(plan_id: str, request: Request) -> dict[str, Any]:
        response = planning_service(request).build_alternatives(plan_id)
        response["variants"] = response.get("alternatives", [])
        return response

    @api.post("/api/plans/{plan_id}/confirm")
    async def confirm_plan(plan_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        return planning_service(request).confirm_plan(plan_id, bool(body.get("confirmed")))

    @api.post("/api/plans/{plan_id}/execute")
    async def execute_plan(plan_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        return planning_service(request).execute_plan(plan_id, bool(body.get("confirmed")))

    @api.post("/api/plans/{plan_id}/recover")
    async def recover_plan(plan_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        return planning_service(request).recover_plan(plan_id, str(body.get("reason", "restaurant_unavailable")))

    @api.patch("/api/plans/{plan_id}/constraints")
    async def patch_constraints(plan_id: str, request: Request) -> dict[str, Any]:
        body = await read_json_object(request)
        return planning_service(request).patch_constraints(plan_id, body)

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


def planning_service(request: Request) -> PlanningService:
    return request.app.state.planning_service


def error_response(error: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": error, "message": error}}, status_code=status_code)


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("backend.api.app:app", host="127.0.0.1", port=8787)


if __name__ == "__main__":
    main()
