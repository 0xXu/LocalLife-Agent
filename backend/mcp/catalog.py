from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.domain.models import ActionKind, PolicyTriggerKind, SupplyLifecycleStage


class CapabilityPlanningSemantics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consumes_user_time: bool
    trigger_kind: PolicyTriggerKind
    minimum_commitments: int = Field(default=1, ge=0)
    maximum_commitments: int = Field(default=1, ge=1)
    location_bound: bool = False
    provides_transition_evidence: bool = False
    required_evidence_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def commitment_range(self) -> "CapabilityPlanningSemantics":
        if self.minimum_commitments > self.maximum_commitments:
            raise ValueError("minimum commitments cannot exceed maximum commitments")
        return self


class CapabilityCompletionSemantics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_sources: list[
        Literal["provider_status", "redemption", "arrival", "user_confirmation"]
    ] = Field(min_length=1)
    provider_statuses: list[str] = Field(default_factory=list)
    timezone: str
    user_confirmation_earliest_minutes_from_start: int
    user_confirmation_latest_minutes_from_end: int = Field(ge=0)


class CapabilityLifecycleSemantics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stages: list[SupplyLifecycleStage] = Field(min_length=1)
    hold_ttl_seconds: int = Field(ge=30)
    refresh_before_commit: bool = True
    observable_signals: list[PolicyTriggerKind] = Field(min_length=1)
    change_actions: list[ActionKind] = Field(default_factory=list)
    compensation_actions: dict[ActionKind, ActionKind] = Field(default_factory=dict)
    offline_verification: bool = False
    completion: CapabilityCompletionSemantics


class ContextRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str
    required_by: str


class CapabilityRetrievalSemantics(BaseModel):
    """Provider-owned declaration of planning-ready read tools."""

    model_config = ConfigDict(extra="forbid")

    entry_tools: list[str] = Field(min_length=1)


class CapabilityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str
    description: str
    outcome_fit: str
    tools: list[str] = Field(min_length=1)
    retrieval: CapabilityRetrievalSemantics
    planning: CapabilityPlanningSemantics
    lifecycle: CapabilityLifecycleSemantics
    context_schema: list[ContextRequirement] = Field(default_factory=list)


class DecisionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str
    clarification: str
    safety: str


class CapabilityCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: int = Field(ge=1)
    provider: str
    decision_policy: DecisionPolicy
    lifecycle_tools: list[str] = Field(default_factory=list)
    capabilities: list[CapabilityDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_capability_ids(self) -> "CapabilityCatalog":
        ids = [item.id for item in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("capability ids must be unique")
        for capability in self.capabilities:
            unpublished = set(capability.retrieval.entry_tools) - set(capability.tools)
            if unpublished:
                raise ValueError(
                    f"retrieval tools are not published by {capability.id}: "
                    f"{sorted(unpublished)}"
                )
        return self

    def select(self, capability_ids: list[str]) -> list[CapabilityDefinition]:
        index = {item.id: item for item in self.capabilities}
        unknown = [item for item in capability_ids if item not in index]
        if unknown:
            raise ValueError(f"model selected unpublished capabilities: {unknown}")
        return [index[item] for item in dict.fromkeys(capability_ids)]


@lru_cache
def load_capability_catalog() -> CapabilityCatalog:
    path = Path(__file__).with_name("capabilities.json")
    return CapabilityCatalog.model_validate(json.loads(path.read_text(encoding="utf-8")))


async def discover_capability_catalog(mcp_url: str) -> CapabilityCatalog:
    """Read the provider-owned catalog across the real MCP seam."""
    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource("meituan://fulfillment/capabilities")
    return CapabilityCatalog.model_validate_json(result.contents[0].text)
