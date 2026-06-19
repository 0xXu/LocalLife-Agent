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
