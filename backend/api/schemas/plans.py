from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlanDetailResponse(BaseModel):
    plan_id: str
    run_id: str
    status: str
    plan: dict[str, Any]
    actions: list[dict[str, Any]] = Field(default_factory=list)
    receipts: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)


class PlanSummaryResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    created_at: str
    updated_at: str
    tags: list[str] = Field(default_factory=list)
    location: str | None = None
    estimated_cost: str | None = None
    itinerary_count: int = 0


class PlanListResponse(BaseModel):
    plans: list[PlanSummaryResponse]
    total: int
