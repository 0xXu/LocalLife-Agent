import pytest

from backend.domain.models import (
    ActionKind,
    DecisionPoint,
    ExecutionMandate,
    FallbackPolicy,
    GoalContract,
    GroundedCandidateSet,
    NodeStatus,
    PlanGraph,
    PlanNode,
    PlanPolicy,
    SupplyReference,
    TemporalConstraint,
    TriggerCondition,
)
from backend.planning import PlanningModule
from backend.supply import SupplyTwin
from tests.backend.conftest import make_plan


async def test_solver_certifies_cross_domain_combinations_before_model_choice(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    dining = [await world.get(item) for item in ["food_yanlan", "food_nightmarket"]]
    activities = [await world.get(item) for item in ["activity_comedy", "activity_aroma"]]
    result = planning.solve(
        GoalContract(
            outcome="晚餐后放松",
            city="北京",
            origin="国贸",
            party_size=2,
            budget_yuan=380,
            deadline="22:30",
        ),
        [
            GroundedCandidateSet(
                capability_id="dining",
                consumes_user_time=True,
                trigger_kind="queue_delay",
                candidates=[item for item in dining if item is not None],
            ),
            GroundedCandidateSet(
                capability_id="experiences",
                consumes_user_time=True,
                trigger_kind="inventory_unavailable",
                candidates=[item for item in activities if item is not None],
            ),
        ],
        [],
    )

    assert result.status == "feasible"
    assert result.pareto_candidate_ids
    for candidate in result.candidates:
        assert candidate.objectives.total_yuan <= 380
        timed = sorted(candidate.selections, key=lambda item: item.starts_at)
        assert all(left.ends_at <= right.starts_at for left, right in zip(timed, timed[1:]))
        assert timed[-1].ends_at <= "22:30"


async def test_solver_places_route_evidence_between_tightly_timed_commitments(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    dining = [await world.get(item) for item in ["food_yanlan", "food_nightmarket"]]
    cinema = await world.get("activity_cinema")
    mobility = [
        await world.get(item)
        for item in ["mobility_connector", "mobility_navigation", "mobility_home"]
    ]
    assert cinema is not None
    result = planning.solve(
        GoalContract(
            outcome="固定时刻晚餐后看电影",
            city="北京",
            origin="国贸",
            party_size=2,
            budget_yuan=800,
            deadline="23:00",
        ),
        [
            GroundedCandidateSet(
                capability_id="dining",
                consumes_user_time=True,
                trigger_kind="queue_delay",
                location_bound=True,
                candidates=[item for item in dining if item is not None],
            ),
            GroundedCandidateSet(
                capability_id="experiences",
                consumes_user_time=True,
                trigger_kind="inventory_unavailable",
                location_bound=True,
                candidates=[cinema],
            ),
            GroundedCandidateSet(
                capability_id="mobility",
                consumes_user_time=True,
                trigger_kind="eta_delay",
                provides_transition_evidence=True,
                maximum_commitments=2,
                candidates=[item for item in mobility if item is not None],
            ),
        ],
        [
            TemporalConstraint(
                capability_id="dining",
                relation="exact_start",
                time="19:00",
            ),
            TemporalConstraint(
                capability_id="experiences",
                relation="exact_start",
                time="20:45",
            ),
        ],
    )

    assert result.status == "feasible"
    for candidate in result.candidates:
        assert sum(
            item.capability_id == "mobility" for item in candidate.selections
        ) == 1
        dining_selection = next(
            item for item in candidate.selections if item.capability_id == "dining"
        )
        experience_selection = next(
            item for item in candidate.selections if item.capability_id == "experiences"
        )
        connector = next(
            item for item in candidate.selections if item.option_id == "mobility_connector"
        )
        assert dining_selection.option_id == "food_nightmarket"
        assert dining_selection.ends_at <= connector.starts_at
        assert connector.ends_at <= experience_selection.starts_at


async def test_solver_enforces_a_later_commitment_after_the_referenced_one(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    massage = await world.get("service_massage_wangjing")
    ride = await world.get("mobility_home")
    assert massage is not None
    assert ride is not None
    ride = ride.model_copy(update={
        "duration_minutes": 36,
        "time_slots": ["20:45"],
        "metadata": {
            **ride.metadata,
            "on_demand": True,
            "scheduling_window_start": "20:45",
            "scheduling_window_end": "23:45",
            "scheduling_interval_minutes": 5,
        },
    }, deep=True)
    candidate_sets = [
        GroundedCandidateSet(
            capability_id="appointments",
            consumes_user_time=True,
            trigger_kind="fulfillment_failure",
            location_bound=True,
            candidates=[massage],
        ),
        GroundedCandidateSet(
            capability_id="mobility",
            consumes_user_time=True,
            trigger_kind="eta_delay",
            provides_transition_evidence=True,
            candidates=[ride],
        ),
    ]
    goal = GoalContract(
        outcome="按摩后在23:00前回到国贸",
        city="北京",
        origin="国贸",
        party_size=1,
        budget_yuan=400,
        deadline="23:00",
    )

    def solve_at(time: str):
        return planning.solve(
            goal,
            candidate_sets,
            [
                TemporalConstraint(
                    capability_id="appointments",
                    relation="exact_start",
                    time=time,
                ),
                TemporalConstraint(
                    capability_id="mobility",
                    relation="starts_after",
                    reference_capability_id="appointments",
                ),
                TemporalConstraint(
                    capability_id="mobility",
                    relation="latest_end",
                    time="23:00",
                ),
            ],
        )

    assert solve_at("20:00").status == "feasible"
    late = solve_at("21:30")
    assert late.status == "infeasible"
    assert any(
        "无法衔接" in reason.message
        for reason in late.infeasible_reasons
    )


async def test_solver_returns_constraint_core_for_impossible_session(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    cinema = await world.get("activity_cinema")
    assert cinema is not None
    result = planning.solve(
        GoalContract(
            outcome="看晚场电影",
            city="北京",
            origin="国贸",
            party_size=1,
            budget_yuan=300,
            deadline="22:20",
        ),
        [GroundedCandidateSet(
            capability_id="experiences",
            consumes_user_time=True,
            trigger_kind="inventory_unavailable",
            candidates=[cinema],
        )],
        [TemporalConstraint(
            capability_id="experiences",
            relation="exact_start",
            time="20:45",
        )],
    )

    assert result.status == "infeasible"
    assert {item.code for item in result.infeasible_reasons} <= {
        "deadline_conflict", "time_window_conflict"
    }
    assert result.infeasible_reasons


async def test_recovery_derives_the_minimum_solver_proved_budget(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    dining = await world.get("food_yanlan")
    assert dining is not None
    goal = GoalContract(
        outcome="吃一顿安静晚餐",
        city="北京",
        origin="国贸",
        party_size=1,
        budget_yuan=100,
        deadline="23:00",
    )
    candidate_sets = [GroundedCandidateSet(
        capability_id="dining",
        consumes_user_time=True,
        trigger_kind="queue_delay",
        candidates=[dining],
    )]
    infeasible = planning.solve(goal, candidate_sets, [])

    recoveries = planning.recover(goal, candidate_sets, [], infeasible)

    assert infeasible.status == "infeasible"
    assert len(recoveries) == 1
    assert recoveries[0].goal.budget_yuan == dining.price_yuan
    assert recoveries[0].feasible_set.status == "feasible"


async def test_recovery_uses_published_slots_in_nearest_first_order(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    massage = await world.get("service_massage_wangjing")
    assert massage is not None
    goal = GoalContract(
        outcome="安排一次按摩",
        city="北京",
        origin="望京",
        party_size=1,
        budget_yuan=500,
        deadline="23:00",
    )
    candidate_sets = [GroundedCandidateSet(
        capability_id="appointments",
        consumes_user_time=True,
        trigger_kind="fulfillment_failure",
        candidates=[massage],
    )]
    constraints = [TemporalConstraint(
        capability_id="appointments",
        relation="exact_start",
        time="19:30",
    )]
    infeasible = planning.solve(goal, candidate_sets, constraints)

    recoveries = planning.recover(goal, candidate_sets, constraints, infeasible)

    assert [item.temporal_constraints[0].time for item in recoveries] == [
        "20:00",
        "18:30",
        "21:30",
    ]
    assert all(item.feasible_set.status == "feasible" for item in recoveries)


async def test_provider_semantics_allow_delivery_to_overlap_an_activity(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    massage = await world.get("service_massage_wangjing")
    medicine = await world.get("delivery_pharmacy_wangjing")
    assert massage is not None and medicine is not None
    result = planning.solve(
        GoalContract(
            outcome="按摩时把药送到家",
            city="北京",
            origin="望京",
            party_size=1,
            budget_yuan=400,
            deadline="21:00",
        ),
        [
            GroundedCandidateSet(
                capability_id="appointments",
                consumes_user_time=True,
                trigger_kind="fulfillment_failure",
                candidates=[massage],
            ),
            GroundedCandidateSet(
                capability_id="delivery",
                consumes_user_time=False,
                trigger_kind="fulfillment_failure",
                candidates=[medicine],
            ),
        ],
        [],
    )

    assert result.status == "feasible"
    assert any(
        left.starts_at < right.ends_at and right.starts_at < left.ends_at
        for candidate in result.candidates
        for left in candidate.selections
        for right in candidate.selections
        if left.capability_id == "appointments" and right.capability_id == "delivery"
    )


async def test_solver_dispatches_delivery_after_service_within_arrival_deadline(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    massage = await world.get("service_massage_wangjing")
    congee = await world.get("delivery_congee_wangjing")
    assert massage is not None and congee is not None
    congee = congee.model_copy(deep=True)
    congee.metadata.update({
        "scheduling_window_start": "18:00",
        "scheduling_window_end": "21:25",
        "scheduling_interval_minutes": 5,
    })
    result = planning.solve(
        GoalContract(
            outcome="按摩结束后把粥送到",
            city="北京",
            origin="望京",
            party_size=1,
            budget_yuan=380,
            deadline="22:00",
        ),
        [
            GroundedCandidateSet(
                capability_id="appointments",
                consumes_user_time=True,
                trigger_kind="fulfillment_failure",
                candidates=[massage],
            ),
            GroundedCandidateSet(
                capability_id="delivery",
                consumes_user_time=False,
                trigger_kind="fulfillment_failure",
                candidates=[congee],
            ),
        ],
        [
            TemporalConstraint(
                capability_id="appointments",
                relation="exact_start",
                time="20:00",
            ),
            TemporalConstraint(
                capability_id="delivery",
                relation="starts_after",
                reference_capability_id="appointments",
            ),
            TemporalConstraint(
                capability_id="delivery",
                relation="latest_end",
                time="22:00",
            ),
        ],
    )

    assert result.status == "feasible"
    assert any(
        selection.capability_id == "delivery"
        and selection.starts_at == "21:15"
        and selection.ends_at == "21:50"
        for candidate in result.candidates
        for selection in candidate.selections
    )


async def test_valid_plan_and_two_level_authorization(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    plan = await make_plan(world)
    assert (await planning.validate(plan)).valid

    with pytest.raises(ValueError, match="approved"):
        planning.commands("task-1", plan)

    plan = planning.approve_mandate(plan)
    free = planning.free_commands("task-1", plan)
    confirmation = planning.transaction_confirmation("task-1", plan)
    assert [item.action.value for item in free] == ["reserve_table"]
    assert confirmation.total_cap_yuan == plan.total_yuan

    with pytest.raises(ValueError, match="transaction"):
        planning.paid_commands("task-1", plan, confirmation)

    plan, confirmation = planning.approve_transaction(plan, confirmation)
    paid = planning.paid_commands("task-1", plan, confirmation)
    assert {item.action.value for item in paid} == {"buy_coupon", "buy_ticket", "request_ride"}


async def test_validator_detects_reachable_world_change(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    plan = await make_plan(world)
    await world.inject("show_sold_out")
    validation = await planning.validate(plan)
    assert not validation.valid
    assert {issue.code for issue in validation.issues} >= {"supply_unavailable", "stale_evidence"}


async def test_patch_preserves_completed_commitments(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    current = await make_plan(world)
    current.nodes[0].status = NodeStatus.COMPLETED
    proposed = current.model_copy(deep=True)
    proposed.nodes[0].starts_at = "18:50"
    patch = planning.diff(current, proposed, trigger_source="supply_event")
    assert patch.requires_confirmation
    with pytest.raises(ValueError, match="committed node"):
        await planning.apply_patch(current, patch, proposed)


async def test_locked_node_is_restored_before_diffing_a_new_plan(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    current = await make_plan(world)
    locked_id = current.nodes[0].id
    current.locked_node_ids = [locked_id]
    proposed = current.model_copy(deep=True)
    proposed.nodes[0].title = "模型试图改掉的晚餐"
    proposed.nodes[1].reason = "用户要求替换后重新选择"

    preserved = planning.preserve_locked_nodes(current, proposed)

    assert preserved.locked_node_ids == [locked_id]
    assert preserved.nodes[0] == current.nodes[0]
    assert preserved.nodes[1].reason == "用户要求替换后重新选择"


async def test_diff_ignores_rehydration_of_unchanged_supply_references(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    current = await make_plan(world)
    for node in current.nodes:
        node.supply_reference = SupplyReference(
            task_id="task-diff",
            node_id=node.id,
            capability_id=node.capability_id,
            supply_id=node.option_id,
            stage="held",
            world_version=1,
        )
    proposed = current.model_copy(deep=True)
    for node in proposed.nodes:
        node.supply_reference = None
    proposed.nodes[1].reason = "用户选择了不同体验方向"
    proposed.nodes[1].starts_at = "20:35"

    patch = planning.diff(current, proposed, trigger_source="plan_edit")

    assert [operation.node_id for operation in patch.operations] == ["show"]


async def test_policy_trigger_produces_one_versioned_local_patch(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    current = planning.approve_mandate(await make_plan(world))
    current.nodes[0].status = NodeStatus.FAILED
    alternative = await world.get("food_nightmarket")
    assert alternative is not None
    replacement = current.nodes[0].model_copy(update={
        "title": alternative.name,
        "option_id": alternative.id,
        "ends_at": "19:50",
        "price_yuan": alternative.price_yuan,
        "venue": alternative.venue,
        "actions": alternative.actions,
        "status": NodeStatus.PROPOSED,
        "evidence": alternative.evidence,
    }, deep=True)
    policy = PlanPolicy(
        primary_plan=current,
        decision_points=[DecisionPoint(
            node_id="dinner",
            trigger=TriggerCondition(
                kind="fulfillment_failure",
                node_id="dinner",
            ),
            slack_minutes=40,
            decision_deadline="18:20",
            fallbacks=[FallbackPolicy(
                node_id="dinner",
                replacement=replacement,
                authorization_effect="within_mandate",
            )],
        )],
    )

    result = await planning.activate_fallback(policy, "dinner")

    assert result is not None
    changed, patch = result
    assert patch.trigger_source == "policy_trigger"
    assert patch.authorization_effect == "within_mandate"
    assert [item.node_id for item in patch.operations] == ["dinner"]
    assert changed.primary_plan.version == current.version + 1
    assert changed.primary_plan.nodes[0].option_id == "food_nightmarket"
    assert changed.primary_plan.nodes[1:] == current.nodes[1:]


async def test_extended_domains_keep_navigation_free_and_orders_transactional(
    world: SupplyTwin,
    planning: PlanningModule,
) -> None:
    specs = [
        ("massage", "service_massage_wangjing", "18:30", "19:45", []),
        ("medicine", "delivery_pharmacy_wangjing", "20:00", "20:32", ["massage"]),
        ("navigate", "mobility_navigation", "20:35", "20:47", ["medicine"]),
    ]
    nodes: list[PlanNode] = []
    for node_id, option_id, starts_at, ends_at, dependencies in specs:
        option = await world.get(option_id)
        assert option is not None
        nodes.append(PlanNode(
            id=node_id,
            capability_id=(
                "mobility" if option.vertical.value == "mobility"
                else "delivery" if option.vertical.value == "delivery"
                else "appointments"
            ),
            vertical=option.vertical,
            title=option.name,
            option_id=option.id,
            starts_at=starts_at,
            ends_at=ends_at,
            price_yuan=option.price_yuan,
            venue=option.venue,
            reason="满足服务、配送和导航目标",
            trigger_kind=(
                "eta_delay" if option.vertical.value == "mobility"
                else "fulfillment_failure"
            ),
            actions=option.actions,
            depends_on=dependencies,
            evidence=option.evidence,
        ))
    plan = PlanGraph(
        title="望京生活代办",
        thesis="预约放松服务并完成到家配送与导航。",
        goal=GoalContract(
            outcome="下班后放松并买药回家",
            city="北京",
            origin="望京",
            party_size=1,
            budget_yuan=400,
            deadline="21:00",
        ),
        nodes=nodes,
        total_yuan=sum(node.price_yuan for node in nodes),
        mandate=ExecutionMandate(
            max_total_yuan=400,
            deadline="21:00",
            allowed_verticals=["service", "delivery", "mobility"],
        ),
    )
    plan = planning.approve_mandate(plan)
    free = planning.free_commands("task-extended", plan)
    confirmation = planning.transaction_confirmation("task-extended", plan)
    plan, confirmation = planning.approve_transaction(plan, confirmation)
    paid = planning.paid_commands("task-extended", plan, confirmation)

    assert [item.action for item in free] == [ActionKind.START_NAVIGATION]
    assert {item.action for item in paid} == {
        ActionKind.BOOK_SERVICE,
        ActionKind.PLACE_ORDER,
    }
