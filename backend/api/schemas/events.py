from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunEventEnvelope(BaseModel):
    type: str
    run_id: str
    plan_id: str | None = None
    seq: int = Field(ge=1)
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)
