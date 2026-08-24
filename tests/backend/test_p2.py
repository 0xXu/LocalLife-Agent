from datetime import timedelta

from backend.domain.models import (
    CompletionEvidence,
    AgentTurn,
    FulfillmentCommand,
    FulfillmentEvent,
    PreferenceEvidence,
    PreferenceFactEdit,
    RealityEvent,
    SupplyReference,
    TurnKind,
    utc_now,
)
from backend.mcp import load_capability_catalog
from backend.preferences import PreferenceModule
from backend.supply import SupplyLifecycleModule
from backend.tasks import TaskModule
from tests.backend.conftest import make_plan, make_policy


async def test_contextual_preference_fact_supersedes_without_becoming_global(world) -> None:
    preferences = PreferenceModule(world.store)
    first = PreferenceEvidence(
        context_scope="与朋友聚会",
        dimension="pace",
        preference="热闹一点",
        source="explicit_expression",
        confidence=0.9,
        task_id="task-one",
    )
    second = first.model_copy(update={
        "preference": "安静聊天",
        "task_id": "task-two",
    })

    created = await preferences.ingest("user-one", [first])
    changed = await preferences.ingest("user-one", [second])

    active = await preferences.list("user-one")
    history = await preferences.list("user-one", include_inactive=True)
    assert [item.preference for item in active] == ["安静聊天"]
    assert changed[0].supersedes == created[0].id
    assert len(history) == 2
    assert await preferences.relevant(
        "user-one",
        context_scope="一个人放空",
        query="安排今晚",
    ) == []

    revised = await preferences.revise(
        "user-one",
        changed[0].id,
        PreferenceFactEdit(preference="轻松聊天"),
    )
    assert revised.preference == "轻松聊天"
    assert revised.source == "agent_override"

    await preferences.ingest("user-one", [second.model_copy(update={
        "preference": "越热闹越好",
        "source": "fulfillment_outcome",
        "confidence": 0.99,
    })])
    assert (await preferences.list("user-one"))[0].preference == "轻松聊天"


async def test_supply_identity_survives_quote_hold_commit_and_observation(world) -> None:
    lifecycle = SupplyLifecycleModule(
        world.store,
        world,
        load_capability_catalog(),
    )
    reference = await lifecycle.quote_and_hold(
        task_id="task-life",
        node_id="experiences",
        capability_id="experiences",
        supply_id="activity_cinema",
    )
    event = await lifecycle.execute(FulfillmentCommand(
        task_id="task-life",
        node_id="experiences",
        action="buy_ticket",
        option_id="activity_cinema",
        amount_yuan=156,
    ))

    assert reference.stage.value == "held"
    assert event.status == "succeeded"
    assert event.lifecycle_stage.value == "committed"
    assert event.actual_amount_yuan == 156
    assert event.compensation_action.value == "refund_ticket"

    persisted = await world.store.load(
        lifecycle.namespace,
        "task-life:experiences",
    )
    assert persisted is not None
    persisted["hold_expires_at"] = (
        utc_now() - timedelta(minutes=1)
    ).isoformat()
    await world.store.save(
        lifecycle.namespace,
        "task-life:experiences",
        persisted,
    )

    changed = await lifecycle.execute(FulfillmentCommand(
        task_id="task-life",
        node_id="experiences",
        action="change_ticket",
        option_id="activity_cinema",
        amount_yuan=0,
        related_receipt_id=event.receipt_id,
    ))
    assert changed.status == "succeeded"
    assert changed.lifecycle_stage.value == "changed"

    await world.inject("price_jump")
    signals = await lifecycle.observe("task-life", "experiences")
    assert signals[0].kind == "price_increase"
    assert signals[0].supply_id == reference.supply_id


async def test_one_supply_reference_tracks_multiple_commitments_independently(world) -> None:
    lifecycle = SupplyLifecycleModule(
        world.store,
        world,
        load_capability_catalog(),
    )
    await lifecycle.quote_and_hold(
        task_id="task-dining-bundle",
        node_id="dining",
        capability_id="dining",
        supply_id="food_yanlan",
    )
    reservation = await lifecycle.execute(FulfillmentCommand(
        task_id="task-dining-bundle",
        node_id="dining",
        action="reserve_table",
        option_id="food_yanlan",
        amount_yuan=0,
    ))
    coupon = await lifecycle.execute(FulfillmentCommand(
        task_id="task-dining-bundle",
        node_id="dining",
        action="buy_coupon",
        option_id="food_yanlan",
        amount_yuan=188,
    ))
    payload = await world.store.load(
        lifecycle.namespace,
        "task-dining-bundle:dining",
    )
    reference = SupplyReference.model_validate(payload)
    assert set(reference.commitments) == {"reserve_table", "buy_coupon"}

    cancelled = await lifecycle.execute(FulfillmentCommand(
        task_id="task-dining-bundle",
        node_id="dining",
        action="cancel_reservation",
        option_id="food_yanlan",
        amount_yuan=0,
        related_receipt_id=reservation.receipt_id,
    ))
    assert cancelled.lifecycle_stage.value == "committed"
    payload = await world.store.load(
        lifecycle.namespace,
        "task-dining-bundle:dining",
    )
    reference = SupplyReference.model_validate(payload)
    assert set(reference.commitments) == {"buy_coupon"}

    refunded = await lifecycle.execute(FulfillmentCommand(
        task_id="task-dining-bundle",
        node_id="dining",
        action="refund_coupon",
        option_id="food_yanlan",
        amount_yuan=0,
        related_receipt_id=coupon.receipt_id,
    ))
    assert refunded.lifecycle_stage.value == "refunded"


async def test_completion_archives_actual_outcome_and_learning_evidence(world, planning) -> None:
    tasks = TaskModule(world.store, planning)
    task = await tasks.start("user-outcome", "今晚和朋友放松，不想排队")
    plan = await make_plan(world)
    task = await tasks.apply_turn(task, AgentTurn(
        kind=TurnKind.PROPOSE,
        message="方案已就绪",
        goal=plan.goal,
        policy=await make_policy(world),
    ))
    task.context_scope = "与朋友聚会"
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
                detail="现实履约完成",
                actual_amount_yuan=node.price_yuan if action == node.actions[0] else 0,
                lifecycle_stage="committed",
            ))
        task, _ = await tasks.record_reality_event(task, RealityEvent(
            task_id=task.id,
            kind="node_completed",
            node_id=node.id,
            detail=f"现实履约完成：{node.title}",
            completion_evidence=CompletionEvidence(
                source="provider_status",
                provider_status="completed",
                detail="供给方确认现实完成",
            ),
        ))

    assert task.live is not None
    assert task.live.actual_outcome is not None
    assert task.live.actual_outcome.total_yuan == task.policy.primary_plan.total_yuan
    assert all(
        node.supply_reference and node.supply_reference.stage.value == "committed"
        for node in task.policy.primary_plan.nodes
    )
    assert task.outcome_check_in is not None
    task = await tasks.record_outcome_check_in(task, "achieved")
    learned = await tasks.preferences.list("user-outcome")
    assert {item.preference for item in learned} == set(plan.goal.preferences)
    assert {item.context_scope for item in learned} == {"与朋友聚会"}


async def test_pre_rewrite_task_documents_never_enter_live_supply_reactions(world, planning) -> None:
    await world.store.save("tasks", "legacy-task", {
        "id": "legacy-task",
        "user_id": "legacy-user",
        "plan": None,
    })
    tasks = TaskModule(world.store, planning)
    assert await tasks.affected_by_supply("activity_cinema") == []
