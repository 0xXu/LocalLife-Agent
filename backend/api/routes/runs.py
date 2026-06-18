from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.api.schemas.runs import CreateRunRequest, CreateRunResponse, RunStatusResponse
from backend.domain.events import format_sse_event
from backend.domain.run import PlanRunRequest

router = APIRouter(prefix="/api/runs", tags=["runs"])


def run_service(request: Request):
    return request.app.state.run_service


@router.post("", response_model=CreateRunResponse)
async def create_run(body: CreateRunRequest, request: Request) -> CreateRunResponse:
    record = run_service(request).create_run(PlanRunRequest(goal=body.goal, user_id=body.user_id, mode=body.mode))
    return CreateRunResponse(
        run_id=record.run_id,
        plan_id=record.plan_id,
        status=record.status,
        events_url=f"/api/runs/{record.run_id}/events",
    )


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run(run_id: str, request: Request) -> RunStatusResponse:
    record = run_service(request).get_run(run_id)
    return RunStatusResponse(**record.__dict__)


@router.get("/{run_id}/events")
async def stream_run_events(run_id: str, request: Request) -> StreamingResponse:
    service = run_service(request)
    service.get_run(run_id)

    async def event_stream():
        replayed_event_ids: set[str] = set()
        for event in service.events.replay(run_id):
            replayed_event_ids.add(event.event_id)
            yield format_sse_event(event)
        while True:
            item = await service.events.next_sse(run_id)
            if item is None:
                break
            event_id = sse_event_id(item)
            if event_id is not None and event_id in replayed_event_ids:
                continue
            yield item

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def sse_event_id(item: str) -> str | None:
    for line in item.splitlines():
        if line.startswith("id: "):
            return line.removeprefix("id: ")
    return None
