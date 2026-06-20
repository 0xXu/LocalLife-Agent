"""Pydantic contracts shared by the API, planner, and persistence layers."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class POI(BaseModel):
    """An immutable point of interest available to the route planner."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str
    name: str
    category: str
    city: str
    rating: Annotated[float, Field(ge=0, le=5)]
    avg_cost: Annotated[float, Field(ge=0, alias="avgCost")] = 0
    tags: list[str] = Field(default_factory=list)
    queue_time: Annotated[float, Field(ge=0, alias="queueTime")] = 0


class Constraint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    value: float | str
    weight: Annotated[float, Field(gt=0)] = 1
    is_hard: bool = Field(default=False, alias="isHard")

    @classmethod
    def budget(cls, amount: float, weight: float = 1) -> "Constraint":
        return cls(id="budget", value=amount, weight=weight)

    @classmethod
    def time_window(cls, start: str, end: str) -> "Constraint":
        return cls(id="time_window", value=f"{start}-{end}", isHard=True)


class RouteSegment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    poi: POI
    arrival_time: str | None = Field(default=None, alias="arrivalTime")
    departure_time: str | None = Field(default=None, alias="departureTime")
    travel_time_from_previous: Annotated[
        float, Field(ge=0, alias="travelTimeFromPrevious")
    ] = 0


class Route(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    segments: list[RouteSegment]
    total_cost: Annotated[float, Field(ge=0, alias="totalCost")] = 0
    violated_soft_constraints: list[Constraint] = Field(
        default_factory=list, alias="violatedSoftConstraints"
    )
    score: Annotated[float, Field(ge=0, le=100)] = 100


class UserPreference(BaseModel):
    tags: dict[str, float] = Field(default_factory=dict)


class UserIntent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str
    city: str = "北京"
    district: str | None = None
    preferred_categories: list[str] = Field(
        default_factory=list, alias="preferredCategories"
    )
    budget: Annotated[float, Field(ge=0)] = 0
    party_size: Annotated[int, Field(ge=1, alias="partySize")] = 1
    start_time: str | None = Field(default=None, alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    min_rating: Annotated[float, Field(ge=0, le=5, alias="minRating")] = 0
    max_queue_minutes: Annotated[
        float, Field(ge=0, alias="maxQueueMinutes")
    ] = 0

    @field_validator("preferred_categories", mode="before")
    @classmethod
    def normalize_empty_categories(cls, value: list[str] | None) -> list[str]:
        return [] if value is None else value


class PlanResponse(BaseModel):
    """Legacy route-planning response fields retained verbatim for clients."""

    model_config = ConfigDict(populate_by_name=True)

    routes: list[Route] = Field(default_factory=list)
    warning: str | None = None
    recommendedRoute: Route | None = None
    explanation: str | None = None
    sessionId: str | None = None


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str
    sessionId: str | None = None
    city: str = "北京"
    userId: str | None = None


class PlanRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str
    sessionId: str | None = None
    city: str = "北京"
    intent: UserIntent | None = None
    userId: str | None = None


class AdjustRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sessionId: str
    adjustment: str
    city: str = "北京"
    userId: str | None = None
