import pytest

from backend.domain.models import (
    AgentTurn,
    ClarificationOption,
    ClarificationQuestion,
    CompletionEvidence,
    DecisionBranch,
    FulfillmentEvent,
    FulfillmentCommand,
    GoalContractEdit,
    PreferenceEvidence,
    PlanEditIntent,
    PlanEditOperation,
    RealityEvent,
    TurnKind,
)
from backend.planning import PlanningModule
from backend.storage import InMemoryDocumentStore
from backend.storage import DocumentConflictError
from backend.supply import SupplyTwin
from backend.tasks import TaskModule
from tests.backend.conftest import make_plan, make_policy


async def test_task_progresses_from_clarification_to_completion(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    store = world.store
    assert isinstance(store, InMemoryDocumentStore)
    tasks = TaskModule(store, planning)
    task = await tasks.start("user-1", "今晚想和朋友放松")
    plan = await make_plan(world)

    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.CLARIFY,
        message="这个选择会影响活动类型。",
        goal=plan.goal,
        intent_path="orchestrated",
        question=ClarificationQuestion(
            prompt="今晚更想热闹地笑一场，还是安静地聊天？",
            why_now="答案会改变活动供给和用餐地点。",
            options=[
                ClarificationOption(id="laugh", label="笑一场", impact="优先喜剧演出"),
                ClarificationOption(id="quiet", label="安静聊天", impact="优先手作或电影"),
            ],
        ),
    ))
    assert task.phase.value == "clarifying"
    assert task.question is not None
    assert task.intent_path == "orchestrated"

    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="已组成一条少移动的松弛路线。",
        goal=plan.goal,
        policy=await make_policy(world),
        preference_evidence=[PreferenceEvidence(
            context_scope="social_evening",
            dimension="queue_tolerance",
            preference="少排队",
            source="explicit_expression",
            confidence=0.95,
            task_id=task.id,
        )],
    ))
    assert task.phase.value == "awaiting_mandate"
    assert (await tasks.preferences.list("user-1"))[0].preference == "少排队"

    task = await tasks.approve_mandate(task)
    assert task.phase.value == "awaiting_transaction"
    task = await tasks.confirm_transaction(task)
    assert task.phase.value == "executing"

    assert task.policy is not None
    for node in task.policy.primary_plan.nodes:
        for action in node.actions:
            task = await tasks.record_event(task, FulfillmentEvent(
                task_id=task.id,
                node_id=node.id,
                action=action,
                status="succeeded",
                detail="测试履约完成",
                receipt_id=f"receipt-{node.id}-{action.value}",
            ))
        task, _ = await tasks.record_reality_event(task, RealityEvent(
            task_id=task.id,
            kind="node_completed",
            node_id=node.id,
            detail=f"测试现实完成：{node.title}",
            completion_evidence=CompletionEvidence(
                source="provider_status",
                provider_status="completed",
                detail="供给方确认现实完成",
            ),
        ))
    assert task.phase.value == "completed"
    assert all(
        node.status.value == "completed"
        for node in task.policy.primary_plan.nodes
    )


async def test_structured_decision_applies_the_branch_without_reinterpreting_label(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("decision-user", "今晚放松一下")
    plan = await make_plan(world)
    chosen_goal = plan.goal.model_copy(update={"budget_yuan": 420}, deep=True)
    branch = DecisionBranch(
        goal=chosen_goal,
        capability_ids=["appointments"],
        path="quick",
        context_scope="独自恢复",
        feasibility_status="feasible",
        verified_candidate_ids={"appointments": ["service_massage_wangjing"]},
    )
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.CLARIFY,
        message="需要确认一个选择",
        goal=plan.goal,
        question=ClarificationQuestion(
            prompt="按哪个边界继续？",
            why_now="会改变可执行方案",
            options=[
                ClarificationOption(
                    id="verified",
                    label="按已验证分支继续",
                    impact="预算改为 420 元",
                    branch=branch,
                ),
                ClarificationOption(
                    id="stop",
                    label="保持原要求并暂停",
                    impact="本轮不继续",
                    branch=DecisionBranch(
                        action="stop",
                        goal=plan.goal,
                        context_scope="独自恢复",
                        feasibility_status="infeasible",
                    ),
                ),
            ],
        ),
    ))

    task, selected, label = await tasks.select_decision_option(task, "verified")

    assert task.goal is not None and task.goal.budget_yuan == 420
    assert task.context_scope == "独自恢复"
    assert task.question is None
    assert task.phase.value == "understanding"
    assert selected == branch
    assert label == "按已验证分支继续"


async def test_user_cannot_claim_completion_before_provider_window(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("early-completion", "今晚安排")
    plan = await make_plan(world)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案好了",
        goal=plan.goal,
        policy=await make_policy(world),
    ))
    task = await tasks.approve_mandate(task)
    task = await tasks.confirm_transaction(task)
    assert task.policy is not None
    node = task.policy.primary_plan.nodes[0]
    node.starts_at = "23:45"
    node.ends_at = "23:55"
    node.status = "executing"

    with pytest.raises(ValueError, match="后可确认现实完成"):
        await tasks.record_reality_event(task, RealityEvent(
            task_id=task.id,
            kind="node_completed",
            node_id=node.id,
            detail="我已经完成了",
            completion_evidence=CompletionEvidence(
                source="user_confirmation",
                detail="用户自行确认",
            ),
        ))


async def test_supply_commitments_do_not_complete_the_real_world_goal(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-real-completion", "今晚安排好后再陪我完成")
    plan = await make_plan(world)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案好了",
        goal=plan.goal,
        policy=await make_policy(world),
    ))
    task = await tasks.approve_mandate(task)
    task = await tasks.confirm_transaction(task)

    assert task.policy is not None
    for node in task.policy.primary_plan.nodes:
        for action in node.actions:
            task = await tasks.record_event(task, FulfillmentEvent(
                task_id=task.id,
                node_id=node.id,
                action=action,
                status="succeeded",
                detail="外部供给已接受承诺",
                receipt_id=f"receipt-{node.id}-{action.value}",
                actual_amount_yuan=node.price_yuan if action == node.actions[0] else 0,
                lifecycle_stage="committed",
            ))

    assert task.phase.value == "executing"
    assert all(node.status.value == "executing" for node in task.policy.primary_plan.nodes)
    assert task.live is not None
    assert task.live.actual_outcome is None

    for node in task.policy.primary_plan.nodes:
        task, affected = await tasks.record_reality_event(task, RealityEvent(
            task_id=task.id,
            kind="node_completed",
            node_id=node.id,
            detail=f"用户已完成：{node.title}",
            completion_evidence=CompletionEvidence(
                source="provider_status",
                provider_status="completed",
                detail="供给方确认现实完成",
            ),
        ))
        assert affected == [node.id]

    assert task.phase.value == "completed"
    assert task.live is not None
    assert task.live.actual_outcome is not None
    assert task.live.actual_outcome.completed_node_ids == [
        node.id for node in task.policy.primary_plan.nodes
    ]


async def test_cancelling_the_only_commitment_ends_as_cancelled_not_completed(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-cancel-outcome", "今晚看场电影")
    plan = await make_plan(world)
    activity = plan.nodes[1].model_copy(update={"depends_on": []}, deep=True)
    plan.nodes = [activity]
    plan.total_yuan = activity.price_yuan
    policy = (await make_policy(world)).model_copy(update={"primary_plan": plan}, deep=True)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案好了",
        goal=plan.goal,
        policy=policy,
    ))
    task = await tasks.approve_mandate(task)
    task = await tasks.confirm_transaction(task)
    task = await tasks.record_event(task, FulfillmentEvent(
        task_id=task.id,
        node_id=activity.id,
        action="buy_ticket",
        status="succeeded",
        detail="电影票已购买",
        receipt_id="ticket-one",
        actual_amount_yuan=activity.price_yuan,
        lifecycle_stage="committed",
    ))
    task = await tasks.record_event(task, FulfillmentEvent(
        task_id=task.id,
        node_id=activity.id,
        action="refund_ticket",
        status="compensated",
        detail="电影票已退款",
        receipt_id="refund-one",
        lifecycle_stage="refunded",
    ))

    assert task.phase.value == "cancelled"
    assert task.policy.primary_plan.nodes[0].status.value == "compensated"
    assert task.live is not None
    assert task.live.actual_outcome is not None
    assert "取消" in task.live.actual_outcome.summary


async def test_direct_time_edit_repairs_only_overlapping_successors_and_can_undo(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-plan-edit", "安排今晚")
    plan = await make_plan(world)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案好了",
        goal=plan.goal,
        policy=await make_policy(world),
    ))

    task = await tasks.apply_plan_edit(task, PlanEditIntent(
        source="direct",
        instruction="电影改到 20:50，其他部分不变",
        operation=PlanEditOperation.ADJUST_NODE,
        node_id="show",
        starts_at="20:50",
    ))

    assert task.policy is not None
    nodes = {node.id: node for node in task.policy.primary_plan.nodes}
    assert (nodes["dinner"].starts_at, nodes["dinner"].ends_at) == ("18:40", "20:00")
    assert (nodes["show"].starts_at, nodes["show"].ends_at) == ("20:50", "22:20")
    assert (nodes["home"].starts_at, nodes["home"].ends_at) == ("22:20", "22:52")
    assert task.last_patch is not None
    assert {item.node_id for item in task.last_patch.operations} == {"show", "home"}
    assert task.plan_undo is not None

    task = await tasks.apply_plan_edit(task, PlanEditIntent(
        source="direct",
        instruction="撤销刚才的时间调整",
        operation=PlanEditOperation.UNDO_LAST_EDIT,
    ))
    assert task.policy is not None
    restored = {node.id: node for node in task.policy.primary_plan.nodes}
    assert restored["show"].starts_at == "20:30"
    assert restored["home"].starts_at == "22:10"
    assert task.plan_undo is None


async def test_undo_reestablishes_the_restored_supply_identity(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-replace-undo", "安排今晚")
    plan = await make_plan(world)
    plan.nodes[0].alternatives = ["food_nightmarket"]
    policy = (await make_policy(world)).model_copy(update={"primary_plan": plan}, deep=True)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案好了",
        goal=plan.goal,
        policy=policy,
    ))
    task = await tasks.apply_plan_edit(task, PlanEditIntent(
        source="direct",
        instruction="晚餐换成已核验候选",
        operation=PlanEditOperation.REPLACE_NODE,
        node_id="dinner",
        option_id="food_nightmarket",
    ))
    task = await tasks.apply_plan_edit(task, PlanEditIntent(
        source="direct",
        instruction="撤销晚餐替换",
        operation=PlanEditOperation.UNDO_LAST_EDIT,
    ))

    assert task.policy is not None
    dinner = task.policy.primary_plan.nodes[0]
    assert dinner.option_id == "food_yanlan"
    assert dinner.supply_reference is not None
    assert dinner.supply_reference.supply_id == "food_yanlan"
    event = await tasks.lifecycle.execute(FulfillmentCommand(
        task_id=task.id,
        node_id=dinner.id,
        action="reserve_table",
        option_id=dinner.option_id,
        amount_yuan=0,
    ))
    assert event.status == "succeeded"


async def test_direct_replacement_refreshes_consumer_plan_summary(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-summary-refresh", "今晚只安排晚餐")
    plan = await make_plan(world)
    dinner = plan.nodes[0].model_copy(update={
        "depends_on": [],
        "alternatives": ["food_nightmarket"],
    }, deep=True)
    plan.nodes = [dinner]
    plan.total_yuan = dinner.price_yuan
    plan.title = dinner.title
    plan.thesis = f"{dinner.starts_at} {dinner.title}（¥{dinner.price_yuan}）"
    policy = (await make_policy(world)).model_copy(update={"primary_plan": plan}, deep=True)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案好了",
        goal=plan.goal,
        policy=policy,
    ))
    task = await tasks.apply_plan_edit(task, PlanEditIntent(
        source="direct",
        instruction="晚餐换成已核验候选",
        operation=PlanEditOperation.REPLACE_NODE,
        node_id=dinner.id,
        option_id="food_nightmarket",
    ))

    assert task.policy is not None
    edited = task.policy.primary_plan
    replacement = edited.nodes[0]
    assert edited.title == replacement.title
    assert replacement.title in edited.thesis
    assert f"¥{edited.total_yuan}" in edited.thesis
    assert dinner.title not in edited.thesis


async def test_direct_remove_reconnects_downstream_dependencies(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-remove-node", "安排今晚")
    plan = await make_plan(world)
    extra = plan.nodes[-1].model_copy(
        update={
            "id": "home_backup",
            "starts_at": "22:42",
            "ends_at": "22:55",
            "depends_on": ["home"],
        },
        deep=True,
    )
    plan.nodes.append(extra)
    plan.total_yuan += extra.price_yuan
    policy = (await make_policy(world)).model_copy(update={"primary_plan": plan}, deep=True)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案好了",
        goal=plan.goal,
        policy=policy,
    ))

    task = await tasks.apply_plan_edit(task, PlanEditIntent(
        source="direct",
        instruction="删掉第一段返程，其他部分不变",
        operation=PlanEditOperation.REMOVE_NODE,
        node_id="home",
    ))

    assert task.policy is not None
    nodes = {node.id: node for node in task.policy.primary_plan.nodes}
    assert set(nodes) == {"dinner", "show", "home_backup"}
    assert nodes["home_backup"].depends_on == ["show"]


async def test_direct_remove_rejects_a_goal_required_commitment(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-required-node", "安排今晚")
    plan = await make_plan(world)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案好了",
        goal=plan.goal,
        policy=await make_policy(world),
    ))

    with pytest.raises(ValueError, match="required by the current goal"):
        await tasks.apply_plan_edit(task, PlanEditIntent(
            source="direct",
            instruction="删掉电影",
            operation=PlanEditOperation.REMOVE_NODE,
            node_id="show",
        ))


async def test_reality_event_uses_capability_observation_contracts(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-weather", "安排今晚")
    plan = await make_plan(world)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案好了",
        goal=plan.goal,
        policy=await make_policy(world),
    ))

    task, affected = await tasks.record_reality_event(task, RealityEvent(
        task_id=task.id,
        kind="weather_change",
        detail="现场开始下雨",
    ))

    assert affected == ["show", "home"]
    assert task.phase.value == "needs_replan"
    assert {signal.supply_id for signal in task.supply_signals[-2:]} == {
        "activity_comedy",
        "mobility_home",
    }

    task, affected = await tasks.record_reality_event(task, RealityEvent(
        task_id=task.id,
        kind="location_change",
        detail="用户已到达大望路地铁站",
        location="大望路地铁站 A 口",
    ))
    assert affected == ["home"]
    assert task.goal is not None
    location = next(
        item for item in task.goal.context_facts if item.key == "current_location"
    )
    assert location.value == "大望路地铁站 A 口"
    assert location.source.value == "explicit"


async def test_user_delay_consumes_slack_before_shifting_successors(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-late", "安排今晚")
    plan = await make_plan(world)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案好了",
        goal=plan.goal,
        policy=await make_policy(world),
    ))
    event = RealityEvent(
        task_id=task.id,
        kind="user_late",
        detail="用户预计晚到 20 分钟",
        magnitude=20,
    )
    task, _ = await tasks.record_reality_event(task, event)
    task, applied = await tasks.apply_user_delay(task, event)

    assert applied
    assert task.policy is not None
    nodes = {node.id: node for node in task.policy.primary_plan.nodes}
    assert (nodes["dinner"].starts_at, nodes["dinner"].ends_at) == ("19:00", "20:20")
    assert nodes["show"].starts_at == "20:30"
    assert nodes["home"].starts_at == "22:10"
    assert task.last_patch is not None
    assert [item.node_id for item in task.last_patch.operations] == ["dinner"]


async def test_unsupported_goal_finishes_with_an_explainable_boundary(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-boundary", "我胸痛，帮我买点药扛过去")
    goal = (await make_plan(world)).goal.model_copy(
        update={"outcome": "处理突发胸痛"},
        deep=True,
    )
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.INFORM,
        message="这可能是医疗急症，不能用购药代替急救，请立即联系 120。",
        goal=goal,
    ))
    assert task.phase.value == "unsupported"


async def test_stale_task_write_is_rejected_without_losing_the_winner(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    created = await tasks.start("user-concurrent", "安排今晚")
    first = await tasks.get(created.id)
    stale = await tasks.get(created.id)
    assert first is not None and stale is not None

    await tasks.add_user_message(first, "先安排晚餐")
    with pytest.raises(DocumentConflictError):
        await tasks.add_user_message(stale, "改成看电影")

    persisted = await tasks.get(created.id)
    assert persisted is not None
    assert [message.content for message in persisted.messages] == [
        "安排今晚",
        "先安排晚餐",
    ]


async def test_goal_contract_edit_changes_only_requested_fields(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-goal-edit", "安排今晚")
    plan = await make_plan(world)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案已就绪。",
        goal=plan.goal,
        policy=await make_policy(world),
    ))

    task, instruction = await tasks.edit_goal(task, GoalContractEdit(
        budget_yuan=400,
        deadline="22:30",
        deadline_label="最晚活动结束",
        lock_fields=["budget_yuan"],
    ))

    assert task.goal is not None
    assert task.goal.budget_yuan == 400
    assert task.goal.deadline == "22:30"
    assert task.goal.deadline_label == "最晚活动结束"
    assert task.goal.origin == "国贸"
    assert task.goal.locked_fields == ["budget_yuan"]
    budget_constraint = next(
        item for item in task.goal.constraints if item.kind.value == "budget"
    )
    assert budget_constraint.label == "预算"
    assert budget_constraint.value == "400"
    deadline_constraint = next(
        item for item in task.goal.constraints if item.kind.value == "deadline"
    )
    assert deadline_constraint.label == "最晚活动结束"
    assert deadline_constraint.source.value == "explicit"
    deadline_fact = next(
        item for item in task.goal.context_facts if item.key == "deadline_meaning"
    )
    assert deadline_fact.label == "最晚活动结束"
    assert deadline_fact.value == "22:30"
    assert deadline_fact.source.value == "explicit"
    assert task.policy is not None
    assert task.policy.primary_plan.goal.budget_yuan == 500
    assert "预算改为 400" in instruction
