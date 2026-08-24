from typing import Literal

from pydantic import BaseModel, Field

from backend.domain.models import ActionKind, PlanEditOperation, RealityEventKind


class StartTaskRequest(BaseModel):
    goal: str = Field(min_length=2, max_length=2000)
    user_id: str = "demo-user"


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class DecisionSelectionRequest(BaseModel):
    option_id: str = Field(min_length=1, max_length=200)


class OutcomeCheckInRequest(BaseModel):
    response: Literal["achieved", "partly", "not_achieved"]
    note: str | None = Field(default=None, max_length=500)


class CompensationRequest(BaseModel):
    fulfillment_event_id: str
    action: ActionKind


class SupplyActionRequest(BaseModel):
    node_id: str
    action: ActionKind


class PlanEditRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)
    operation: PlanEditOperation | None = None
    node_id: str | None = None
    keep_other_nodes: bool = True
    starts_at: str | None = Field(
        default=None,
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
    )
    budget_yuan: int | None = Field(default=None, ge=1)
    option_id: str | None = None
    candidate_id: str | None = None


class RealityEventRequest(BaseModel):
    kind: RealityEventKind
    detail: str = Field(min_length=1, max_length=1000)
    magnitude: int = 0
    node_id: str | None = None
    supply_id: str | None = None
    location: str | None = Field(default=None, min_length=1, max_length=300)
    completion_source: Literal[
        "provider_status", "redemption", "arrival", "user_confirmation"
    ] | None = None
    provider_status: str | None = Field(default=None, max_length=100)
