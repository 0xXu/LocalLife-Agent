from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


def to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value


@dataclass
class ParsedConstraints:
    scenario: str
    origin: dict[str, Any]
    time_window: dict[str, Any]
    people: dict[str, Any]
    preferences: dict[str, Any]
    constraints: dict[str, Any]
    required_actions: list[str]


@dataclass
class POI:
    id: str
    name: str
    category: str
    lat: float
    lng: float
    distance_km: float
    rating: float
    avg_price: int
    tags: list[str]
    duration_minutes: int
    open_hours: list[dict[str, str]]
    wait_minutes: int = 0
    booking_supported: bool = False
    availability: list[dict[str, Any]] = field(default_factory=list)
    source: str = "mock_poi_db"
    reason: str = ""


@dataclass
class ItineraryStep:
    start: str
    end: str
    type: str
    title: str
    place_id: str
    reason: str
    cost: str
    travel: str


@dataclass
class PlanAction:
    type: str
    label: str
    target: str
    detail: str
    requires_confirmation: bool = True


@dataclass
class PlanOverview:
    theme: str
    total_duration: str
    drive_time: str
    walking_distance: str
    estimated_cost: str


@dataclass
class TraceStep:
    agent: str
    tool: str
    status: str
    message: str
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


@dataclass
class Receipt:
    type: str
    tool: str
    id: str
    status: str
    detail: str


@dataclass
class RecoveryDiff:
    changed: str
    reason: str
    from_value: str
    to: str
    cost_delta: str
    travel_delta: str
    preserved: list[str]

    def as_frontend_dict(self) -> dict[str, Any]:
        data = to_dict(self)
        data["from"] = data.pop("from_value")
        data["costDelta"] = data.pop("cost_delta")
        data["travelDelta"] = data.pop("travel_delta")
        return data


@dataclass
class PlanState:
    goal: str
    plan_id: str = ""
    status: str = "input"
    constraints: ParsedConstraints | None = None
    context: dict[str, Any] = field(default_factory=dict)
    candidates: dict[str, list[POI]] = field(default_factory=dict)
    ranked: dict[str, list[POI]] = field(default_factory=dict)
    itinerary: list[ItineraryStep] = field(default_factory=list)
    overview: PlanOverview | None = None
    actions: list[PlanAction] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)
    receipts: list[Receipt] = field(default_factory=list)
    diff: RecoveryDiff | None = None
    adjustment: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def add_trace(self, trace: TraceStep) -> None:
        self.trace.append(trace)

    def plan_dict(self) -> dict[str, Any]:
        scenario = self.constraints.scenario if self.constraints else "family"
        is_family = scenario == "family"
        return {
            "id": self.plan_id,
            "status": self.status,
            "title": "亲子科学馆 + 健康轻食半日计划" if is_family else "朋友轻松活动 + 健康聚餐半日计划",
            "summary": "科学馆亲子活动、低脂轻食餐厅和饭后河畔散步。" if is_family else "室内朋友活动、可订位轻食餐厅和饭后河畔散步。",
            "constraints": to_dict(self.constraints),
            "itinerary": [
                {
                    "start": step.start,
                    "end": step.end,
                    "type": step.type,
                    "title": step.title,
                    "place_id": step.place_id,
                    "reason": step.reason,
                    "cost": step.cost,
                    "travel": step.travel,
                }
                for step in self.itinerary
            ],
            "overview": frontend_overview(self.overview),
            "actions": [
                {
                    "type": action.type,
                    "label": action.label,
                    "target": action.target,
                    "detail": action.detail,
                    "requiresConfirmation": action.requires_confirmation,
                }
                for action in self.actions
            ],
        }


def frontend_overview(overview: PlanOverview | None) -> dict[str, str]:
    if not overview:
        return {}
    return {
        "theme": overview.theme,
        "totalDuration": overview.total_duration,
        "driveTime": overview.drive_time,
        "walkingDistance": overview.walking_distance,
        "estimatedCost": overview.estimated_cost,
    }


def state_response(state: PlanState) -> dict[str, Any]:
    response = {
        "constraints": to_dict(state.constraints),
        "progress": progress_from_trace(state.trace),
        "trace": [to_dict(step) for step in state.trace],
        "itinerary": state.plan_dict()["itinerary"],
        "plan": state.plan_dict(),
    }
    if state.receipts:
        response["receipts"] = [to_dict(receipt) for receipt in state.receipts]
    if state.diff:
        response["diff"] = state.diff.as_frontend_dict()
        response["adjustment"] = state.adjustment
    return response


def progress_from_trace(trace: list[TraceStep]) -> list[dict[str, str]]:
    labels = {
        "IntentParserAgent": "理解出行需求",
        "ContextBuilderAgent": "补全场景上下文",
        "CandidateSearchAgent": "筛选本地供给",
        "RankerAgent": "匹配餐厅和活动",
        "RouteSchedulerAgent": "规划顺路路线",
        "PlanValidatorAgent": "确认可订时间",
    }
    return [
        {
            "label": labels.get(step.agent, step.agent),
            "detail": step.message,
            "status": "done" if step.status == "ok" else step.status,
        }
        for step in trace
        if step.agent in labels
    ]
