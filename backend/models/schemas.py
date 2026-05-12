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
    source: str = "local_seed_catalog"
    reason: str = ""
    risk_tags: list[str] = field(default_factory=list)
    review_count: int = 100
    supported_scenarios: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "POI":
        return cls(
            id=item["id"],
            name=item["name"],
            category=item["category"],
            lat=float(item["lat"]),
            lng=float(item["lng"]),
            distance_km=float(item["distance_km"]),
            rating=float(item["rating"]),
            avg_price=int(item["avg_price"]),
            tags=list(item["tags"]),
            duration_minutes=int(item["duration_minutes"]),
            open_hours=[dict(value) for value in item["open_hours"]],
            wait_minutes=int(item.get("wait_minutes", 0)),
            booking_supported=bool(item.get("booking_supported", False)),
            availability=[dict(value) for value in item.get("availability", [])],
            source=item.get("source", "local_seed_catalog"),
            reason=item.get("reason", ""),
            risk_tags=list(item.get("risk_tags", [])),
            review_count=int(item.get("review_count", 100)),
            supported_scenarios=list(item.get("supported_scenarios", [])),
        )


@dataclass
class Coupon:
    id: str
    poi_id: str
    title: str
    price: int
    face_value: int
    rules: str
    valid_until: str


@dataclass
class MenuItem:
    id: str
    poi_id: str
    name: str
    price: int
    tags: list[str]


@dataclass
class AvailabilitySlot:
    place_id: str
    time: str
    available: bool
    capacity: int


@dataclass
class RouteLeg:
    from_id: str
    to_id: str
    mode: str
    minutes: int
    distance_km: float


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
    score: int = 90
    risk: str = ""


@dataclass
class PlanAction:
    type: str
    label: str
    target: str
    detail: str
    requires_confirmation: bool = True
    tool: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanOverview:
    theme: str
    total_duration: str
    drive_time: str
    walking_distance: str
    estimated_cost: str
    score: int = 90


@dataclass
class PlanVariant:
    kind: str
    title: str
    summary: str
    score: int
    estimated_budget: int
    itinerary: list[ItineraryStep]


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
class ToolCall:
    tool: str
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    status: str
    duration_ms: int = 0
    side_effect: bool = False
    error: str = ""


@dataclass
class ToolResult:
    tool: str
    output: dict[str, Any]
    status: str = "ok"
    duration_ms: int = 120
    side_effect: bool = False
    error: str = ""


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
class Checkpoint:
    plan_id: str
    status: str
    trace: list[TraceStep]
    pending_actions: list[PlanAction]
    receipts: list[Receipt]
    recovery_history: list[RecoveryDiff]


@dataclass
class PlanState:
    goal: str
    plan_id: str = ""
    status: str = "input_received"
    constraints: ParsedConstraints | None = None
    context: dict[str, Any] = field(default_factory=dict)
    candidates: dict[str, list[POI]] = field(default_factory=dict)
    ranked: dict[str, list[POI]] = field(default_factory=dict)
    itinerary: list[ItineraryStep] = field(default_factory=list)
    route: dict[str, Any] = field(default_factory=dict)
    overview: PlanOverview | None = None
    actions: list[PlanAction] = field(default_factory=list)
    pending_actions: list[PlanAction] = field(default_factory=list)
    variants: list[PlanVariant] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    receipts: list[Receipt] = field(default_factory=list)
    diff: RecoveryDiff | None = None
    recovery_history: list[RecoveryDiff] = field(default_factory=list)
    adjustment: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def add_trace(self, trace: TraceStep) -> None:
        self.trace.append(trace)

    def add_tool_result(self, result: ToolResult, input_summary: dict[str, Any] | None = None) -> None:
        self.tool_calls.append(
            ToolCall(
                tool=result.tool,
                input_summary=input_summary or {},
                output_summary=result.output,
                status=result.status,
                duration_ms=result.duration_ms,
                side_effect=result.side_effect,
                error=result.error,
            )
        )

    def checkpoint(self) -> Checkpoint:
        return Checkpoint(
            plan_id=self.plan_id,
            status=self.status,
            trace=list(self.trace),
            pending_actions=list(self.pending_actions),
            receipts=list(self.receipts),
            recovery_history=list(self.recovery_history),
        )

    def plan_dict(self) -> dict[str, Any]:
        fit = constraint_fit_dict(self.constraints, self.itinerary, self.overview)
        return {
            "id": self.plan_id,
            "status": self.status,
            "title": plan_title(self.constraints, self.itinerary),
            "summary": plan_summary(self.constraints, self.itinerary),
            "constraints": to_dict(self.constraints),
            "constraint_fit": fit,
            "itinerary": [step_dict(step) for step in self.itinerary],
            "overview": frontend_overview(self.overview),
            "actions": [action_dict(action) for action in self.actions],
            "variants": [variant_dict(variant, fit) for variant in self.variants],
            "receipts": [to_dict(receipt) for receipt in self.receipts],
            "badges": plan_badges(self.constraints, self.itinerary),
        }


def plan_title(constraints: ParsedConstraints | None, itinerary: list[ItineraryStep] | None = None) -> str:
    scenario = constraints.scenario if constraints else "family"
    step_types = {step.type for step in itinerary or []}
    intent_label = str((constraints.preferences if constraints else {}).get("intent_label", "")).strip()
    activity_text = " ".join(step.title for step in itinerary or [] if step.type == "activity")
    if intent_label and scenario not in {"family", "friends", "date", "rainy_indoor"}:
        return f"{intent_label}短计划" if "restaurant" not in step_types else f"{intent_label} + 顺路用餐计划"
    if any(keyword in activity_text for keyword in ["山", "徒步", "登山", "步道"]):
        return "户外徒步短计划" if "restaurant" not in step_types else "户外徒步 + 顺路补给计划"
    if itinerary and "restaurant" not in step_types:
        return {
            "family": "亲子轻活动短计划",
            "friends": "朋友轻活动短计划",
            "date": "安静体验短计划",
            "rainy_indoor": "雨天室内短计划",
        }.get(scenario, "本地生活短计划")
    if itinerary and "dessert_walk" not in step_types:
        return {
            "family": "亲子活动 + 顺路用餐计划",
            "friends": "朋友活动 + 顺路聚餐计划",
            "date": "安静体验 + 顺路用餐计划",
            "rainy_indoor": "雨天室内活动 + 顺路用餐计划",
        }.get(scenario, "本地生活顺路计划")
    return {
        "family": "亲子科学馆 + 健康轻食半日计划",
        "friends": "朋友轻松活动 + 健康聚餐半日计划",
        "date": "安静约会 + 氛围晚餐半日计划",
        "rainy_indoor": "雨天室内活动 + 顺路用餐半日计划",
    }.get(scenario, "本地生活半日执行计划")


def plan_summary(constraints: ParsedConstraints | None, itinerary: list[ItineraryStep] | None = None) -> str:
    scenario = constraints.scenario if constraints else "family"
    step_types = {step.type for step in itinerary or []}
    intent_label = str((constraints.preferences if constraints else {}).get("intent_label", "")).strip()
    activity_text = " ".join(step.title for step in itinerary or [] if step.type == "activity")
    if intent_label and scenario not in {"family", "friends", "date", "rainy_indoor"}:
        return f"围绕“{intent_label}”选择本地供给，按时间、距离、预算和可执行动作生成计划。"
    if any(keyword in activity_text for keyword in ["山", "徒步", "登山", "步道"]):
        return "围绕户外徒步安排核心路线，去掉不必要的餐厅和甜品绕路。" if "restaurant" not in step_types else "户外徒步后只保留顺路补给，控制绕行和等待。"
    if itinerary and "restaurant" not in step_types:
        return {
            "family": "只保留亲子活动和必要交通，适合短时间轻量出门。",
            "friends": "只保留核心活动和必要交通，减少额外排队与绕路。",
            "date": "只保留安静体验和必要交通，适合一小时左右的轻计划。",
            "rainy_indoor": "只保留室内活动和必要交通，规避天气风险。",
        }.get(scenario, "按当前时长只保留核心体验。")
    if itinerary and "dessert_walk" not in step_types:
        return {
            "family": "活动后顺路用餐，不额外安排饭后散步。",
            "friends": "活动和聚餐连在一起，控制总时长和路线绕行。",
            "date": "安静体验后顺路用餐，减少等待和奔波。",
            "rainy_indoor": "室内活动后顺路用餐，保持路线稳定。",
        }.get(scenario, "围绕核心活动和用餐生成顺路计划。")
    return {
        "family": "亲子活动、健康轻食、饭后散步和确认后执行回执。",
        "friends": "室内活动、可拍照聊天餐厅、团购券和朋友群分享。",
        "date": "安静活动、氛围餐厅、低排队风险和顺路散步。",
        "rainy_indoor": "雨天优先室内点位，自动规避户外风险。",
    }.get(scenario, "围绕当前约束生成可执行本地生活方案。")


def step_dict(step: ItineraryStep) -> dict[str, Any]:
    return {
        "start": step.start,
        "end": step.end,
        "type": step.type,
        "title": step.title,
        "place_id": step.place_id,
        "reason": step.reason,
        "cost": step.cost,
        "travel": step.travel,
        "score": step.score,
        "risk": step.risk,
    }


def action_dict(action: PlanAction) -> dict[str, Any]:
    payload = dict(action.payload)
    place_id = payload.get("place_id") or payload.get("shop_id")
    return {
        "id": action_id(action),
        "type": action.type,
        "place_id": place_id,
        "label": action.label,
        "target": action.target,
        "detail": action.detail,
        "requires_confirmation": action.requires_confirmation,
        "requiresConfirmation": action.requires_confirmation,
        "tool": action.tool,
        "payload": payload,
    }


def action_id(action: PlanAction) -> str:
    target = str(action.target).strip().replace(" ", "_")
    return f"{action.tool or action.type}_{target or 'default'}"


def variant_dict(variant: PlanVariant, fit: dict[str, float] | None = None) -> dict[str, Any]:
    return {
        "id": f"variant_{variant.kind}",
        "kind": variant.kind,
        "title": variant.title,
        "summary": variant.summary,
        "score": variant.score,
        "estimated_budget": variant.estimated_budget,
        "itinerary": [step_dict(step) for step in variant.itinerary],
        "constraint_fit": fit or {},
    }


def frontend_overview(overview: PlanOverview | None) -> dict[str, Any]:
    if not overview:
        return {}
    return {
        "theme": overview.theme,
        "totalDuration": overview.total_duration,
        "driveTime": overview.drive_time,
        "walkingDistance": overview.walking_distance,
        "estimatedCost": overview.estimated_cost,
        "score": overview.score,
    }


def state_response(state: PlanState) -> dict[str, Any]:
    response = {
        "constraints": to_dict(state.constraints),
        "progress": progress_from_trace(state.trace),
        "trace": [to_dict(step) for step in state.trace],
        "tool_calls": [to_dict(call) for call in state.tool_calls],
        "itinerary": state.plan_dict()["itinerary"],
        "pending_actions": [action_dict(action) for action in state.pending_actions],
        "plan": state.plan_dict(),
    }
    if state.route:
        response["route"] = state.route
    if state.receipts:
        response["receipts"] = [to_dict(receipt) for receipt in state.receipts]
    if state.diff:
        response["diff"] = state.diff.as_frontend_dict()
        response["adjustment"] = state.adjustment
    return response


def constraint_fit_dict(constraints: ParsedConstraints | None, itinerary: list[ItineraryStep], overview: PlanOverview | None) -> dict[str, float]:
    if not constraints:
        return {"distance": 1, "time": 1, "budget": 1}
    radius = max(float(constraints.constraints.get("radius_km", 5)), 1)
    max_score = max((step.score for step in itinerary if step.type != "transport"), default=90)
    distance_fit = max(0.0, min(1.0, max_score / 100))
    time_fit = 1.0 if overview and overview.total_duration else 0.85
    budget_fit = 0.92
    if overview:
        estimated = parse_money(overview.estimated_cost)
        level = str(constraints.preferences.get("budget_level", "medium"))
        limit = 500 if level == "low" else 1600 if level == "high" else 1000
        budget_fit = max(0.0, min(1.0, 1 - max(0, estimated - limit) / max(limit, 1)))
    result = {
        "distance": round(distance_fit if radius else 1.0, 2),
        "time": round(time_fit, 2),
        "budget": round(budget_fit, 2),
    }
    if constraints.people.get("children"):
        result["child_friendly"] = 1.0 if any(step.type == "activity" for step in itinerary) else 0.6
    if constraints.preferences.get("diet"):
        result["diet"] = 0.9 if any(step.type == "restaurant" for step in itinerary) else 0.7
    return result


def parse_money(value: str) -> int:
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits or "0")


def plan_badges(constraints: ParsedConstraints | None, itinerary: list[ItineraryStep]) -> list[str]:
    if not constraints:
        return ["本地生活"]
    labels = {
        "family": "家庭",
        "friends": "朋友",
        "date": "约会",
        "rainy_indoor": "雨天",
    }
    intent = str(constraints.preferences.get("intent_label", "")).strip()
    badges = [labels.get(constraints.scenario, intent or "开放域")]
    badges.extend(str(tag) for tag in constraints.preferences.get("activity", [])[:2])
    if "restaurant" not in {step.type for step in itinerary}:
        badges.append("轻量短计划")
    return list(dict.fromkeys(badges))


def progress_from_trace(trace: list[TraceStep]) -> list[dict[str, str]]:
    labels = {
        "IntentParserAgent": "理解出行需求",
        "ContextBuilderAgent": "补全场景上下文",
        "CandidateSearchAgent": "筛选本地供给",
        "RankerAgent": "多目标排序",
        "RouteSchedulerAgent": "生成时间轴和路线",
        "PlanValidatorAgent": "校验可订性和约束",
        "ConfirmationAgent": "等待用户确认",
        "ExecutionAgent": "执行已确认动作",
        "RecoveryAgent": "异常恢复",
    }
    return [
        {
            "label": labels.get(step.agent, step.agent),
            "detail": step.message,
            "status": "done" if step.status == "ok" else step.status,
        }
        for step in trace
    ]
