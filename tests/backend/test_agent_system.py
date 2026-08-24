import json
import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from backend.agent.system import (
    CounterfactualBranch,
    CounterfactualGoalPatch,
    IntentClarification,
    IntentClarificationOption,
    IntentDisposition,
    IntentFrame,
    IntentPath,
    CandidateSelection,
    RecoveryPresentation,
    decision_context,
    extract_json_object,
    materialize_candidate_selection,
)
from backend.config import Settings
from backend.domain.models import (
    ChatMessage,
    ClarificationOption,
    ClarificationQuestion,
    DecisionBranch,
    FeasiblePlanCandidate,
    FeasiblePlanSet,
    FeasibleSelection,
    GoalContract,
    InfeasibleReason,
    PlanObjectiveVector,
    TaskSnapshot,
    TemporalConstraint,
    ToolTrace,
    TurnKind,
    utc_now,
)
from backend.mcp import (
    CapabilityEvidence,
    CapabilityQueryOrchestrator,
    CapabilityQueryPlan,
    CapabilityToolQuery,
    load_capability_catalog,
)
from backend.mcp.schemas import ToolEnvelope
from backend.planning.recovery import RecoveryCandidate


class StaticToolPort:
    def __init__(self, responses=None, *, delay: float = 0) -> None:
        self.responses = responses or {}
        self.delay = delay
        self.calls = []
        self.schemas = {
            tool: {
                "name": tool,
                "description": "test tool",
                "input_schema": {"type": "object", "additionalProperties": True},
            }
            for capability in load_capability_catalog().capabilities
            for tool in capability.retrieval.entry_tools
        }

    async def start(self) -> None:
        return None

    async def list_tools(self):
        return self.schemas

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.responses[name]

    async def close(self) -> None:
        return None


async def make_engine(world, planning, *, port=None):
    from google.adk.sessions import InMemorySessionService

    from backend.agent.system import GoogleAdkDecisionEngine
    from backend.memory import PostgresMemoryService
    from backend.tasks import TaskModule

    query = CapabilityQueryOrchestrator(
        load_capability_catalog(),
        port or StaticToolPort(),
    )
    await query.start()
    return GoogleAdkDecisionEngine(
        settings=Settings(_env_file=None, use_in_memory_store=True),
        planning=planning,
        tasks=TaskModule(world.store, planning),
        session_service=InMemorySessionService(),
        memory_service=PostgresMemoryService(world.store),
        capability_catalog=load_capability_catalog(),
        query_orchestrator=query,
    )


def query_plan(capability_id: str, tool_name: str) -> CapabilityQueryPlan:
    return CapabilityQueryPlan(queries=[CapabilityToolQuery(
        capability_id=capability_id,
        tool_name=tool_name,
        arguments={},
    )])


def goal() -> GoalContract:
    return GoalContract(
        outcome="今晚放松一下",
        city="北京",
        origin="国贸",
        party_size=1,
        budget_yuan=500,
        deadline="23:00",
    )


def test_personal_assistant_defaults_to_one_person() -> None:
    assert Settings(_env_file=None).default_party_size == 1


def test_published_catalog_is_the_capability_selection_boundary() -> None:
    catalog = load_capability_catalog()

    selected = catalog.select(["delivery", "dining", "delivery"])

    assert [item.id for item in selected] == ["delivery", "dining"]
    with pytest.raises(ValueError, match="unpublished capabilities"):
        catalog.select(["hotel"])


def test_published_capabilities_declare_the_context_they_need() -> None:
    catalog = load_capability_catalog()

    assert all(capability.context_schema for capability in catalog.capabilities)
    assert {
        requirement.key
        for capability in catalog.capabilities
        for requirement in capability.context_schema
    } >= {"party_size", "destination", "origin"}
    assert all(
        capability.lifecycle.completion.evidence_sources
        and capability.lifecycle.completion.timezone
        for capability in catalog.capabilities
    )


def test_proceed_intent_requires_a_provider_capability() -> None:
    with pytest.raises(ValidationError, match="at least one published capability"):
        IntentFrame(
            disposition=IntentDisposition.PROCEED,
            goal=goal(),
            message="可以开始找供给",
        )


def test_quick_path_is_only_valid_for_one_capability() -> None:
    frame = IntentFrame(
        disposition=IntentDisposition.PROCEED,
        path=IntentPath.QUICK,
        goal=goal(),
        capability_ids=["delivery"],
        message="直接核验配送供给",
    )
    assert frame.path == IntentPath.QUICK

    with pytest.raises(ValidationError, match="exactly one"):
        IntentFrame(
            disposition=IntentDisposition.PROCEED,
            path=IntentPath.QUICK,
            goal=goal(),
            capability_ids=["dining", "mobility"],
            message="需要跨能力协调",
        )


def test_clarification_is_a_typed_high_leverage_decision() -> None:
    question = IntentClarification(
        prompt="你更想安静恢复，还是出去获得新鲜感？",
        why_now="答案会改变需要调用的供给能力",
        options=[
            IntentClarificationOption(id="quiet", label="安静恢复", impact="优先到店服务"),
            IntentClarificationOption(id="novel", label="新鲜体验", impact="优先休闲娱乐"),
        ],
    )
    frame = IntentFrame(
        disposition=IntentDisposition.CLARIFY,
        goal=goal(),
        message="先确认你想要的放松方式。",
        question=question,
        uncertainties=["体验方向会改变能力集合"],
        counterfactual_branches=[
            CounterfactualBranch(
                option_id="quiet",
                goal_patch=CounterfactualGoalPatch(outcome="安静恢复"),
                capability_ids=["appointments"],
                query_plan=query_plan("appointments", "service.search"),
            ),
            CounterfactualBranch(
                option_id="novel",
                goal_patch=CounterfactualGoalPatch(outcome="获得新鲜体验"),
                capability_ids=["experiences"],
                query_plan=query_plan("experiences", "activity.search"),
            ),
        ],
        default_branch_option_id="quiet",
    )

    assert frame.question == question
    assert frame.capability_ids == []


def test_clarification_cannot_dump_the_entire_capability_catalog() -> None:
    with pytest.raises(ValidationError, match="at most 4"):
        IntentClarification(
            prompt="今晚安排什么？",
            why_now="方向会改变能力集合",
            options=[
                IntentClarificationOption(
                    id=str(index), label=f"方向{index}", impact="不同供给"
                )
                for index in range(5)
            ],
        )


async def test_selected_supply_queries_run_concurrently_without_extra_llm_calls(
    world,
    planning,
) -> None:
    dining = await world.get("food_yanlan")
    delivery = await world.get("delivery_flowers_guomao")
    assert dining is not None and delivery is not None
    observed = utc_now()
    port = StaticToolPort({
        "food.search": ToolEnvelope(
            status="ok", observed_at=observed, valid_until=observed,
            world_version=1, items=[dining.model_dump(mode="json")],
        ),
        "delivery.search": ToolEnvelope(
            status="ok", observed_at=observed, valid_until=observed,
            world_version=1, items=[delivery.model_dump(mode="json")],
        ),
    }, delay=0.03)
    engine = await make_engine(world, planning, port=port)
    plan = CapabilityQueryPlan(queries=[
        CapabilityToolQuery(
            capability_id="dining", tool_name="food.search", arguments={},
        ),
        CapabilityToolQuery(
            capability_id="delivery", tool_name="delivery.search", arguments={},
        ),
    ])

    started = asyncio.get_running_loop().time()
    evidence = await engine.query_orchestrator.resolve(
        plan,
        ["dining", "delivery"],
    )
    elapsed = asyncio.get_running_loop().time() - started

    assert elapsed < 0.055
    assert [item.id for item in evidence["dining"].candidates] == [dining.id]
    assert [item.id for item in evidence["delivery"].candidates] == [delivery.id]
    with pytest.raises(ValueError, match="not a retrieval entry tool"):
        engine.query_orchestrator.validate_plan(
            CapabilityQueryPlan(queries=[CapabilityToolQuery(
                capability_id="dining",
                tool_name="delivery.search",
                arguments={},
            )]),
            ["dining"],
        )
    assert engine._build_planner(IntentFrame(
        disposition=IntentDisposition.PROCEED,
        goal=goal(),
        capability_ids=["dining"],
        query_plan=query_plan("dining", "food.search"),
        message="开始比较",
    )).tools == []

async def test_supply_query_stage_has_a_hard_deadline(world) -> None:
    dining = await world.get("food_yanlan")
    assert dining is not None
    observed = utc_now()
    orchestrator = CapabilityQueryOrchestrator(
        load_capability_catalog(),
        StaticToolPort({
            "food.search": ToolEnvelope(
                status="ok",
                observed_at=observed,
                valid_until=observed,
                world_version=1,
                items=[dining.model_dump(mode="json")],
            ),
        }, delay=0.03),
        timeout_seconds=0.01,
    )
    await orchestrator.start()

    with pytest.raises(TimeoutError):
        await orchestrator.resolve(
            query_plan("dining", "food.search"),
            ["dining"],
        )


def test_decision_context_does_not_replay_adk_or_tool_history() -> None:
    task = TaskSnapshot(
        user_id="u1",
        goal_text="安排今晚",
        messages=[ChatMessage(role="user", content=str(index)) for index in range(10)],
        tool_traces=[ToolTrace(
            agent="capability_query_orchestrator",
            tool="supply.search",
            status="succeeded",
            result_summary="ok",
            duration_ms=10,
        )],
    )

    context = decision_context(task)

    assert "tool_traces" not in context
    assert [item["content"] for item in context["messages"]] == [str(i) for i in range(2, 10)]


async def test_clarification_is_grounded_in_divergent_plan_branches(
    world,
    planning,
    monkeypatch,
) -> None:
    engine = await make_engine(world, planning)
    question = IntentClarification(
        prompt="今晚更想安静恢复，还是获得新鲜刺激？",
        why_now="两种结果会形成不同安排。",
        options=[
            IntentClarificationOption(id="recover", label="安静恢复", impact="待核验"),
            IntentClarificationOption(id="novel", label="新鲜刺激", impact="待核验"),
        ],
    )
    frame = IntentFrame(
        disposition=IntentDisposition.CLARIFY,
        goal=goal(),
        message="需要确认结果方向。",
        question=question,
        counterfactual_branches=[
            CounterfactualBranch(
                option_id="recover",
                capability_ids=["dining"],
                query_plan=query_plan("dining", "food.search"),
            ),
            CounterfactualBranch(
                option_id="novel",
                capability_ids=["experiences"],
                query_plan=query_plan("experiences", "activity.search"),
            ),
        ],
        default_branch_option_id="recover",
    )
    dining = await world.get("food_yanlan")
    experience = await world.get("activity_art_exhibition")
    assert dining is not None and experience is not None

    async def branch_reports(task, branch_frame, *, record_traces=True):
        capability_id = branch_frame.capability_ids[0]
        return {
            capability_id: CapabilityEvidence(
                capability_id=capability_id,
                candidates=[dining if capability_id == "dining" else experience],
            )
        }

    monkeypatch.setattr(engine, "_query_supply", branch_reports)
    async def keep_grounded_impacts(task, intent_frame, grounded_question):
        return grounded_question

    monkeypatch.setattr(engine, "_present_grounded_question", keep_grounded_impacts)
    grounded = await engine._ground_clarification(
        TaskSnapshot(user_id="branch-user", goal_text="今晚想放松"),
        frame,
    )

    assert isinstance(grounded, ClarificationQuestion)
    assert all("已核验" in option.impact for option in grounded.options)


async def test_infeasible_supply_becomes_an_actionable_question(
    world,
    planning,
    monkeypatch,
) -> None:
    from backend.tasks import TaskModule

    tasks = TaskModule(world.store, planning)
    engine = await make_engine(world, planning)
    engine.tasks = tasks
    frame = IntentFrame(
        disposition=IntentDisposition.PROCEED,
        path=IntentPath.ORCHESTRATED,
        goal=goal(),
        capability_ids=["appointments"],
        query_plan=query_plan("appointments", "service.search"),
        temporal_constraints=[TemporalConstraint(
            capability_id="appointments",
            relation="exact_start",
            time="19:30",
        )],
        message="开始核验按摩供给",
    )
    candidate = await world.get("service_massage_wangjing")
    assert candidate is not None
    reports = {
        "appointments": CapabilityEvidence(
            capability_id="appointments",
            candidates=[candidate],
        )
    }
    infeasible = FeasiblePlanSet(
        status="infeasible",
        infeasible_reasons=[InfeasibleReason(
            code="time_window_conflict",
            message="当前供给无法满足 19:30",
        )],
    )
    recovery = ClarificationQuestion(
        prompt="19:30 暂时约不到，你想怎么调整？",
        why_now="调整开始时间后才能形成可执行方案。",
        options=[
            ClarificationOption(id="later", label="改到 20:00", impact="当前有可约时段"),
            ClarificationOption(id="keep", label="仍要 19:30", impact="本轮不继续下单"),
        ],
    )
    monkeypatch.setattr(engine, "_interpret", AsyncMock(return_value=frame))
    monkeypatch.setattr(engine, "_query_supply", AsyncMock(return_value=reports))
    monkeypatch.setattr(engine.planning, "solve", lambda *args: infeasible)
    ask = AsyncMock(return_value=recovery)
    monkeypatch.setattr(engine, "_present_infeasibility_question", ask, raising=False)

    task = await tasks.start("recovery-user", "今晚 19:30 按摩")
    turn = await engine.decide(task, task.goal_text)

    assert turn.kind == TurnKind.CLARIFY
    assert turn.question == recovery
    assert turn.feasible_plan_set == infeasible
    ask.assert_awaited_once()


async def test_recovery_branch_cannot_drop_original_commitment_scope(
    world,
    planning,
    monkeypatch,
) -> None:
    from backend.tasks import TaskModule

    tasks = TaskModule(world.store, planning)
    engine = await make_engine(world, planning)
    engine.tasks = tasks
    frame = IntentFrame(
        disposition=IntentDisposition.PROCEED,
        path=IntentPath.ORCHESTRATED,
        context_scope="下班后独处放松",
        goal=goal(),
        capability_ids=["appointments", "mobility"],
        query_plan=CapabilityQueryPlan(queries=[
            CapabilityToolQuery(
                capability_id="appointments",
                tool_name="service.search",
                arguments={},
            ),
            CapabilityToolQuery(
                capability_id="mobility",
                tool_name="mobility.quote",
                arguments={},
            ),
        ]),
        temporal_constraints=[
            TemporalConstraint(
                capability_id="appointments",
                relation="exact_start",
                time="19:30",
            ),
            TemporalConstraint(
                capability_id="mobility",
                relation="starts_after",
                reference_capability_id="appointments",
            ),
        ],
        message="开始核验按摩和按时到家",
    )
    appointment = await world.get("service_massage_wangjing")
    mobility = await world.get("mobility_home")
    assert appointment is not None
    assert mobility is not None
    reports = {
        "appointments": CapabilityEvidence(
            capability_id="appointments",
            candidates=[appointment],
        ),
        "mobility": CapabilityEvidence(
            capability_id="mobility",
            candidates=[mobility],
        ),
    }
    infeasible = FeasiblePlanSet(
        status="infeasible",
        infeasible_reasons=[InfeasibleReason(
            code="deadline_conflict",
            message="当前组合无法在 23:00 前完成",
        )],
    )
    recovery_goal = frame.goal.model_copy(update={"deadline": "23:30"}, deep=True)
    recovery_set = FeasiblePlanSet(
        status="feasible",
        candidates=[FeasiblePlanCandidate(
            id="recovered_candidate",
            selections=[FeasibleSelection(
                capability_id="appointments",
                option_id=appointment.id,
                consumes_user_time=True,
                trigger_kind="inventory_unavailable",
                starts_at="19:30",
                ends_at="20:30",
                price_yuan=appointment.price_yuan,
            )],
            objectives=PlanObjectiveVector(
                total_yuan=appointment.price_yuan,
                completion_minute=1230,
                elapsed_minutes=60,
                movement_minutes=0,
                experience_milli=4500,
            ),
            slack_minutes=180,
        )],
        pareto_candidate_ids=["recovered_candidate"],
    )
    monkeypatch.setattr(
        engine,
        "_run_agent",
        AsyncMock(return_value=RecoveryPresentation(
            prompt="要保留按摩和返程安排，需要把最晚到家时间放宽到 23:30。",
            why_now="当前已核验的完整行程无法在 23:00 前结束。",
        ).model_dump_json()),
    )
    monkeypatch.setattr(engine.planning, "recover", lambda *args: [
        RecoveryCandidate(
            label="最晚完成改到 23:30",
            impact="这是保留当前供给组合所需的最早完成边界。",
            goal=recovery_goal,
            temporal_constraints=frame.temporal_constraints,
            feasible_set=recovery_set,
        )
    ])
    task = await tasks.start("scope-user", "今晚按摩后按时回家")

    question = await engine._present_infeasibility_question(
        task,
        frame,
        infeasible,
        reports,
    )

    branch = question.options[0].branch
    assert branch is not None
    assert branch.capability_ids == ["appointments", "mobility"]
    assert branch.context_scope == "下班后独处放松"
    assert any(
        item.relation == "starts_after"
        and item.reference_capability_id == "appointments"
        for item in branch.temporal_constraints
    )
    assert branch.feasibility_status == "feasible"
    assert branch.goal.deadline == "23:30"
    assert set(branch.verified_candidates) == {"appointments", "mobility"}


async def test_candidate_selection_is_materialized_from_supply_facts(planning) -> None:
    frame = IntentFrame(
        disposition=IntentDisposition.PROCEED,
        goal=goal(),
        capability_ids=["dining"],
        message="开始找餐厅",
    )
    decision = CandidateSelection(
        title="国贸安静晚餐",
        candidate_id="candidate_1",
        alternative_candidate_ids=["candidate_2"],
        selection_reasons={"food_yanlan": "环境安静且预算合适"},
    )
    feasible_set = FeasiblePlanSet(
        status="feasible",
        candidates=[
            FeasiblePlanCandidate(
                id="candidate_1",
                selections=[FeasibleSelection(
                    capability_id="dining",
                    option_id="food_yanlan",
                    consumes_user_time=True,
                    trigger_kind="queue_delay",
                    starts_at="19:00",
                    ends_at="20:20",
                    price_yuan=188,
                )],
                objectives=PlanObjectiveVector(
                    total_yuan=188,
                    completion_minute=1220,
                    elapsed_minutes=80,
                    movement_minutes=0,
                    experience_milli=4700,
                ),
                slack_minutes=160,
            ),
            FeasiblePlanCandidate(
                id="candidate_2",
                selections=[FeasibleSelection(
                    capability_id="dining",
                    option_id="food_nightmarket",
                    consumes_user_time=True,
                    trigger_kind="queue_delay",
                    starts_at="19:00",
                    ends_at="20:10",
                    price_yuan=146,
                )],
                objectives=PlanObjectiveVector(
                    total_yuan=146,
                    completion_minute=1210,
                    elapsed_minutes=70,
                    movement_minutes=0,
                    experience_milli=4600,
                ),
                slack_minutes=150,
            ),
        ],
        pareto_candidate_ids=["candidate_1", "candidate_2"],
    )

    turn = await materialize_candidate_selection(frame, decision, planning, feasible_set)

    assert turn.policy is not None
    node = turn.policy.primary_plan.nodes[0]
    assert node.ends_at == "20:20"
    assert node.price_yuan == 188
    assert node.venue == "宴岚·京味小馆（国贸店）"
    assert turn.policy.primary_plan.total_yuan == 188
    assert turn.policy.primary_plan.mandate.max_total_yuan == 500
    assert "¥188" in turn.message
    assert "宴岚·京味小馆" in turn.message
    assert turn.policy.alternatives[0].summary == "少花 ¥42"
    assert turn.policy.decision_points[0].fallbacks[0].replacement.option_id == "food_nightmarket"


async def test_materializer_normalizes_model_selection_order(planning) -> None:
    frame = IntentFrame(
        disposition=IntentDisposition.PROCEED,
        goal=goal(),
        capability_ids=["dining", "experiences"],
        message="开始组合",
    )
    decision = CandidateSelection(
        title="晚餐和电影",
        candidate_id="candidate_1",
        selection_reasons={
            "activity_cinema": "晚间场次",
            "food_yanlan": "安静晚餐",
        },
    )
    feasible_set = FeasiblePlanSet(
        status="feasible",
        candidates=[FeasiblePlanCandidate(
            id="candidate_1",
            selections=[
                FeasibleSelection(capability_id="dining", option_id="food_yanlan", consumes_user_time=True, trigger_kind="queue_delay", starts_at="19:00", ends_at="20:20", price_yuan=188),
                FeasibleSelection(capability_id="experiences", option_id="activity_cinema", consumes_user_time=True, trigger_kind="inventory_unavailable", starts_at="20:45", ends_at="22:43", price_yuan=116),
            ],
            objectives=PlanObjectiveVector(total_yuan=304, completion_minute=1363, elapsed_minutes=223, movement_minutes=0, experience_milli=9300),
            slack_minutes=17,
        )],
        pareto_candidate_ids=["candidate_1"],
    )

    turn = await materialize_candidate_selection(frame, decision, planning, feasible_set)

    assert turn.policy is not None
    assert [node.id for node in turn.policy.primary_plan.nodes] == ["dining", "experiences"]


def test_extract_json_object_ignores_model_classification_prefix() -> None:
    payload = {"disposition": "inform", "message": "不支持该目标"}
    text = f"[delivery, appointments]\n\n{json.dumps(payload)}"

    assert json.loads(extract_json_object(text)) == payload


def test_extract_json_object_rejects_text_without_an_object() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        extract_json_object("[delivery, appointments]")


def test_candidate_selection_rejects_primary_as_an_alternative() -> None:
    with pytest.raises(ValidationError, match="primary candidate"):
        CandidateSelection(
            title="鲜花与晚餐",
            candidate_id="candidate_1",
            alternative_candidate_ids=["candidate_1"],
            selection_reasons={"delivery_flowers": "按时送达"},
        )
