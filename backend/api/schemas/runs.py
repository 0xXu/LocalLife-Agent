from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    goal: str = Field(min_length=1)
    user_id: str = "local_demo_user"
    mode: str = "plan"


class CreateRunResponse(BaseModel):
    run_id: str
    plan_id: str
    status: str
    events_url: str


class RunStatusResponse(BaseModel):
    run_id: str
    plan_id: str | None = None
    status: str
    current_agent: str | None = None
    created_at: str
    updated_at: str
    error: dict[str, Any] | None = None


class ApproveActionsRequest(BaseModel):
    action_ids: list[str]


class RejectRunRequest(BaseModel):
    reason: str = "user_rejected"
