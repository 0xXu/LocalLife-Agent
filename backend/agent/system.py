from __future__ import annotations

import asyncio
import json
import time
from enum import StrEnum
from typing import Any, Protocol

from google.adk.agents import Agent
from google.adk.memory import BaseMemoryService
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.config import Settings
from backend.domain.models import (
    AgentTurn,
    ClarificationOption,
    ClarificationQuestion,
    DecisionBranch,
    FeasiblePlanSet,
    GoalContract,
    GroundedCandidateSet,
    PreferenceEvidence,
    SupplyOption,
    TaskSnapshot,
    TaskPhase,
    TemporalConstraint,
    ToolTrace,
    TurnKind,
)
from backend.mcp import (
    CapabilityCatalog,
    CapabilityEvidence,
    CapabilityQueryOrchestrator,
    CapabilityQueryPlan,
)
from backend.planning import PlanningModule
from backend.tasks import TaskModule


class IntentDisposition(StrEnum):
    PROCEED = "proceed"
    CLARIFY = "clarify"
    INFORM = "inform"


class IntentPath(StrEnum):
    QUICK = "quick"
    ORCHESTRATED = "orchestrated"


class IntentClarificationOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    impact: str


class IntentClarification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str
    why_now: str
    options: list[IntentClarificationOption] = Field(min_length=2, max_length=4)


class CounterfactualGoalPatch(BaseModel):
    """Only the goal fields that differ from the frame's shared base contract."""

    model_config = ConfigDict(extra="forbid")
    outcome: str | None = None
    city: str | None = None
    origin: str | None = None
    party_size: int | None = Field(default=None, ge=1, le=20)
    budget_yuan: int | None = Field(default=None, ge=1)
    deadline: str | None = Field(
        default=None,
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
    )
    deadline_label: str | None = None
    preferences: list[str] | None = None

    def apply(self, base: GoalContract) -> GoalContract:
        return base.model_copy(
            update=self.model_dump(exclude_none=True),
            deep=True,
        )


class CounterfactualBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    option_id: str
    goal_patch: CounterfactualGoalPatch = Field(
        default_factory=CounterfactualGoalPatch
    )
    capability_ids: list[str] = Field(min_length=1)
    temporal_constraints: list[TemporalConstraint] = Field(default_factory=list)
    query_plan: CapabilityQueryPlan


class IntentFrame(BaseModel):
    """Typed semantic hand-off between goal understanding and supply planning."""

    model_config = ConfigDict(extra="forbid")
    disposition: IntentDisposition
    path: IntentPath = IntentPath.ORCHESTRATED
    context_scope: str = "general"
    goal: GoalContract
    capability_ids: list[str] = Field(default_factory=list)
    temporal_constraints: list[TemporalConstraint] = Field(default_factory=list)
    query_plan: CapabilityQueryPlan = Field(default_factory=CapabilityQueryPlan)
    decision_basis: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    counterfactual_branches: list[CounterfactualBranch] = Field(default_factory=list)
    default_branch_option_id: str | None = None
    message: str
    question: IntentClarification | None = None

    @model_validator(mode="after")
    def disposition_payload(self) -> "IntentFrame":
        if self.disposition == IntentDisposition.PROCEED and not self.capability_ids:
            raise ValueError("proceed requires at least one published capability")
        if self.path == IntentPath.QUICK and len(self.capability_ids) != 1:
            raise ValueError("quick path requires exactly one published capability")
        if self.disposition == IntentDisposition.CLARIFY and self.question is None:
            raise ValueError("clarify requires one high-leverage question")
        if self.disposition != IntentDisposition.CLARIFY and self.question is not None:
            raise ValueError("only clarify may include a question")
        if self.disposition == IntentDisposition.CLARIFY and self.question is not None:
            option_ids = {item.id for item in self.question.options}
            branch_ids = {item.option_id for item in self.counterfactual_branches}
            if branch_ids != option_ids:
                raise ValueError("clarification requires one counterfactual branch per option")
            if self.default_branch_option_id not in option_ids:
                raise ValueError("clarification requires a valid default branch")
        elif self.counterfactual_branches or self.default_branch_option_id is not None:
            raise ValueError("only clarification may include counterfactual branches")
        return self


class CandidateSelection(BaseModel):
    """Semantic choice inside a solver-certified Pareto frontier."""

    model_config = ConfigDict(extra="forbid")
    title: str
    candidate_id: str
    alternative_candidate_ids: list[str] = Field(default_factory=list, max_length=2)
    selection_reasons: dict[str, str] = Field(default_factory=dict)
    preference_evidence: list[PreferenceEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def required_payload(self) -> "CandidateSelection":
        if self.candidate_id in self.alternative_candidate_ids:
            raise ValueError("primary candidate cannot also be an alternative")
        self.alternative_candidate_ids = list(dict.fromkeys(
            self.alternative_candidate_ids
        ))[:2]
        return self


class QuestionPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str
    why_now: str
    labels: dict[str, str]


class RecoveryPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str
    why_now: str


class DecisionEngine(Protocol):
    async def decide(self, task: TaskSnapshot, user_message: str) -> AgentTurn: ...
    async def decide_branch(
        self,
        task: TaskSnapshot,
        branch: DecisionBranch,
        selection_label: str,
    ) -> AgentTurn: ...
    async def close(self) -> None: ...


def extract_json_object(raw: str) -> str:
    """Extract one complete object while leaving schema validation to Pydantic."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
    decoder = json.JSONDecoder()
    for offset, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[offset:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
    raise ValueError("model response did not contain a complete JSON object")


def decision_context(task: TaskSnapshot) -> dict[str, Any]:
    """Project durable state without replaying traces or an ADK conversation."""
    return {
        "task_id": task.id,
        "revision": task.revision,
        "phase": task.phase,
        "intent_path": task.intent_path,
        "goal_text": task.goal_text,
        "messages": [
            {"role": item.role, "content": item.content}
            for item in task.messages[-8:]
        ],
        "goal": task.goal.model_dump(mode="json") if task.goal else None,
        "question": task.question.model_dump(mode="json") if task.question else None,
        "policy": task.policy.model_dump(mode="json") if task.policy else None,
        "feasible_plan_set": (
            task.feasible_plan_set.model_dump(mode="json")
            if task.feasible_plan_set
            else None
        ),
        "last_patch": task.last_patch.model_dump(mode="json") if task.last_patch else None,
        "pending_plan_edit": (
            task.pending_plan_edit.model_dump(mode="json")
            if task.pending_plan_edit
            else None
        ),
        "fulfillment_events": [
            item.model_dump(mode="json") for item in task.fulfillment_events
        ],
    }


async def materialize_candidate_selection(
    frame: IntentFrame,
    decision: CandidateSelection,
    planning: PlanningModule,
    feasible_set: FeasiblePlanSet,
    supply_evidence: dict[str, SupplyOption] | None = None,
) -> AgentTurn:
    policy = await planning.materialize_policy(
        frame.goal,
        feasible_set,
        decision.candidate_id or "",
        decision.alternative_candidate_ids,
        title=decision.title or frame.goal.outcome,
        selection_reasons=decision.selection_reasons,
        supply_evidence=supply_evidence,
    )
    return AgentTurn(
        kind=TurnKind.PROPOSE,
        message=f"方案已组合：{policy.primary_plan.thesis}",
        goal=frame.goal,
        intent_path=frame.path.value,
        policy=policy,
        feasible_plan_set=feasible_set,
        preference_evidence=decision.preference_evidence,
    )


class GoogleAdkDecisionEngine:
    """A two-stage intent orchestrator over a provider-published capability catalog."""

    def __init__(
        self,
        settings: Settings,
        planning: PlanningModule,
        tasks: TaskModule,
        session_service: BaseSessionService,
        memory_service: BaseMemoryService,
        capability_catalog: CapabilityCatalog,
        query_orchestrator: CapabilityQueryOrchestrator,
    ) -> None:
        self.settings = settings
        self.planning = planning
        self.tasks = tasks
        self.session_service = session_service
        self.memory_service = memory_service
        self.catalog = capability_catalog
        self.query_orchestrator = query_orchestrator
        self.model = LiteLlm(
            model=settings.deepseek_litellm_model,
            api_base=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            extra_body={"thinking": {"type": settings.deepseek_thinking}},
            response_format={"type": "json_object"},
        )
        self.intent_config = types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=2400,
        )
        self.presentation_config = types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=500,
        )
        self.planner_config = types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=900,
        )
        self.intent_agent = self._build_intent_agent()
        self.intent_runner = self._runner(self.intent_agent, f"{settings.app_name}-intent")
        self.question_presenter = self._build_question_presenter()
        self.question_runner = self._runner(
            self.question_presenter,
            f"{settings.app_name}-question-presenter",
        )
        self.infeasibility_questioner = self._build_infeasibility_questioner()
        self.infeasibility_question_runner = self._runner(
            self.infeasibility_questioner,
            f"{settings.app_name}-constraint-negotiator",
        )

    def _runner(self, agent: Agent, app_name: str | None = None) -> Runner:
        return Runner(
            app_name=app_name or self.settings.app_name,
            agent=agent,
            session_service=self.session_service,
            memory_service=self.memory_service,
            auto_create_session=True,
        )

    def _build_intent_agent(self) -> Agent:
        catalog_payload = self.catalog.model_dump(mode="json")
        retrieval_payload = self.query_orchestrator.protocol_description()
        intent_schema = json.dumps(
            IntentFrame.model_json_schema(), ensure_ascii=False, separators=(",", ":")
        )
        instruction = f"""
You are IntentGovernor for an intent-to-fulfillment local-life agent. Infer the
user's desired outcome and the minimum provider capabilities needed to achieve it.
Reason semantically from the whole task and conversation; never route by keyword,
surface category, or a fixed example lookup.

Choose path=quick for one independently fulfillable capability; choose orchestrated when
capabilities, constraints or fallbacks interact. Both paths produce a complete
GoalContract and use live supply.

The provider publishes this runtime capability catalog:
{json.dumps(catalog_payload, ensure_ascii=False, separators=(",", ":"))}

The catalog and its decision_policy define the product boundary. Select the minimum
published capabilities that create evidence or commitments protecting the outcome.
Mobility is relevant for an explicit ride/navigation result or when route evidence is
needed to prove a walking, arrival or tightly timed multi-location constraint—not merely
because a default origin differs from a venue.

Ask one question only when plausible answers change capabilities, feasibility, a hard
boundary, destination or authorization. Clarification offers 2-4 outcome-level options,
each with a matching counterfactual branch, the complete branch capabilities, temporal
constraints and query plan. goal_patch contains only branch differences; choose a safe,
reversible default. The runtime grounds every branch. Do not combine mutually exclusive
outcome hypotheses into one mandatory plan. Merchant selection and details that can wait
until transaction belong to provider retrieval or editable assumptions, not a question.

Set context_scope to the narrowest stable situation supported by the conversation.
Use durable memories only when subject and scope fit; current explicit statements outrank
older memory, and contextual facts do not become global preferences.

Defaults are city={self.settings.default_city}, origin={self.settings.default_origin},
party_size={self.settings.default_party_size}, budget={self.settings.default_budget_yuan}
yuan and overall deadline=23:00; record defaults as editable assumptions. GoalContract
deadline is whole-plan completion, while event times belong to temporal_constraints.
Preserve current explicit and locked facts unless the latest message edits them. For an
unsupported or unsafe outcome, use disposition=inform with no capabilities.

Qualitative time phrases are constraints; use an editable time assumption when a clock
boundary is needed. Express ordering with starts_after. minimum_gap_minutes represents
only a user-stated buffer—provider durations come from supply evidence, and inferred
buffers stay assumptions rather than hard constraints. A mobility exact_start requires
an explicit departure time; query depart_at alone is only a retrieval lower bound.

Keep Constraint labels and context keys semantic and stable; literals belong in values.
Use capability context_schema and defer facts until the stage that requires them.

Return one IntentFrame JSON object. decision_basis contains concise decision facts and
uncertainties only unresolved decision-relevant facts. A proceed query_plan covers every selected
capability using its published read entry tools and exact input schemas; clarification
puts the corresponding query plan on each branch. Mobility endpoints need resolvable
places or known districts rather than generic category nouns.
The provider-published retrieval interfaces are:
{json.dumps(retrieval_payload, ensure_ascii=False, separators=(",", ":"))}

Behavioral demonstrations below illustrate the decision principles. Generalize the
reasoning; never copy their literal places, times, capabilities or option labels.

Example A
User: “今晚想让自己状态好一点，但还没想好怎么过。”
Decision: disposition=clarify. Create mutually exclusive outcome branches such as quiet
recovery versus fresh stimulation, each with only the capabilities needed by that
outcome. Do not combine every plausible branch into one mandatory plan.

Example B
User: “今晚想安静吃顿饭，具体哪家你来选。”
Decision: disposition=proceed with the minimum dining capability and provider retrieval.
The unknown merchant is the point of retrieval, not a reason to ask the user.

Example C
User: “19:00在望京吃饭，20:45在CBD看演出，23:00前结束，尽量少走路。”
Decision: disposition=proceed with the two commitments and one mobility transition
between their locations. Preserve both exact starts and the overall deadline. The route
starts after the first commitment with zero invented gap and must finish before the
second. Because merchants are selected in parallel, query mobility with origin=望京,
destination=CBD and depart_at=19:00—not a generic endpoint such as “restaurant” or
“venue”. Do not add a route after the final commitment unless the user asks for one.

Example D
User: “做完头发后休息20分钟再去吃饭。”
Decision: the later commitment starts_after the earlier one with
minimum_gap_minutes=20, citing the explicit user fact. Here the gap is real because the
user stated it, unlike an inferred safety buffer.

Use the exact schema below. `goal` is the complete shared
GoalContract object, `capability_ids` is the only capability field, and `message` is
always a string. Do not add aliases such as capabilities or capabilities_needed:
{intent_schema}
"""
        return Agent(
            name="intent_governor",
            description="Produces a typed intent, uncertainty, and capability decision.",
            model=self.model,
            instruction=instruction,
            output_schema=IntentFrame,
            generate_content_config=self.intent_config,
        )

    def _build_question_presenter(self) -> Agent:
        schema = json.dumps(
            QuestionPresentation.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return Agent(
            name="question_presenter",
            description="Translates grounded branch divergence into one user-level choice.",
            model=self.model,
            instruction=f"""
You present one necessary clarification after the system has already grounded and solved
all counterfactual branches. Translate internal branch methods into the lived result the
user is choosing: emotional state, social energy, recovery, novelty, pace, control, or
another outcome evident in the original request.

labels maps every supplied option_id to one short, mutually exclusive desired end state.
A label must describe why the user wants the plan, never what they buy or which provider
category, merchant, service, activity, tool, capability or inventory fulfills it. Do not
list concrete examples. prompt asks about the outcome distinction. why_now explains the
user-visible change in the resulting plan, without mentioning internal abilities,
routing, services, supply domains or system mechanics. Preserve every option id exactly.
Address the user consistently as “你”; never switch to the formal “您”.
Return only one QuestionPresentation JSON object matching: {schema}
""",
            tools=[],
            output_schema=QuestionPresentation,
            generate_content_config=self.presentation_config,
        )

    def _build_infeasibility_questioner(self) -> Agent:
        schema = json.dumps(
            RecoveryPresentation.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return Agent(
            name="constraint_negotiator",
            description="Explains a solver-certified set of concrete recovery choices.",
            model=self.model,
            instruction=f"""
The input already contains 2-4 mutually exclusive, solver-proved recovery branches with
immutable labels and impacts. Do not create, edit, rank or remove branches. Write one
concise prompt asking which concrete boundary the user accepts, and one why_now sentence
that explains the real-life conflict. Use ordinary life language; never mention solvers,
capabilities, routing, tools or internal mechanics. Do not repeat all options in the
prompt. Address the user as “你”, never “您”.

Return exactly one RecoveryPresentation JSON object matching: {schema}
""",
            tools=[],
            output_schema=RecoveryPresentation,
            generate_content_config=self.presentation_config,
        )

    def _build_planner(self, frame: IntentFrame) -> Agent:
        selected = self.catalog.select(frame.capability_ids)
        capability_context = [item.model_dump(mode="json") for item in selected]
        decision_schema = json.dumps(
            CandidateSelection.model_json_schema(), ensure_ascii=False, separators=(",", ":")
        )
        return Agent(
            name="life_goal_planner",
            description="Builds one grounded and authorizable plan for a typed life goal.",
            model=self.model,
            instruction=f"""
You are LifeGoalPlanner. IntentGovernor has already resolved the semantic intent and
selected the minimum published capabilities. The selected capability definitions are:
{json.dumps(capability_context, ensure_ascii=False, separators=(",", ":"))}

The input contains a feasible_plan_set produced by a constraint solver from concurrent
live MCP supply. Every candidate already satisfies capacity, total budget, time windows,
non-overlap, capability commitment counts and the overall completion deadline. The
pareto_supply object hydrates only Pareto candidates with grounded names, tags, ratings
and evidence. Treat both as authoritative. Do not imitate tools, change times, invent
supply, or construct a combination outside the supplied candidate ids.

Make the semantic judgment inside that certified frontier. Select exactly one
candidate_id from pareto_candidate_ids. Optionally retain at most two different Pareto
candidate ids as alternatives when they expose genuinely different user-facing
tradeoffs. Use selection_reasons keyed by exact option_id to explain why each chosen
commitment advances this user's outcome. Do not use a fixed scoring formula: interpret
preferences, context, evidence and the user's latest edit holistically.

When plan_edit exists, treat it as the exact requested edit scope. locked_node_ids are
user-owned commitments.
Prefer a Pareto candidate that preserves them and the requested scope; never claim to
preserve a node when its option or time changes. Preserve completed commitments during
replanning. Never invent venues, sessions, routes, receipts, discounts or availability.
No external action occurs in this turn: mandate and payment confirmation happen later.

Emit preference_evidence only for a preference the user explicitly expressed or an
actual choice they made in this decision turn. Each record must preserve task_id and
context_scope from the input. Do not turn assumptions,
retrieval evidence, model suggestions, or an unused alternative into user facts. Existing
durable memories influence selection but must not be emitted again as new evidence.

Return exactly one CandidateSelection JSON object with title, candidate_id,
selection_reasons and optional alternative_candidate_ids. Use only the properties in:
{decision_schema}
""",
            tools=[],
            output_schema=CandidateSelection,
            generate_content_config=self.planner_config,
        )

    async def _query_supply(
        self,
        task: TaskSnapshot,
        frame: IntentFrame,
        *,
        record_traces: bool = True,
    ) -> dict[str, CapabilityEvidence]:
        evidence = await self.query_orchestrator.resolve(
            frame.query_plan,
            frame.capability_ids,
        )
        definitions = {item.id: item for item in self.catalog.select(frame.capability_ids)}
        for capability_id, report in evidence.items():
            if record_traces:
                await self.tasks.record_progress(
                    task,
                    kind="retrieval_completed",
                    detail=(
                        f"{definitions[capability_id].display_name}返回 "
                        f"{len(report.candidates)} 条已核验供给"
                    ),
                    capability_id=capability_id,
                )
            for call in report.calls:
                if not record_traces:
                    continue
                await self.tasks.record_trace(
                    task,
                    ToolTrace(
                        agent="capability_query_orchestrator",
                        tool=call.tool_name,
                        input_summary=call.arguments,
                        status=(
                            "failed"
                            if call.status in {"invalid_query", "no_supply", "stale_version"}
                            else "succeeded"
                        ),
                        result_summary=(
                            f"返回 {call.item_count} 条供给"
                            if call.item_count
                            else f"状态：{call.status}"
                        ),
                        world_version=call.world_version,
                        duration_ms=call.duration_ms,
                    ),
                )
        return evidence

    def _grounded_candidate_sets(
        self,
        frame: IntentFrame,
        reports: dict[str, CapabilityEvidence],
    ) -> list[GroundedCandidateSet]:
        definitions = {item.id: item for item in self.catalog.select(frame.capability_ids)}
        return [
            GroundedCandidateSet(
                capability_id=capability_id,
                consumes_user_time=definitions[capability_id].planning.consumes_user_time,
                trigger_kind=definitions[capability_id].planning.trigger_kind,
                location_bound=definitions[capability_id].planning.location_bound,
                provides_transition_evidence=(
                    definitions[capability_id].planning.provides_transition_evidence
                ),
                minimum_commitments=(
                    definitions[capability_id].planning.minimum_commitments
                ),
                maximum_commitments=(
                    definitions[capability_id].planning.maximum_commitments
                ),
                candidates=[
                    candidate
                    for candidate in report.candidates
                    if all(
                        field in candidate.metadata
                        for field in definitions[
                            capability_id
                        ].planning.required_evidence_fields
                    )
                ],
            )
            for capability_id, report in reports.items()
        ]

    @staticmethod
    def _pareto_supply_context(
        feasible_set: FeasiblePlanSet,
        options: dict[str, SupplyOption],
    ) -> dict[str, list[dict[str, Any]]]:
        pareto = set(feasible_set.pareto_candidate_ids)
        return {
            candidate.id: [
                {
                    "option_id": selection.option_id,
                    "name": options[selection.option_id].name,
                    "tags": options[selection.option_id].tags,
                    "rating": options[selection.option_id].rating,
                    "availability": options[selection.option_id].availability,
                    "evidence": options[selection.option_id].evidence.model_dump(mode="json"),
                }
                for selection in candidate.selections
            ]
            for candidate in feasible_set.candidates
            if candidate.id in pareto
        }

    async def _ground_clarification(
        self,
        task: TaskSnapshot,
        frame: IntentFrame,
    ) -> tuple[IntentFrame, dict[str, CapabilityEvidence]] | ClarificationQuestion:
        async def ground(branch: CounterfactualBranch):
            branch_goal = branch.goal_patch.apply(frame.goal)
            branch_frame = IntentFrame(
                disposition=IntentDisposition.PROCEED,
                goal=branch_goal,
                capability_ids=branch.capability_ids,
                temporal_constraints=branch.temporal_constraints,
                query_plan=branch.query_plan,
                decision_basis=frame.decision_basis,
                uncertainties=[],
                message="反事实分支供给核验",
            )
            reports = await self._query_supply(
                task,
                branch_frame,
                record_traces=False,
            )
            feasible = self.planning.solve(
                branch_goal,
                self._grounded_candidate_sets(branch_frame, reports),
                branch.temporal_constraints,
            )
            return branch, branch_frame, reports, feasible

        grounded = await asyncio.gather(*(
            ground(branch) for branch in frame.counterfactual_branches
        ))
        fingerprints: dict[str, tuple[Any, ...]] = {}
        impacts: dict[str, str] = {}
        for branch, _, _, feasible in grounded:
            pareto = set(feasible.pareto_candidate_ids)
            fingerprints[branch.option_id] = (
                tuple(branch.capability_ids),
                feasible.status,
                tuple(sorted(
                    tuple(
                        (item.capability_id, item.option_id, item.starts_at, item.ends_at)
                        for item in candidate.selections
                    )
                    for candidate in feasible.candidates
                    if candidate.id in pareto
                )),
            )
            if feasible.status == "feasible":
                candidates = [
                    item for item in feasible.candidates if item.id in pareto
                ]
                low = min(item.objectives.total_yuan for item in candidates)
                high = max(item.objectives.total_yuan for item in candidates)
                impacts[branch.option_id] = (
                    f"已核验 {len(candidates)} 个可行方向，"
                    f"预算区间 ¥{low}" + (f"–¥{high}" if high != low else "")
                )
            else:
                impacts[branch.option_id] = "；".join(
                    item.message for item in feasible.infeasible_reasons
                ) or "当前供给未得到可证明的可行组合"

        if len(set(fingerprints.values())) > 1:
            assert frame.question is not None
            grounded_by_id = {
                branch.option_id: (branch, branch_frame, reports, feasible)
                for branch, branch_frame, reports, feasible in grounded
            }
            grounded_question = ClarificationQuestion(
                prompt=frame.question.prompt,
                why_now=frame.question.why_now,
                options=[
                    ClarificationOption(
                        id=option.id,
                        label=option.label,
                        impact=impacts[option.id],
                        branch=DecisionBranch(
                            goal=grounded_by_id[option.id][1].goal,
                            capability_ids=grounded_by_id[option.id][0].capability_ids,
                            temporal_constraints=(
                                grounded_by_id[option.id][0].temporal_constraints
                            ),
                            path=grounded_by_id[option.id][1].path.value,
                            context_scope=frame.context_scope,
                            feasibility_status=grounded_by_id[option.id][3].status,
                            verified_candidate_ids={
                                capability_id: [item.id for item in report.candidates]
                                for capability_id, report
                                in grounded_by_id[option.id][2].items()
                            },
                            verified_candidates={
                                capability_id: [
                                    item.model_copy(deep=True)
                                    for item in report.candidates
                                ]
                                for capability_id, report
                                in grounded_by_id[option.id][2].items()
                            },
                        ),
                    )
                    for option in frame.question.options
                ],
                allow_free_text=True,
            )
            return await self._present_grounded_question(
                task,
                frame,
                grounded_question,
            )

        default_id = frame.default_branch_option_id
        selected = next(item for item in grounded if item[0].option_id == default_id)
        return selected[1], selected[2]

    async def _present_grounded_question(
        self,
        task: TaskSnapshot,
        frame: IntentFrame,
        question: ClarificationQuestion,
    ) -> ClarificationQuestion:
        prompt = {
            "original_goal": frame.goal.outcome,
            "decision_facts": frame.decision_basis,
            "branches": [
                {
                    "option_id": branch.option_id,
                    "branch_outcome": branch.goal_patch.apply(frame.goal).outcome,
                    "preferences": branch.goal_patch.apply(frame.goal).preferences,
                    "grounded_impact": next(
                        item.impact
                        for item in question.options
                        if item.id == branch.option_id
                    ),
                }
                for branch in frame.counterfactual_branches
            ],
            "instruction": (
                "Express only the desired life-result distinction. Preserve each option id."
            ),
        }
        session_id = f"{task.id}-question-presenter"
        text = await self._run_agent(
            self.question_runner,
            self.question_presenter.name,
            task,
            session_id,
            prompt,
            record_traces=True,
        )
        presentation = QuestionPresentation.model_validate_json(
            extract_json_object(text)
        )
        option_ids = {item.id for item in question.options}
        if set(presentation.labels) != option_ids:
            raise ValueError("question presentation must preserve every branch option id")
        presented = question.model_copy(update={
            "prompt": presentation.prompt,
            "why_now": presentation.why_now,
            "options": [
                option.model_copy(update={
                    "label": presentation.labels[option.id],
                })
                for option in question.options
            ],
        }, deep=True)
        return presented

    async def _present_infeasibility_question(
        self,
        task: TaskSnapshot,
        frame: IntentFrame,
        feasible_set: FeasiblePlanSet,
        reports: dict[str, CapabilityEvidence],
    ) -> ClarificationQuestion:
        candidate_sets = self._grounded_candidate_sets(frame, reports)
        recoveries = self.planning.recover(
            frame.goal,
            candidate_sets,
            frame.temporal_constraints,
            feasible_set,
        )
        verified_ids = {
            capability_id: [item.id for item in report.candidates]
            for capability_id, report in reports.items()
        }
        verified_candidates = {
            capability_id: [item.model_copy(deep=True) for item in report.candidates]
            for capability_id, report in reports.items()
        }
        options = [
            {
                "id": f"recovery_{index + 1}",
                "label": recovery.label,
                "impact": recovery.impact,
                "branch": DecisionBranch(
                    goal=recovery.goal,
                    capability_ids=list(frame.capability_ids),
                    temporal_constraints=recovery.temporal_constraints,
                    path=frame.path.value,
                    context_scope=frame.context_scope,
                    feasibility_status=recovery.feasible_set.status,
                    verified_candidate_ids=verified_ids,
                    verified_candidates=verified_candidates,
                ),
            }
            for index, recovery in enumerate(recoveries)
        ]
        options.append({
            "id": "keep_and_pause",
            "label": "保持现在的要求，先暂停这次安排",
            "impact": "不放宽任何边界，也不会进行预约、购券或下单。",
            "branch": DecisionBranch(
                action="stop",
                goal=frame.goal.model_copy(deep=True),
                capability_ids=[],
                temporal_constraints=frame.temporal_constraints,
                path=frame.path.value,
                context_scope=frame.context_scope,
                feasibility_status="infeasible",
            ),
        })
        if len(options) == 1:
            options.insert(0, {
                "id": "revise_boundary",
                "label": "换一个时间或地点再告诉我",
                "impact": "当前供给没有可证明的最小单项调整，需要你提供新的边界。",
                "branch": DecisionBranch(
                    action="stop",
                    goal=frame.goal.model_copy(deep=True),
                    capability_ids=[],
                    temporal_constraints=frame.temporal_constraints,
                    path=frame.path.value,
                    context_scope=frame.context_scope,
                    feasibility_status="infeasible",
                ),
            })
        prompt = {
            "solver_conflicts": [
                item.model_dump(mode="json")
                for item in feasible_set.infeasible_reasons
            ],
            "fixed_options": [
                {"id": item["id"], "label": item["label"], "impact": item["impact"]}
                for item in options
            ],
            "instruction": "Explain why one of these already-proved boundary choices is needed.",
        }
        session_id = f"{task.id}-constraint-negotiation"
        text = await self._run_agent(
            self.infeasibility_question_runner,
            self.infeasibility_questioner.name,
            task,
            session_id,
            prompt,
            record_traces=True,
        )
        presentation = RecoveryPresentation.model_validate_json(extract_json_object(text))
        return ClarificationQuestion(
            prompt=presentation.prompt,
            why_now=presentation.why_now,
            options=options,
            allow_free_text=True,
        )

    async def decide(self, task: TaskSnapshot, user_message: str) -> AgentTurn:
        memories = await self.tasks.preferences.relevant(
            task.user_id,
            context_scope=task.context_scope,
            query=user_message,
        )
        frame = await self._interpret(task, user_message, memories)
        return await self._decide_frame(task, user_message, memories, frame)

    async def decide_branch(
        self,
        task: TaskSnapshot,
        branch: DecisionBranch,
        selection_label: str,
    ) -> AgentTurn:
        if branch.action != "continue":
            raise ValueError("only continuing branches can enter planning")
        memories = await self.tasks.preferences.relevant(
            task.user_id,
            context_scope=branch.context_scope,
            query=f"{selection_label} {branch.goal.outcome}",
        )
        frame = IntentFrame(
            disposition=IntentDisposition.PROCEED,
            path=IntentPath(branch.path),
            context_scope=branch.context_scope,
            goal=branch.goal,
            capability_ids=branch.capability_ids,
            temporal_constraints=branch.temporal_constraints,
            decision_basis=[f"用户选择已验证决策分支：{selection_label}"],
            message=selection_label,
        )
        reports: dict[str, CapabilityEvidence] | None = None
        if branch.feasibility_status == "feasible" and branch.verified_candidates:
            reports = {
                capability_id: CapabilityEvidence(
                    capability_id=capability_id,
                    candidates=[item.model_copy(deep=True) for item in options],
                )
                for capability_id, options in branch.verified_candidates.items()
            }
            if set(reports) != set(branch.capability_ids):
                reports = None
        elif branch.feasibility_status == "feasible" and branch.verified_candidate_ids:
            hydrated: dict[str, CapabilityEvidence] = {}
            for capability_id, option_ids in branch.verified_candidate_ids.items():
                options = [await self.planning.supply.get(option_id) for option_id in option_ids]
                if any(option is None for option in options):
                    hydrated = {}
                    break
                hydrated[capability_id] = CapabilityEvidence(
                    capability_id=capability_id,
                    candidates=[option for option in options if option is not None],
                )
            if set(hydrated) == set(branch.capability_ids):
                reports = hydrated
        if reports is None:
            refreshed = await self._interpret(task, selection_label, memories)
            if set(refreshed.capability_ids) != set(branch.capability_ids):
                raise ValueError("selected branch no longer maps to the same capabilities")
            frame.query_plan = refreshed.query_plan
        return await self._decide_frame(
            task,
            selection_label,
            memories,
            frame,
            reports=reports,
        )

    async def _decide_frame(
        self,
        task: TaskSnapshot,
        user_message: str,
        memories: list[Any],
        frame: IntentFrame,
        *,
        reports: dict[str, CapabilityEvidence] | None = None,
    ) -> AgentTurn:
        await self.tasks.record_progress(
            task,
            kind="goal_understood",
            detail=(
                f"已形成目标契约，并选择 {len(frame.capability_ids)} 项最小供给能力"
                if frame.capability_ids
                else "已形成目标契约，正在判断一个关键分歧"
            ),
        )
        task.context_scope = frame.context_scope
        memories = await self.tasks.preferences.relevant(
            task.user_id,
            context_scope=frame.context_scope,
            query=f"{user_message} {frame.goal.outcome} {' '.join(frame.goal.preferences)}",
        )
        self.catalog.select(frame.capability_ids)
        if frame.disposition == IntentDisposition.CLARIFY:
            task = await self.tasks.set_phase(task, TaskPhase.RETRIEVING)
            grounded = await self._ground_clarification(task, frame)
            if isinstance(grounded, ClarificationQuestion):
                return AgentTurn(
                    kind=TurnKind.CLARIFY,
                    message=f"这个选择会改变最终安排：{grounded.why_now}",
                    goal=frame.goal,
                    intent_path=frame.path.value,
                    question=grounded,
                )
            frame, reports = grounded
        elif frame.disposition == IntentDisposition.INFORM:
            return AgentTurn(
                kind=TurnKind.INFORM,
                message=frame.message,
                goal=frame.goal,
                intent_path=frame.path.value,
            )

        if reports is not None:
            await self.tasks.record_progress(
                task,
                kind="retrieval_started",
                detail="已复用这个选择刚刚核验过的供给，直接重新组合方案",
            )
        if reports is None:
            task = await self.tasks.set_phase(task, TaskPhase.RETRIEVING)
            await self.tasks.record_progress(
                task,
                kind="retrieval_started",
                detail=f"正在核验：{', '.join(frame.capability_ids)}",
            )
            reports = await self._query_supply(task, frame)
        grounded_candidate_sets = self._grounded_candidate_sets(frame, reports)
        supply_evidence = {
            option.id: option
            for candidate_set in grounded_candidate_sets
            for option in candidate_set.candidates
        }
        feasible_set = self.planning.solve(
            frame.goal,
            grounded_candidate_sets,
            frame.temporal_constraints,
        )
        if feasible_set.status == "infeasible" and frame.path == IntentPath.ORCHESTRATED:
            conflict = "；".join(
                item.message for item in feasible_set.infeasible_reasons
            )
            await self.tasks.record_progress(
                task,
                kind="feasibility_conflict",
                detail=f"当前组合冲突：{conflict}；正在准备一个最小调整选择",
            )
        if feasible_set.status != "feasible":
            detail = "；".join(item.message for item in feasible_set.infeasible_reasons)
            await self.tasks.record_progress(
                task,
                kind="feasibility_conflict",
                detail=detail or "供给组合未通过硬约束验证",
            )
            question = await self._present_infeasibility_question(
                task,
                frame,
                feasible_set,
                reports,
            )
            return AgentTurn(
                kind=TurnKind.CLARIFY,
                message=question.why_now,
                goal=frame.goal,
                intent_path=frame.path.value,
                feasible_plan_set=feasible_set,
                question=question,
            )
        task = await self.tasks.set_phase(task, TaskPhase.COMPOSING)
        await self.tasks.record_progress(
            task,
            kind="composing_plan",
            detail=f"正在比较 {len(feasible_set.pareto_candidate_ids)} 个价格与时间都可行的方向",
        )
        planner = self._build_planner(frame)
        runner = self._runner(planner)
        session_id = f"{task.id}-plan"
        pareto_ids = set(feasible_set.pareto_candidate_ids)
        prompt = {
            "task_id": task.id,
            "latest_user_message": user_message,
            "goal": {
                "outcome": frame.goal.outcome,
                "preferences": frame.goal.preferences,
                "context_scope": frame.context_scope,
            },
            "plan_edit": (
                task.pending_plan_edit.model_dump(mode="json")
                if task.pending_plan_edit else None
            ),
            "locked_node_ids": (
                task.policy.primary_plan.locked_node_ids
                if task.policy else []
            ),
            "pareto_candidates": [
                item.model_dump(mode="json")
                for item in feasible_set.candidates
                if item.id in pareto_ids
            ],
            "pareto_supply": self._pareto_supply_context(
                feasible_set,
                supply_evidence,
            ),
            "durable_memories": [item.model_dump(mode="json") for item in memories],
            "instruction": "Synthesize the grounded reports into one decision turn.",
        }
        final_text = await self._run_agent(
            runner, planner.name, task, session_id, prompt, record_traces=True
        )
        try:
            decision = CandidateSelection.model_validate_json(extract_json_object(final_text))
            turn = await materialize_candidate_selection(
                frame,
                decision,
                self.planning,
                feasible_set,
                supply_evidence=supply_evidence,
            )
        except (ValidationError, ValueError) as exc:
            return await self._repair_plan(
                runner,
                planner.name,
                task,
                session_id,
                frame,
                feasible_set,
                [f"CandidateSelection error: {exc}"],
                supply_evidence,
            )
        if turn.kind == TurnKind.PROPOSE and turn.policy is not None:
            validation = await self.planning.validate(turn.policy.primary_plan)
            if not validation.valid:
                issues = [
                    f"{item.code}: {item.message}"
                    + (f" (node={item.node_id})" if item.node_id else "")
                    for item in validation.issues
                ]
                return await self._repair_plan(
                    runner,
                    planner.name,
                    task,
                    session_id,
                    frame,
                    feasible_set,
                    issues,
                    supply_evidence,
                )
        return turn

    async def _interpret(
        self, task: TaskSnapshot, message: str, memories: list[Any]
    ) -> IntentFrame:
        prompt = {
            "current_task": decision_context(task),
            "latest_user_message": message,
            "durable_memories": [item.model_dump(mode="json") for item in memories],
            "instruction": "Produce the semantic IntentFrame for this decision turn.",
        }
        session_id = f"{task.id}-intent"
        final_text = await self._run_agent(
            self.intent_runner,
            self.intent_agent.name,
            task,
            session_id,
            prompt,
            record_traces=True,
        )
        try:
            frame = IntentFrame.model_validate_json(extract_json_object(final_text))
            self._validate_intent_frame(frame)
            return frame
        except (ValidationError, ValueError) as exc:
            repair = {
                "validation_issue": str(exc),
                "instruction": (
                    "Repair the immediately preceding IntentFrame once. Select only ids "
                    "from the published catalog and return one complete IntentFrame."
                ),
            }
            repaired = await self._run_agent(
                self.intent_runner,
                self.intent_agent.name,
                task,
                session_id,
                repair,
                record_traces=True,
            )
            frame = IntentFrame.model_validate_json(extract_json_object(repaired))
            self._validate_intent_frame(frame)
            return frame

    def _validate_intent_frame(self, frame: IntentFrame) -> None:
        def validate_temporal_references(
            capability_ids: list[str],
            temporal_constraints: list[TemporalConstraint],
        ) -> None:
            selected = self.catalog.select(capability_ids)
            selected_ids = {capability.id for capability in selected}
            invalid_dependencies = [
                constraint
                for constraint in temporal_constraints
                if constraint.relation == "starts_after"
                and (
                    constraint.capability_id not in selected_ids
                    or constraint.reference_capability_id not in selected_ids
                )
            ]
            if invalid_dependencies:
                raise ValueError(
                    "temporal dependencies must reference selected capabilities"
                )

        validate_temporal_references(frame.capability_ids, frame.temporal_constraints)
        if frame.disposition == IntentDisposition.PROCEED:
            self.query_orchestrator.validate_plan(
                frame.query_plan,
                frame.capability_ids,
            )
        for branch in frame.counterfactual_branches:
            validate_temporal_references(
                branch.capability_ids,
                branch.temporal_constraints,
            )
            self.query_orchestrator.validate_plan(
                branch.query_plan,
                branch.capability_ids,
            )

    async def _repair_plan(
        self,
        runner: Runner,
        author: str,
        task: TaskSnapshot,
        session_id: str,
        frame: IntentFrame,
        feasible_set: FeasiblePlanSet,
        issues: list[str],
        supply_evidence: dict[str, SupplyOption] | None = None,
    ) -> AgentTurn:
        prompt = {
            "validation_issues": issues,
            "instruction": (
                "Repair the immediately preceding CandidateSelection exactly once. Reuse the typed "
                "feasible Pareto set already supplied in this planner session and change only what "
                "the issues require."
            ),
        }
        text = await self._run_agent(
            runner, author, task, session_id, prompt, record_traces=True
        )
        decision = CandidateSelection.model_validate_json(extract_json_object(text))
        repaired = await materialize_candidate_selection(
            frame,
            decision,
            self.planning,
            feasible_set,
            supply_evidence=supply_evidence,
        )
        if repaired.kind == TurnKind.PROPOSE and repaired.policy is not None:
            validation = await self.planning.validate(repaired.policy.primary_plan)
            if not validation.valid:
                detail = "; ".join(item.message for item in validation.issues)
                raise ValueError(f"agent repair produced an invalid plan: {detail}")
        return repaired

    async def _run_agent(
        self,
        runner: Runner,
        final_author: str,
        task: TaskSnapshot,
        session_id: str,
        prompt: dict[str, Any],
        *,
        record_traces: bool,
    ) -> str:
        message = types.Content(
            role="user",
            parts=[types.Part(text=json.dumps(prompt, ensure_ascii=False, default=str))],
        )
        final_text = ""
        started = time.perf_counter()
        first_event_ms: int | None = None
        usage: dict[str, int] = {}
        try:
            async with asyncio.timeout(self.settings.decision_llm_timeout_seconds):
                async for event in runner.run_async(
                    user_id=task.user_id,
                    session_id=session_id,
                    new_message=message,
                    run_config=RunConfig(max_llm_calls=1),
                ):
                    if first_event_ms is None and (event.content or event.usage_metadata):
                        first_event_ms = int((time.perf_counter() - started) * 1000)
                    if event.usage_metadata is not None:
                        metadata = event.usage_metadata
                        usage = {
                            "prompt_tokens": metadata.prompt_token_count or 0,
                            "output_tokens": metadata.candidates_token_count or 0,
                            "cached_tokens": metadata.cached_content_token_count or 0,
                            "total_tokens": metadata.total_token_count or 0,
                        }
                    if (
                        event.author == final_author
                        and not event.get_function_calls()
                        and not event.get_function_responses()
                        and event.is_final_response()
                        and event.content
                    ):
                        final_text = "".join(
                            part.text or "" for part in event.content.parts or []
                        )
        except Exception:
            if record_traces:
                await self.tasks.record_trace(
                    task,
                    ToolTrace(
                        agent=final_author,
                        tool="deepseek.generate",
                        input_summary={
                            "stage": final_author,
                            "prompt_chars": len(message.parts[0].text or ""),
                        },
                        status="failed",
                        result_summary="模型生成失败",
                        duration_ms=int((time.perf_counter() - started) * 1000),
                    ),
                )
            raise
        if not final_text:
            raise RuntimeError("model completed without the required typed response")
        if record_traces:
            await self.tasks.record_trace(
                task,
                ToolTrace(
                    agent=final_author,
                    tool="deepseek.generate",
                    input_summary={
                        "stage": final_author,
                        "prompt_chars": len(message.parts[0].text or ""),
                        "first_event_ms": first_event_ms or 0,
                        **usage,
                    },
                    status="succeeded",
                    result_summary=(
                        f"生成 {usage.get('output_tokens', 0)} tokens"
                        if usage else "模型生成完成"
                    ),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                ),
            )
        return final_text

    async def close(self) -> None:
        await self.query_orchestrator.close()
