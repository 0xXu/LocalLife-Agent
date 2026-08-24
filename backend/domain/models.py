from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class TaskPhase(StrEnum):
    UNDERSTANDING = "understanding"
    CLARIFYING = "clarifying"
    RETRIEVING = "retrieving"
    COMPOSING = "composing"
    AWAITING_MANDATE = "awaiting_mandate"
    AWAITING_TRANSACTION = "awaiting_transaction"
    EXECUTING = "executing"
    NEEDS_REPLAN = "needs_replan"
    UNSUPPORTED = "unsupported"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Vertical(StrEnum):
    FOOD = "food"
    ACTIVITY = "activity"
    SERVICE = "service"
    DELIVERY = "delivery"
    MOBILITY = "mobility"


class ConstraintKind(StrEnum):
    BUDGET = "budget"
    DEADLINE = "deadline"
    ORIGIN = "origin"
    PARTY_SIZE = "party_size"
    PREFERENCE = "preference"


class ValueSource(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    DEFAULT = "default"


class Availability(StrEnum):
    AVAILABLE = "available"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


class ActionKind(StrEnum):
    RESERVE_TABLE = "reserve_table"
    BUY_COUPON = "buy_coupon"
    BUY_TICKET = "buy_ticket"
    REQUEST_RIDE = "request_ride"
    BOOK_SERVICE = "book_service"
    PLACE_ORDER = "place_order"
    START_NAVIGATION = "start_navigation"
    CHANGE_RESERVATION = "change_reservation"
    CHANGE_TICKET = "change_ticket"
    CHANGE_RIDE = "change_ride"
    CANCEL_RESERVATION = "cancel_reservation"
    REFUND_COUPON = "refund_coupon"
    REFUND_TICKET = "refund_ticket"
    CANCEL_RIDE = "cancel_ride"
    CANCEL_SERVICE = "cancel_service"
    CANCEL_ORDER = "cancel_order"


class NodeStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


class SupplyLifecycleStage(StrEnum):
    VERIFIED = "verified"
    QUOTED = "quoted"
    HELD = "held"
    COMMITTED = "committed"
    CHANGED = "changed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class TurnKind(StrEnum):
    CLARIFY = "clarify"
    PROPOSE = "propose"
    INFORM = "inform"


class Constraint(DomainModel):
    id: str = Field(default_factory=lambda: f"constraint_{uuid4().hex[:8]}")
    kind: ConstraintKind
    label: str
    value: str
    hard: bool = True
    source: ValueSource


class Assumption(DomainModel):
    id: str = Field(default_factory=lambda: f"assumption_{uuid4().hex[:8]}")
    label: str
    value: str
    reason: str
    editable: bool = True


class ContextFact(DomainModel):
    id: str = Field(default_factory=lambda: f"context_{uuid4().hex[:8]}")
    key: str
    label: str
    value: str
    source: ValueSource


class GoalContract(DomainModel):
    outcome: str
    city: str
    origin: str
    party_size: int = Field(ge=1, le=20)
    budget_yuan: int = Field(ge=1)
    deadline: str = Field(
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        description=(
            "Overall completion deadline for the entire plan, never an intermediate "
            "appointment, meal, session, or delivery time."
        ),
    )
    deadline_label: str = "最晚完成"
    context_facts: list[ContextFact] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    locked_fields: list[str] = Field(default_factory=list)


class ConstraintEdit(DomainModel):
    id: str
    value: str | None = None
    hard: bool | None = None
    delete: bool = False


class AssumptionEdit(DomainModel):
    id: str
    value: str | None = None
    delete: bool = False


class GoalContractEdit(DomainModel):
    outcome: str | None = None
    city: str | None = None
    origin: str | None = None
    party_size: int | None = Field(default=None, ge=1, le=20)
    budget_yuan: int | None = Field(default=None, ge=1)
    deadline: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    deadline_label: str | None = None
    constraint_edits: list[ConstraintEdit] = Field(default_factory=list)
    assumption_edits: list[AssumptionEdit] = Field(default_factory=list)
    lock_fields: list[str] = Field(default_factory=list)
    unlock_fields: list[str] = Field(default_factory=list)


class PlanEditOperation(StrEnum):
    LOCK_NODE = "lock_node"
    UNLOCK_NODE = "unlock_node"
    REPLACE_NODE = "replace_node"
    REMOVE_NODE = "remove_node"
    ADJUST_NODE = "adjust_node"
    ADJUST_BUDGET = "adjust_budget"
    SELECT_ALTERNATIVE = "select_alternative"
    UNDO_LAST_EDIT = "undo_last_edit"


class PlanEditIntent(DomainModel):
    source: Literal["natural_language", "direct"]
    instruction: str = Field(min_length=1)
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

    @model_validator(mode="after")
    def operation_payload(self) -> "PlanEditIntent":
        node_operations = {
            PlanEditOperation.LOCK_NODE,
            PlanEditOperation.UNLOCK_NODE,
            PlanEditOperation.REPLACE_NODE,
            PlanEditOperation.REMOVE_NODE,
            PlanEditOperation.ADJUST_NODE,
        }
        if self.operation in node_operations and self.node_id is None:
            raise ValueError("node plan edit requires node_id")
        if self.operation == PlanEditOperation.ADJUST_NODE and self.starts_at is None:
            raise ValueError("adjust_node requires starts_at")
        if self.operation == PlanEditOperation.ADJUST_BUDGET and self.budget_yuan is None:
            raise ValueError("adjust_budget requires budget_yuan")
        if self.operation == PlanEditOperation.SELECT_ALTERNATIVE and self.candidate_id is None:
            raise ValueError("select_alternative requires candidate_id")
        return self


class TemporalConstraint(DomainModel):
    capability_id: str
    relation: Literal[
        "exact_start",
        "earliest_start",
        "latest_end",
        "starts_after",
    ]
    time: str | None = Field(
        default=None,
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
    )
    reference_capability_id: str | None = None
    minimum_gap_minutes: int = Field(default=0, ge=0, le=240)
    source_constraint_id: str | None = None

    @model_validator(mode="after")
    def relation_payload(self) -> "TemporalConstraint":
        if self.relation == "starts_after":
            if not self.reference_capability_id:
                raise ValueError("starts_after requires reference_capability_id")
            if self.time is not None:
                raise ValueError("starts_after cannot contain an absolute time")
        elif self.time is None:
            raise ValueError(f"{self.relation} requires an absolute time")
        elif self.reference_capability_id is not None:
            raise ValueError("absolute time constraints cannot reference a capability")
        return self


PolicyTriggerKind = Literal[
    "inventory_unavailable",
    "queue_delay",
    "price_increase",
    "eta_delay",
    "hold_expired",
    "weather_change",
    "user_late",
    "location_change",
    "fulfillment_failure",
]

RealityEventKind = PolicyTriggerKind | Literal["node_completed"]


class GroundedCandidateSet(DomainModel):
    capability_id: str
    consumes_user_time: bool
    trigger_kind: PolicyTriggerKind
    location_bound: bool = False
    provides_transition_evidence: bool = False
    minimum_commitments: int = Field(default=1, ge=0)
    maximum_commitments: int = Field(default=1, ge=1)
    candidates: list["SupplyOption"] = Field(default_factory=list)

    @model_validator(mode="after")
    def commitment_range(self) -> "GroundedCandidateSet":
        if self.minimum_commitments > self.maximum_commitments:
            raise ValueError("minimum commitments cannot exceed maximum commitments")
        return self


class SupplyEvidence(DomainModel):
    checked_at: datetime = Field(default_factory=utc_now)
    detail: str
    inventory_version: int = 1
    valid_for_seconds: int = Field(default=300, ge=1)


class SupplyOption(DomainModel):
    id: str
    vertical: Vertical
    name: str
    venue: str
    district: str
    price_yuan: int = Field(
        ge=0,
        description=(
            "All-in payable total for this entire supply option and represented party; "
            "never multiply it by party size or add fees from metadata."
        ),
    )
    duration_minutes: int = Field(ge=1)
    rating: float = Field(ge=0, le=5)
    availability: Availability = Availability.AVAILABLE
    substitution_group: str | None = Field(
        default=None,
        description=(
            "Provider-published semantic equivalence group for safe direct replacement; "
            "options from different groups remain plan-level alternatives."
        ),
    )
    tags: list[str] = Field(default_factory=list)
    time_slots: list[str] = Field(default_factory=list)
    actions: list[ActionKind]
    evidence: SupplyEvidence
    metadata: dict[str, Any] = Field(default_factory=dict)


class SupplyReference(DomainModel):
    id: str = Field(default_factory=lambda: f"supply_ref_{uuid4().hex[:12]}")
    task_id: str
    node_id: str
    capability_id: str
    supply_id: str
    stage: SupplyLifecycleStage
    quote_id: str | None = None
    hold_id: str | None = None
    commitment_id: str | None = None
    commitments: dict[ActionKind, str] = Field(default_factory=dict)
    quoted_total_yuan: int | None = Field(default=None, ge=0)
    hold_expires_at: datetime | None = None
    world_version: int
    terms: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class OfflineVerificationResult(DomainModel):
    supply_id: str
    status: Literal["confirmed", "unavailable", "needs_human"]
    summary: str
    facts: dict[str, str] = Field(default_factory=dict)
    verified_at: datetime = Field(default_factory=utc_now)


class FeasibleSelection(DomainModel):
    capability_id: str
    option_id: str
    consumes_user_time: bool
    trigger_kind: PolicyTriggerKind
    starts_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    ends_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    price_yuan: int = Field(ge=0)


class PlanObjectiveVector(DomainModel):
    total_yuan: int = Field(ge=0)
    completion_minute: int = Field(ge=0, le=24 * 60)
    elapsed_minutes: int = Field(ge=0)
    movement_minutes: int = Field(ge=0)
    experience_milli: int = Field(ge=0)


class FeasiblePlanCandidate(DomainModel):
    id: str
    selections: list[FeasibleSelection] = Field(min_length=1)
    objectives: PlanObjectiveVector
    slack_minutes: int = Field(ge=0)


class InfeasibleReason(DomainModel):
    code: Literal[
        "missing_supply",
        "budget_conflict",
        "deadline_conflict",
        "time_window_conflict",
        "capacity_conflict",
        "no_combination",
    ]
    message: str
    constraint_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)


class FeasiblePlanSet(DomainModel):
    status: Literal["feasible", "infeasible", "unknown"]
    candidates: list[FeasiblePlanCandidate] = Field(default_factory=list)
    pareto_candidate_ids: list[str] = Field(default_factory=list)
    infeasible_reasons: list[InfeasibleReason] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_status(self) -> "FeasiblePlanSet":
        candidate_ids = {item.id for item in self.candidates}
        if self.status == "feasible" and not self.candidates:
            raise ValueError("feasible result requires candidates")
        if self.status == "infeasible" and not self.infeasible_reasons:
            raise ValueError("infeasible result requires reasons")
        if not set(self.pareto_candidate_ids).issubset(candidate_ids):
            raise ValueError("Pareto ids must reference feasible candidates")
        return self


class PlanNode(DomainModel):
    id: str
    capability_id: str
    vertical: Vertical
    title: str
    option_id: str
    starts_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    ends_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    price_yuan: int = Field(ge=0)
    venue: str
    reason: str
    consumes_user_time: bool = True
    trigger_kind: PolicyTriggerKind
    actions: list[ActionKind]
    status: NodeStatus = NodeStatus.PROPOSED
    depends_on: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    evidence: SupplyEvidence
    supply_reference: SupplyReference | None = None


class ExecutionMandate(DomainModel):
    max_total_yuan: int = Field(ge=1)
    deadline: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    allowed_verticals: list[Vertical]
    max_price_increase_yuan: int = Field(default=30, ge=0)
    allow_auto_substitution: bool = True
    approved_at: datetime | None = None


class TransactionLine(DomainModel):
    node_id: str
    action: ActionKind
    label: str
    amount_yuan: int = Field(ge=0)


class TransactionConfirmation(DomainModel):
    lines: list[TransactionLine]
    total_cap_yuan: int = Field(ge=0)
    confirmed_at: datetime | None = None


class PlanGraph(DomainModel):
    version: int = Field(default=1, ge=1)
    title: str
    thesis: str
    goal: GoalContract
    nodes: list[PlanNode]
    total_yuan: int = Field(ge=0)
    rationale: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    locked_node_ids: list[str] = Field(default_factory=list)
    mandate: ExecutionMandate
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def total_matches_nodes(self) -> "PlanGraph":
        expected = sum(node.price_yuan for node in self.nodes)
        if self.total_yuan != expected:
            raise ValueError(f"total_yuan must equal node sum ({expected})")
        unknown_locks = set(self.locked_node_ids) - {node.id for node in self.nodes}
        if unknown_locks:
            raise ValueError(f"locked nodes do not exist: {sorted(unknown_locks)}")
        return self


class PlanPatchOperation(DomainModel):
    operation: Literal["add", "replace", "remove", "update"]
    node_id: str
    reason: str
    node: PlanNode | None = None


class PlanPatch(DomainModel):
    from_version: int
    to_version: int
    summary: str
    operations: list[PlanPatchOperation]
    requires_confirmation: bool
    trigger_source: Literal["goal_edit", "plan_edit", "supply_event", "policy_trigger"]
    authorization_effect: Literal["within_mandate", "confirmation_required"]


class PlanAlternative(DomainModel):
    candidate_id: str
    direction: Literal[
        "cheaper",
        "earlier",
        "less_elapsed",
        "less_movement",
        "stronger_experience",
    ]
    summary: str
    total_yuan: int = Field(ge=0)
    completion_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    option_ids: list[str] = Field(min_length=1)


class TriggerCondition(DomainModel):
    kind: PolicyTriggerKind
    node_id: str
    threshold: int = Field(default=0, ge=0)


class FallbackPolicy(DomainModel):
    id: str = Field(default_factory=lambda: f"fallback_{uuid4().hex[:8]}")
    node_id: str
    replacement: PlanNode
    affected_node_ids: list[str] = Field(default_factory=list)
    authorization_effect: Literal["within_mandate", "confirmation_required"]


class DecisionPoint(DomainModel):
    id: str = Field(default_factory=lambda: f"decision_{uuid4().hex[:8]}")
    node_id: str
    trigger: TriggerCondition
    slack_minutes: int = Field(ge=0)
    decision_deadline: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    fallbacks: list[FallbackPolicy] = Field(default_factory=list)


class PlanPolicy(DomainModel):
    primary_plan: PlanGraph
    alternatives: list[PlanAlternative] = Field(default_factory=list, max_length=2)
    decision_points: list[DecisionPoint] = Field(default_factory=list)


class PlanUndoCheckpoint(DomainModel):
    policy: PlanPolicy
    fulfillment_event_count: int = Field(ge=0)


class DecisionBranch(DomainModel):
    action: Literal["continue", "stop"] = "continue"
    goal: GoalContract
    capability_ids: list[str] = Field(default_factory=list)
    temporal_constraints: list[TemporalConstraint] = Field(default_factory=list)
    path: Literal["quick", "orchestrated"] = "orchestrated"
    context_scope: str = "general"
    feasibility_status: Literal["feasible", "infeasible", "unknown"] = "unknown"
    verified_candidate_ids: SkipJsonSchema[dict[str, list[str]]] = Field(
        default_factory=dict
    )
    verified_candidates: SkipJsonSchema[dict[str, list[SupplyOption]]] = Field(
        default_factory=dict
    )
    authorization_effect: Literal["unchanged", "confirmation_required"] = "unchanged"

    @model_validator(mode="after")
    def executable_branch(self) -> "DecisionBranch":
        if self.action == "continue" and not self.capability_ids:
            raise ValueError("continuing decision branches require capabilities")
        if self.action == "continue" and self.path == "quick" and len(self.capability_ids) != 1:
            raise ValueError("quick decision branches require exactly one capability")
        if self.action == "stop" and self.capability_ids:
            raise ValueError("stopping decision branches cannot select capabilities")
        return self


class ClarificationOption(DomainModel):
    id: str
    label: str
    impact: str
    branch: DecisionBranch | None = None


class ClarificationQuestion(DomainModel):
    id: str = Field(default_factory=lambda: f"question_{uuid4().hex[:8]}")
    prompt: str
    why_now: str
    options: list[ClarificationOption] = Field(min_length=2, max_length=4)
    allow_free_text: bool = True


class PreferenceEvidence(DomainModel):
    subject: str = "self"
    context_scope: str
    dimension: str
    preference: str
    polarity: Literal["prefer", "avoid", "require"] = "prefer"
    source: Literal[
        "explicit_expression",
        "actual_choice",
        "agent_override",
        "cancellation",
        "fulfillment_outcome",
    ]
    confidence: float = Field(ge=0, le=1)
    task_id: str
    observed_at: datetime = Field(default_factory=utc_now)


class PreferenceFact(DomainModel):
    id: str = Field(default_factory=lambda: f"preference_{uuid4().hex[:10]}")
    user_id: str
    subject: str
    context_scope: str
    dimension: str
    preference: str
    polarity: Literal["prefer", "avoid", "require"]
    source: Literal[
        "explicit_expression",
        "actual_choice",
        "agent_override",
        "cancellation",
        "fulfillment_outcome",
    ]
    confidence: float = Field(ge=0, le=1)
    observed_at: datetime
    valid_from: datetime
    supersedes: str | None = None
    task_id: str
    active: bool = True


class PreferenceFactEdit(DomainModel):
    context_scope: str | None = None
    preference: str | None = None
    polarity: Literal["prefer", "avoid", "require"] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    delete: bool = False


class ChatMessage(DomainModel):
    id: str = Field(default_factory=lambda: f"message_{uuid4().hex[:8]}")
    role: Literal["user", "agent", "system"]
    content: str
    created_at: datetime = Field(default_factory=utc_now)


class ToolTrace(DomainModel):
    id: str = Field(default_factory=lambda: f"trace_{uuid4().hex[:10]}")
    agent: str
    tool: str
    input_summary: dict[str, Any] = Field(default_factory=dict)
    status: Literal["succeeded", "failed"]
    result_summary: str
    world_version: int | None = None
    duration_ms: int = Field(ge=0)
    occurred_at: datetime = Field(default_factory=utc_now)


class TaskProgressEvent(DomainModel):
    id: str = Field(default_factory=lambda: f"progress_{uuid4().hex[:10]}")
    kind: Literal[
        "goal_understood",
        "retrieval_started",
        "retrieval_completed",
        "feasibility_conflict",
        "composing_plan",
        "patch_completed",
    ]
    detail: str
    revision: int = Field(ge=1)
    capability_id: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)


class AgentTurn(DomainModel):
    kind: TurnKind
    message: str
    goal: GoalContract
    intent_path: Literal["quick", "orchestrated"] | None = None
    question: ClarificationQuestion | None = None
    policy: PlanPolicy | None = None
    feasible_plan_set: FeasiblePlanSet | None = None
    preference_evidence: list[PreferenceEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def required_payload(self) -> "AgentTurn":
        if self.kind == TurnKind.CLARIFY and self.question is None:
            raise ValueError("clarify turns require a question")
        if self.kind == TurnKind.PROPOSE and self.policy is None:
            raise ValueError("propose turns require a policy")
        return self


class FulfillmentCommand(DomainModel):
    id: str = Field(default_factory=lambda: f"command_{uuid4().hex[:12]}")
    task_id: str
    node_id: str
    action: ActionKind
    option_id: str
    amount_yuan: int = Field(ge=0)
    related_receipt_id: str | None = None
    commitment_context: dict[str, Any] = Field(default_factory=dict)


class FulfillmentEvent(DomainModel):
    id: str = Field(default_factory=lambda: f"event_{uuid4().hex[:10]}")
    task_id: str
    node_id: str
    action: ActionKind
    status: Literal["started", "succeeded", "failed", "compensated"]
    detail: str
    receipt_id: str | None = None
    actual_amount_yuan: int | None = Field(default=None, ge=0)
    lifecycle_stage: SupplyLifecycleStage | None = None
    compensation_action: ActionKind | None = None
    occurred_at: datetime = Field(default_factory=utc_now)


class SupplySignal(DomainModel):
    id: str = Field(default_factory=lambda: f"signal_{uuid4().hex[:10]}")
    supply_id: str
    kind: PolicyTriggerKind
    detail: str
    world_version: int
    magnitude: int = 0
    observed_at: datetime = Field(default_factory=utc_now)


class RealityEvent(DomainModel):
    id: str = Field(default_factory=lambda: f"reality_{uuid4().hex[:10]}")
    task_id: str
    kind: RealityEventKind
    detail: str
    magnitude: int = 0
    node_id: str | None = None
    supply_id: str | None = None
    location: str | None = None
    completion_evidence: "CompletionEvidence | None" = None
    occurred_at: datetime = Field(default_factory=utc_now)


class CompletionEvidence(DomainModel):
    source: Literal["provider_status", "redemption", "arrival", "user_confirmation"]
    detail: str
    provider_status: str | None = None
    observed_at: datetime = Field(default_factory=utc_now)


class LiveStep(DomainModel):
    node_id: str
    title: str
    instruction: str
    due_at: str
    status: Literal["upcoming", "ready", "in_progress", "done", "blocked"]
    completion_available: bool = False
    completion_hint: str | None = None


class ActualOutcome(DomainModel):
    total_yuan: int = Field(ge=0)
    completed_node_ids: list[str]
    compensated_node_ids: list[str] = Field(default_factory=list)
    completed_at: datetime
    summary: str
    goal_attainment: Literal["unknown", "achieved", "partly", "not_achieved"] = "unknown"
    preference_evidence: list[PreferenceEvidence] = Field(default_factory=list)


class OutcomeCheckIn(DomainModel):
    prompt: str
    response: Literal["achieved", "partly", "not_achieved"] | None = None
    note: str | None = None
    responded_at: datetime | None = None


class LiveState(DomainModel):
    next_step: LiveStep | None = None
    risk: str | None = None
    affected_node_ids: list[str] = Field(default_factory=list)
    agent_activity: str
    waiting_for: str | None = None
    available_actions: list[ActionKind] = Field(default_factory=list)
    last_signal: SupplySignal | None = None
    actual_outcome: ActualOutcome | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class TaskSnapshot(DomainModel):
    id: str = Field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    user_id: str
    goal_text: str
    phase: TaskPhase = TaskPhase.UNDERSTANDING
    revision: int = 1
    messages: list[ChatMessage] = Field(default_factory=list)
    goal: GoalContract | None = None
    question: ClarificationQuestion | None = None
    policy: PlanPolicy | None = None
    feasible_plan_set: FeasiblePlanSet | None = None
    transaction_confirmation: TransactionConfirmation | None = None
    last_patch: PlanPatch | None = None
    pending_plan_edit: PlanEditIntent | None = None
    plan_undo: PlanUndoCheckpoint | None = None
    fulfillment_events: list[FulfillmentEvent] = Field(default_factory=list)
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    progress_events: list[TaskProgressEvent] = Field(default_factory=list)
    workflow_id: str | None = None
    observation_workflow_id: str | None = None
    context_scope: str = "general"
    intent_path: Literal["quick", "orchestrated"] | None = None
    applied_preference_fact_ids: list[str] = Field(default_factory=list)
    supply_signals: list[SupplySignal] = Field(default_factory=list)
    reality_events: list[RealityEvent] = Field(default_factory=list)
    live: LiveState | None = None
    outcome_check_in: OutcomeCheckIn | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def advance(self) -> None:
        self.revision += 1
        self.updated_at = utc_now()
