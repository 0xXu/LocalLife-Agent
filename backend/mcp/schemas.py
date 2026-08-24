from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.models import SupplyOption


class ToolEnvelope(BaseModel):
    status: Literal["ok", "partial", "invalid_query", "no_supply", "stale_version"]
    observed_at: datetime
    valid_until: datetime
    world_version: int
    items: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CapabilityToolQuery(BaseModel):
    """One model-selected, provider-published read operation."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    tool_name: str
    arguments: dict[str, Any]


class CapabilityQueryPlan(BaseModel):
    """Semantic hand-off from intent understanding to deterministic retrieval."""

    model_config = ConfigDict(extra="forbid")

    queries: list[CapabilityToolQuery] = Field(default_factory=list)


class SupplyCallTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any]
    status: str
    item_count: int = Field(ge=0)
    world_version: int | None = None
    duration_ms: int = Field(ge=0)


class CapabilityEvidence(BaseModel):
    """Provider evidence returned through the query module interface."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    candidates: list[SupplyOption] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    calls: list[SupplyCallTrace] = Field(default_factory=list)
