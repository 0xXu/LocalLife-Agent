from __future__ import annotations

from pydantic import ValidationError

from backend.domain.models import (
    AgentTurn,
    ChatMessage,
    Constraint,
    ContextFact,
    ConstraintKind,
    DecisionBranch,
    GoalContractEdit,
    GoalContract,
    FulfillmentEvent,
    PreferenceEvidence,
    RealityEvent,
    NodeStatus,
    OutcomeCheckIn,
    PlanEditIntent,
    PlanEditOperation,
    PlanPolicy,
    PlanUndoCheckpoint,
    TaskPhase,
    TaskProgressEvent,
    TaskSnapshot,
    TurnKind,
    ToolTrace,
    SupplySignal,
    ValueSource,
    utc_now,
)
from backend.live import LiveCompanionModule
from backend.mcp import load_capability_catalog
from backend.planning import PlanningModule
from backend.preferences import PreferenceModule
from backend.storage import DocumentStore
from backend.supply.lifecycle import SupplyLifecycleModule


class TaskModule:
    """Owns task state transitions and delegates learned user facts."""

    task_namespace = "tasks"
    def __init__(
        self,
        store: DocumentStore,
        planning: PlanningModule,
        preferences: PreferenceModule | None = None,
        lifecycle: SupplyLifecycleModule | None = None,
        live: LiveCompanionModule | None = None,
    ) -> None:
        self.store = store
        self.planning = planning
        catalog = load_capability_catalog()
        self.preferences = preferences or PreferenceModule(store)
        self.lifecycle = lifecycle or SupplyLifecycleModule(store, planning.supply, catalog)
        self.live = live or LiveCompanionModule(catalog)

    @staticmethod
    def _normalize_goal_labels(goal: GoalContract) -> GoalContract:
        labels = {
            ConstraintKind.BUDGET: "预算",
            ConstraintKind.DEADLINE: goal.deadline_label,
            ConstraintKind.ORIGIN: "地点",
            ConstraintKind.PARTY_SIZE: "人数",
        }
        normalized = goal.model_copy(deep=True)
        for constraint in normalized.constraints:
            if constraint.kind in labels:
                constraint.label = labels[constraint.kind]
        constraint_sources = {
            constraint.kind: constraint.source
            for constraint in normalized.constraints
        }
        facts = {item.key: item for item in normalized.context_facts}
        core = {
            "city": ("城市", normalized.city, ValueSource.DEFAULT),
            "origin": (
                "出发地点",
                normalized.origin,
                constraint_sources.get(ConstraintKind.ORIGIN, ValueSource.DEFAULT),
            ),
            "party_size": (
                "参与人数",
                str(normalized.party_size),
                constraint_sources.get(ConstraintKind.PARTY_SIZE, ValueSource.DEFAULT),
            ),
            "deadline_meaning": (
                normalized.deadline_label,
                normalized.deadline,
                constraint_sources.get(ConstraintKind.DEADLINE, ValueSource.DEFAULT),
            ),
        }
        for key, (label, value, source) in core.items():
            if key in facts:
                facts[key].label = label
                facts[key].value = value
                if source != ValueSource.DEFAULT or facts[key].source == ValueSource.DEFAULT:
                    facts[key].source = source
            else:
                normalized.context_facts.append(ContextFact(
                    key=key,
                    label=label,
                    value=value,
                    source=source,
                ))
        return normalized

    async def start(self, user_id: str, goal_text: str) -> TaskSnapshot:
        task = TaskSnapshot(
            user_id=user_id,
            goal_text=goal_text,
            messages=[ChatMessage(role="user", content=goal_text)],
        )
        await self._save(task, create=True)
        return task

    async def get(self, task_id: str) -> TaskSnapshot | None:
        payload = await self.store.load(self.task_namespace, task_id)
        return TaskSnapshot.model_validate(payload) if payload else None

    async def list_for_user(self, user_id: str) -> list[TaskSnapshot]:
        tasks = self._current_snapshots(
            item
            for item in await self.store.scan(self.task_namespace)
            if item.get("user_id") == user_id
        )
        return sorted(tasks, key=lambda item: item.updated_at, reverse=True)

    async def affected_by_supply(self, supply_id: str) -> list[TaskSnapshot]:
        tasks = self._current_snapshots(await self.store.scan(self.task_namespace))
        return [
            task
            for task in tasks
            if task.policy is not None
            and task.phase not in {TaskPhase.COMPLETED, TaskPhase.CANCELLED, TaskPhase.FAILED}
            and any(node.option_id == supply_id for node in task.policy.primary_plan.nodes)
        ]

    @staticmethod
    def _current_snapshots(payloads) -> list[TaskSnapshot]:
        current: list[TaskSnapshot] = []
        for payload in payloads:
            try:
                current.append(TaskSnapshot.model_validate(payload))
            except ValidationError:
                # Documents from the deleted pre-rewrite task model are not product tasks.
                continue
        return current

    async def add_user_message(self, task: TaskSnapshot, content: str) -> TaskSnapshot:
        if task.policy is not None and task.question is None:
            task.pending_plan_edit = PlanEditIntent(
                source="natural_language",
                instruction=content,
            )
        task.messages.append(ChatMessage(role="user", content=content))
        task.phase = TaskPhase.UNDERSTANDING
        task.question = None
        await self._save(task)
        return task

    async def select_decision_option(
        self,
        task: TaskSnapshot,
        option_id: str,
    ) -> tuple[TaskSnapshot, DecisionBranch, str]:
        if task.question is None:
            raise ValueError("task has no active decision")
        option = next((item for item in task.question.options if item.id == option_id), None)
        if option is None:
            raise ValueError("decision option does not belong to the active question")
        if option.branch is None:
            raise ValueError("decision option is not executable")
        branch = option.branch.model_copy(deep=True)
        task.messages.append(ChatMessage(role="user", content=option.label))
        task.goal = self._normalize_goal_labels(branch.goal)
        task.context_scope = branch.context_scope
        task.question = None
        if branch.action == "stop":
            task.phase = TaskPhase.CANCELLED
            task.messages.append(ChatMessage(
                role="agent",
                content="已保留你原来的要求并暂停这次安排。",
            ))
        else:
            task.phase = TaskPhase.UNDERSTANDING
        await self._save(task)
        return task, branch, option.label

    async def edit_goal(
        self,
        task: TaskSnapshot,
        edit: GoalContractEdit,
    ) -> tuple[TaskSnapshot, str]:
        if task.goal is None:
            raise ValueError("task goal is not ready")
        goal = task.goal.model_copy(deep=True)
        changes: list[str] = []
        field_labels = {
            "outcome": "目标",
            "city": "城市",
            "origin": "地点",
            "party_size": "人数",
            "budget_yuan": "预算",
            "deadline": goal.deadline_label,
        }
        for field_name in field_labels:
            value = getattr(edit, field_name)
            if value is None:
                continue
            setattr(goal, field_name, value)
            constraint_kind = {
                "budget_yuan": ConstraintKind.BUDGET,
                "deadline": ConstraintKind.DEADLINE,
                "origin": ConstraintKind.ORIGIN,
                "party_size": ConstraintKind.PARTY_SIZE,
            }.get(field_name)
            if constraint_kind is not None:
                matched_constraint = False
                for constraint in goal.constraints:
                    if constraint.kind == constraint_kind:
                        matched_constraint = True
                        constraint.label = field_labels[field_name]
                        constraint.value = str(value)
                        constraint.source = ValueSource.EXPLICIT
                if not matched_constraint:
                    goal.constraints.append(Constraint(
                        kind=constraint_kind,
                        label=field_labels[field_name],
                        value=str(value),
                        hard=True,
                        source=ValueSource.EXPLICIT,
                    ))
            context_key = {
                "city": "city",
                "origin": "origin",
                "party_size": "party_size",
                "deadline": "deadline_meaning",
            }.get(field_name)
            if context_key is not None:
                context_fact = next(
                    (item for item in goal.context_facts if item.key == context_key),
                    None,
                )
                if context_fact is not None:
                    context_fact.source = ValueSource.EXPLICIT
            changes.append(f"{field_labels[field_name]}改为 {value}")

        if edit.deadline_label is not None:
            goal.deadline_label = edit.deadline_label
            changes.append(f"截止时间语义改为 {edit.deadline_label}")

        constraints = {item.id: item for item in goal.constraints}
        for change in edit.constraint_edits:
            constraint = constraints.get(change.id)
            if constraint is None:
                raise ValueError(f"constraint does not exist: {change.id}")
            if change.delete:
                goal.constraints = [item for item in goal.constraints if item.id != change.id]
                changes.append(f"删除约束“{constraint.label}”")
                continue
            if change.value is not None:
                constraint.value = change.value
            if change.hard is not None:
                constraint.hard = change.hard
            changes.append(
                f"约束“{constraint.label}”设为{'必须' if constraint.hard else '尽量'}"
            )

        assumptions = {item.id: item for item in goal.assumptions}
        for change in edit.assumption_edits:
            assumption = assumptions.get(change.id)
            if assumption is None:
                raise ValueError(f"assumption does not exist: {change.id}")
            if change.delete:
                goal.assumptions = [item for item in goal.assumptions if item.id != change.id]
                changes.append(f"删除假设“{assumption.label}”")
                continue
            if change.value is not None:
                assumption.value = change.value
                changes.append(f"假设“{assumption.label}”改为 {change.value}")

        locked = set(goal.locked_fields)
        locked.update(edit.lock_fields)
        locked.difference_update(edit.unlock_fields)
        goal.locked_fields = sorted(locked)
        if edit.lock_fields:
            changes.append(f"锁定 {', '.join(edit.lock_fields)}")
        if edit.unlock_fields:
            changes.append(f"取消锁定 {', '.join(edit.unlock_fields)}")
        if not changes:
            raise ValueError("goal edit has no changes")

        instruction = "；".join(changes) + "。其他已经确认的要求保持不变。"
        task.goal = self._normalize_goal_labels(goal)
        task.messages.append(ChatMessage(role="user", content=instruction))
        task.phase = TaskPhase.UNDERSTANDING
        task.question = None
        await self._save(task)
        return task, instruction

    async def apply_plan_edit(
        self,
        task: TaskSnapshot,
        intent: PlanEditIntent,
    ) -> TaskSnapshot:
        if task.policy is None:
            raise ValueError("task has no plan")
        plan = task.policy.primary_plan
        if intent.operation in {
            PlanEditOperation.LOCK_NODE,
            PlanEditOperation.UNLOCK_NODE,
        }:
            node = next(
                (item for item in plan.nodes if item.id == intent.node_id),
                None,
            )
            if node is None:
                raise ValueError(f"plan node does not exist: {intent.node_id}")
            locked = set(plan.locked_node_ids)
            if intent.operation == PlanEditOperation.LOCK_NODE:
                locked.add(node.id)
            else:
                locked.discard(node.id)
            plan.locked_node_ids = sorted(locked)
            task.pending_plan_edit = None
            task.messages.append(ChatMessage(role="user", content=intent.instruction))
            await self._save(task)
            return task

        direct_operations = {
            PlanEditOperation.REMOVE_NODE,
            PlanEditOperation.ADJUST_NODE,
            PlanEditOperation.ADJUST_BUDGET,
        }
        if intent.operation == PlanEditOperation.REPLACE_NODE and intent.option_id is not None:
            direct_operations.add(PlanEditOperation.REPLACE_NODE)

        if intent.operation in direct_operations:
            target = await self.planning.edit_target(plan, intent)
            proposed_policy = task.policy.model_copy(
                update={
                    "primary_plan": target,
                    "alternatives": [],
                    "decision_points": [
                        item
                        for item in task.policy.decision_points
                        if any(node.id == item.node_id for node in target.nodes)
                        and item.node_id != intent.node_id
                    ],
                },
                deep=True,
            )
            return await self._apply_direct_policy(task, intent, proposed_policy)

        if intent.operation == PlanEditOperation.SELECT_ALTERNATIVE:
            if task.feasible_plan_set is None or task.feasible_plan_set.status != "feasible":
                raise ValueError("task has no feasible alternatives")
            assert intent.candidate_id is not None
            candidate_ids = set(task.feasible_plan_set.pareto_candidate_ids)
            if intent.candidate_id not in candidate_ids:
                raise ValueError("selected alternative is not in the current Pareto frontier")
            selected_direction = next(
                (
                    item.direction
                    for item in task.policy.alternatives
                    if item.candidate_id == intent.candidate_id
                ),
                None,
            )
            proposed_policy = await self.planning.materialize_policy(
                plan.goal,
                task.feasible_plan_set,
                intent.candidate_id,
                [
                    item
                    for item in task.feasible_plan_set.pareto_candidate_ids
                    if item != intent.candidate_id
                ][:2],
                title=plan.title,
                selection_reasons={},
            )
            proposed_policy.primary_plan = proposed_policy.primary_plan.model_copy(
                update={"version": plan.version + 1},
                deep=True,
            )
            proposed_policy.primary_plan = self.planning.preserve_locked_nodes(
                plan,
                proposed_policy.primary_plan,
            )
            task = await self._apply_direct_policy(task, intent, proposed_policy)
            if selected_direction is not None:
                changed = await self.preferences.ingest(task.user_id, [PreferenceEvidence(
                    context_scope=task.context_scope,
                    dimension="plan_tradeoff_choice",
                    preference=selected_direction,
                    source="actual_choice",
                    confidence=0.65,
                    task_id=task.id,
                )])
                task.applied_preference_fact_ids = [item.id for item in changed]
                await self._save(task)
            return task

        if intent.operation == PlanEditOperation.UNDO_LAST_EDIT:
            checkpoint = task.plan_undo
            if checkpoint is None:
                raise ValueError("there is no unfulfilled plan edit to undo")
            if checkpoint.fulfillment_event_count != len(task.fulfillment_events):
                raise ValueError("the latest edit can no longer be undone after fulfillment")
            restored = checkpoint.policy.model_copy(deep=True)
            restored.primary_plan.version = plan.version + 1
            task.plan_undo = None
            return await self._apply_direct_policy(
                task,
                intent,
                restored,
                create_undo=False,
            )

        task.pending_plan_edit = intent
        task.messages.append(ChatMessage(role="user", content=intent.instruction))
        task.phase = TaskPhase.UNDERSTANDING
        task.question = None
        await self._save(task)
        return task

    async def _apply_direct_policy(
        self,
        task: TaskSnapshot,
        intent: PlanEditIntent,
        proposed_policy: PlanPolicy,
        *,
        create_undo: bool = True,
    ) -> TaskSnapshot:
        assert task.policy is not None
        current_policy = task.policy.model_copy(deep=True)
        current = current_policy.primary_plan
        target = proposed_policy.primary_plan
        self.planning.refresh_consumer_summary(target)
        patch = self.planning.diff(current, target, trigger_source="plan_edit")
        applied = await self.planning.apply_patch(current, patch, target)
        applied = await self.lifecycle.prepare_plan(task.id, applied)
        prepared_nodes = {node.id: node for node in applied.nodes}
        for operation in patch.operations:
            if operation.node is not None and operation.node_id in prepared_nodes:
                operation.node = prepared_nodes[operation.node_id]
        if (
            current.mandate.approved_at is not None
            and patch.authorization_effect == "within_mandate"
        ):
            applied.mandate.approved_at = current.mandate.approved_at
        proposed_policy.primary_plan = applied
        if create_undo:
            task.plan_undo = PlanUndoCheckpoint(
                policy=current_policy,
                fulfillment_event_count=len(task.fulfillment_events),
            )
        task.policy = proposed_policy
        task.last_patch = patch
        task.progress_events.append(TaskProgressEvent(
            kind="patch_completed",
            detail=patch.summary,
            revision=task.revision + 1,
        ))
        task.pending_plan_edit = None
        task.question = None
        task.messages.append(ChatMessage(role="user", content=intent.instruction))
        if applied.mandate.approved_at is not None:
            task.transaction_confirmation = self.planning.transaction_confirmation(
                task.id,
                applied,
            )
            task.phase = TaskPhase.AWAITING_TRANSACTION
        else:
            task.transaction_confirmation = None
            task.phase = TaskPhase.AWAITING_MANDATE
        await self._save(task)
        return task

    async def stop_decision(self, task: TaskSnapshot) -> TaskSnapshot:
        task.phase = TaskPhase.CANCELLED
        task.question = None
        task.messages.append(ChatMessage(role="system", content="已停止当前规划。"))
        await self._save(task)
        return task

    async def set_phase(
        self,
        task: TaskSnapshot,
        phase: TaskPhase,
    ) -> TaskSnapshot:
        """Publish a meaningful decision stage without leaking agent internals."""
        if task.phase == phase:
            return task
        task.phase = phase
        await self._save(task)
        return task

    async def record_progress(
        self,
        task: TaskSnapshot,
        *,
        kind: str,
        detail: str,
        capability_id: str | None = None,
    ) -> TaskSnapshot:
        task.progress_events.append(TaskProgressEvent(
            kind=kind,
            detail=detail,
            revision=task.revision + 1,
            capability_id=capability_id,
        ))
        await self._save(task)
        return task

    async def save_live_refresh(self, task: TaskSnapshot) -> TaskSnapshot:
        """Persist a refreshed live projection without changing plan semantics."""
        await self._save(task)
        return task

    async def fail_decision(
        self,
        task: TaskSnapshot,
        message: str,
    ) -> TaskSnapshot:
        task.phase = TaskPhase.FAILED
        task.question = None
        task.messages.append(ChatMessage(role="agent", content=message))
        await self._save(task)
        return task

    async def apply_turn(self, task: TaskSnapshot, turn: AgentTurn) -> TaskSnapshot:
        task.goal = self._normalize_goal_labels(turn.goal)
        task.intent_path = turn.intent_path
        task.messages.append(ChatMessage(role="agent", content=turn.message))
        task.question = turn.question
        if turn.feasible_plan_set is not None:
            task.feasible_plan_set = turn.feasible_plan_set
        if turn.kind == TurnKind.CLARIFY:
            task.phase = TaskPhase.CLARIFYING
        elif turn.kind == TurnKind.PROPOSE:
            if turn.policy is None:
                raise ValueError("proposal has no plan policy")
            proposed_policy = turn.policy.model_copy(deep=True)
            proposed = proposed_policy.primary_plan
            proposed = proposed.model_copy(update={"goal": task.goal}, deep=True)
            if task.policy is not None:
                current = task.policy.primary_plan
                if task.pending_plan_edit is not None:
                    task.plan_undo = PlanUndoCheckpoint(
                        policy=task.policy.model_copy(deep=True),
                        fulfillment_event_count=len(task.fulfillment_events),
                    )
                proposed = proposed.model_copy(
                    update={"version": current.version + 1},
                    deep=True,
                )
                proposed = self.planning.preserve_locked_nodes(current, proposed)
                trigger_source = (
                    "plan_edit"
                    if task.pending_plan_edit is not None
                    else "supply_event"
                    if task.supply_signals
                    or any(item.status == "failed" for item in task.fulfillment_events)
                    else "goal_edit"
                )
                patch = self.planning.diff(
                    current,
                    proposed,
                    trigger_source=trigger_source,
                )
                proposed = await self.planning.apply_patch(current, patch, proposed)
                task.last_patch = patch
                if (
                    current.mandate.approved_at is not None
                    and patch.authorization_effect == "within_mandate"
                ):
                    proposed.mandate.approved_at = current.mandate.approved_at
            validation = await self.planning.validate(proposed)
            if not validation.valid:
                detail = "; ".join(issue.message for issue in validation.issues)
                raise ValueError(f"agent proposed an invalid plan: {detail}")
            proposed_policy.primary_plan = proposed
            proposed_policy.primary_plan = await self.lifecycle.prepare_plan(
                task.id,
                proposed_policy.primary_plan,
            )
            if task.last_patch is not None:
                prepared_nodes = {
                    node.id: node for node in proposed_policy.primary_plan.nodes
                }
                for operation in task.last_patch.operations:
                    if operation.node is not None and operation.node_id in prepared_nodes:
                        operation.node = prepared_nodes[operation.node_id]
            task.policy = proposed_policy
            if proposed.mandate.approved_at is not None:
                task.transaction_confirmation = self.planning.transaction_confirmation(
                    task.id,
                    proposed,
                )
                task.phase = TaskPhase.AWAITING_TRANSACTION
            else:
                task.transaction_confirmation = None
                task.phase = TaskPhase.AWAITING_MANDATE
            task.question = None
            task.pending_plan_edit = None
        else:
            task.phase = (
                TaskPhase.NEEDS_REPLAN
                if turn.feasible_plan_set is not None
                and turn.feasible_plan_set.status == "infeasible"
                else TaskPhase.UNSUPPORTED
            )
            task.pending_plan_edit = None
        changed = await self.preferences.ingest(task.user_id, turn.preference_evidence)
        task.applied_preference_fact_ids = [item.id for item in changed]
        await self._save(task)
        return task

    async def approve_mandate(self, task: TaskSnapshot) -> TaskSnapshot:
        if task.policy is None:
            raise ValueError("task has no plan")
        task.policy.primary_plan = self.planning.approve_mandate(
            task.policy.primary_plan
        )
        task.transaction_confirmation = self.planning.transaction_confirmation(
            task.id, task.policy.primary_plan
        )
        task.phase = TaskPhase.AWAITING_TRANSACTION
        task.messages.append(ChatMessage(
            role="system",
            content="执行边界已批准。免费预约可以执行，支付动作等待单独确认。",
        ))
        await self._save(task)
        return task

    async def confirm_transaction(self, task: TaskSnapshot) -> TaskSnapshot:
        if task.policy is None or task.transaction_confirmation is None:
            raise ValueError("task has no transaction proposal")
        task.policy.primary_plan, task.transaction_confirmation = (
            self.planning.approve_transaction(
                task.policy.primary_plan,
                task.transaction_confirmation,
            )
        )
        task.phase = TaskPhase.EXECUTING
        task.messages.append(ChatMessage(
            role="system",
            content=(
                f"已确认最高 ¥{task.transaction_confirmation.total_cap_yuan} "
                "的交易动作，开始履约。"
            ),
        ))
        await self._save(task)
        return task

    async def set_workflow(self, task: TaskSnapshot, workflow_id: str) -> TaskSnapshot:
        task.workflow_id = workflow_id
        await self._save(task)
        return task

    async def set_observation_workflow(
        self,
        task: TaskSnapshot,
        workflow_id: str,
    ) -> TaskSnapshot:
        task.observation_workflow_id = workflow_id
        await self._save(task)
        return task

    async def record_trace(self, task: TaskSnapshot, trace: ToolTrace) -> TaskSnapshot:
        task.tool_traces.append(trace)
        await self._save(task)
        return task

    async def record_system_message(
        self,
        task: TaskSnapshot,
        content: str,
    ) -> TaskSnapshot:
        task.messages.append(ChatMessage(role="system", content=content))
        await self._save(task)
        return task

    async def apply_policy_fallback(
        self,
        task: TaskSnapshot,
        node_id: str,
    ) -> tuple[TaskSnapshot, bool]:
        if task.policy is None:
            return task, False
        result = await self.planning.activate_fallback(task.policy, node_id)
        if result is None:
            return task, False
        task.policy, task.last_patch = result
        task.policy.primary_plan = await self.lifecycle.prepare_plan(
            task.id,
            task.policy.primary_plan,
        )
        task.messages.append(ChatMessage(
            role="agent",
            content=f"已触发预先核验的局部候补：{task.last_patch.summary}",
        ))
        if task.last_patch.authorization_effect == "within_mandate":
            previous_confirmation = task.transaction_confirmation
            refreshed = self.planning.transaction_confirmation(
                task.id,
                task.policy.primary_plan,
            )
            if (
                previous_confirmation is not None
                and previous_confirmation.confirmed_at is not None
                and refreshed.total_cap_yuan <= previous_confirmation.total_cap_yuan
            ):
                refreshed.confirmed_at = previous_confirmation.confirmed_at
                task.transaction_confirmation = refreshed
                task.phase = TaskPhase.EXECUTING
            else:
                task.transaction_confirmation = refreshed
                task.phase = TaskPhase.AWAITING_TRANSACTION
        else:
            task.transaction_confirmation = None
            task.phase = TaskPhase.AWAITING_MANDATE
        await self._save(task)
        return task, True

    async def record_event(self, task: TaskSnapshot, event: FulfillmentEvent) -> TaskSnapshot:
        task.fulfillment_events.append(event)
        if task.policy:
            plan = task.policy.primary_plan
            node = next((item for item in plan.nodes if item.id == event.node_id), None)
            if node:
                if node.supply_reference and event.lifecycle_stage is not None:
                    node.supply_reference.stage = event.lifecycle_stage
                    node.supply_reference.updated_at = event.occurred_at
                    if event.status == "compensated":
                        capability = next(
                            item
                            for item in load_capability_catalog().capabilities
                            if item.id == node.capability_id
                        )
                        original = next(
                            (
                                source
                                for source, compensation in capability.lifecycle.compensation_actions.items()
                                if compensation == event.action
                            ),
                            None,
                        )
                        if original is not None:
                            node.supply_reference.commitments.pop(original, None)
                        node.supply_reference.commitment_id = next(
                            reversed(node.supply_reference.commitments.values()),
                            None,
                        )
                    elif event.lifecycle_stage.value == "committed":
                        node.supply_reference.commitment_id = event.receipt_id
                        if event.receipt_id:
                            node.supply_reference.commitments[event.action] = event.receipt_id
                if event.status == "started":
                    node.status = NodeStatus.EXECUTING
                elif event.status == "failed":
                    node.status = NodeStatus.FAILED
                elif event.status == "compensated":
                    node.status = NodeStatus.COMPENSATED
                elif event.status == "succeeded":
                    successful_actions = {
                        item.action
                        for item in task.fulfillment_events
                        if item.node_id == node.id and item.status == "succeeded"
                    }
                    if set(node.actions).issubset(successful_actions):
                        # External commands secure the commitment; the lived activity
                        # remains in progress until reality reports its completion.
                        node.status = NodeStatus.EXECUTING

        task.live = self.live.evolve(task, event=event)
        if event.status == "failed":
            task.phase = TaskPhase.NEEDS_REPLAN
            task.messages.append(ChatMessage(
                role="system",
                content=f"现实发生变化：{event.detail}。Agent 将保留已完成动作并局部重规划。",
            ))
        elif task.policy and all(
            node.status in {NodeStatus.COMPLETED, NodeStatus.COMPENSATED}
            for node in task.policy.primary_plan.nodes
        ):
            completed = [
                node for node in task.policy.primary_plan.nodes
                if node.status == NodeStatus.COMPLETED
            ]
            task.phase = TaskPhase.COMPLETED if completed else TaskPhase.CANCELLED
            task.messages.append(ChatMessage(
                role="agent",
                content=(
                    "计划已经全部履约完成。所有订单、时间和实际费用都已归档。"
                    if completed
                    else "任务已取消，相关预约、订单或票券已经处理。"
                ),
            ))
            if task.phase == TaskPhase.COMPLETED:
                task.outcome_check_in = OutcomeCheckIn(
                    prompt=(
                        f"这次“{task.policy.primary_plan.goal.outcome}”"
                        "达到你想要的效果了吗？"
                    ),
                )
        elif (
            task.transaction_confirmation is None
            or task.transaction_confirmation.confirmed_at is None
        ):
            task.phase = TaskPhase.AWAITING_TRANSACTION
        else:
            task.phase = TaskPhase.EXECUTING
        await self._save(task)
        return task

    async def record_signal(
        self,
        task: TaskSnapshot,
        signal: SupplySignal,
    ) -> TaskSnapshot:
        task.supply_signals.append(signal)
        task.live = self.live.evolve(task, signal=signal)
        task.phase = TaskPhase.NEEDS_REPLAN
        task.messages.append(ChatMessage(
            role="system",
            content=f"Agent 主动观察到现实变化：{signal.detail}",
        ))
        await self._save(task)
        return task

    async def record_reality_event(
        self,
        task: TaskSnapshot,
        event: RealityEvent,
    ) -> tuple[TaskSnapshot, list[str]]:
        if task.policy is None:
            raise ValueError("task has no active plan")
        if event.task_id != task.id:
            raise ValueError("reality event belongs to another task")
        plan = task.policy.primary_plan
        if event.kind == "node_completed":
            if event.node_id is None:
                raise ValueError("node completion requires a node id")
            node = next((item for item in plan.nodes if item.id == event.node_id), None)
            if node is None:
                raise ValueError("completed node does not belong to the active plan")
            if node.status not in {NodeStatus.APPROVED, NodeStatus.EXECUTING}:
                raise ValueError("only an active plan node can be completed")
            if not self.live.accepts_completion(task, node, event.completion_evidence):
                _, hint = self.live.completion_window(node)
                raise ValueError(hint)
            node.status = NodeStatus.COMPLETED
            task.reality_events.append(event)
            task.live = self.live.evolve(task)
            task.live.agent_activity = event.detail
            if all(
                item.status in {NodeStatus.COMPLETED, NodeStatus.COMPENSATED}
                for item in plan.nodes
            ):
                task.phase = TaskPhase.COMPLETED
                task.messages.append(ChatMessage(
                    role="agent",
                    content="生活目标已经在现实中完成，实际结果已归档。",
                ))
                task.outcome_check_in = OutcomeCheckIn(
                    prompt=f"这次“{plan.goal.outcome}”达到你想要的效果了吗？",
                )
            else:
                task.phase = TaskPhase.EXECUTING
            await self._save(task)
            return task, [node.id]
        capability_by_id = {
            capability.id: capability
            for capability in load_capability_catalog().capabilities
        }
        affected = [
            node
            for node in plan.nodes
            if (
                event.node_id is not None and node.id == event.node_id
                or event.supply_id is not None and node.option_id == event.supply_id
                or event.node_id is None
                and event.supply_id is None
                and event.kind
                in capability_by_id[node.capability_id].lifecycle.observable_signals
            )
            and node.status not in {NodeStatus.COMPLETED, NodeStatus.COMPENSATED}
        ]
        if not affected:
            raise ValueError("reality event does not affect an active plan node")
        if event.kind == "location_change" and event.location:
            current_location = next(
                (item for item in task.goal.context_facts if item.key == "current_location"),
                None,
            ) if task.goal else None
            if current_location is None and task.goal is not None:
                task.goal.context_facts.append(ContextFact(
                    key="current_location",
                    label="当前位置",
                    value=event.location,
                    source=ValueSource.EXPLICIT,
                ))
            elif current_location is not None:
                current_location.value = event.location
                current_location.source = ValueSource.EXPLICIT
        task.reality_events.append(event)
        for node in affected:
            task.supply_signals.append(SupplySignal(
                supply_id=node.option_id,
                kind=event.kind,
                detail=event.detail,
                world_version=node.evidence.inventory_version,
                magnitude=event.magnitude,
                observed_at=event.occurred_at,
            ))
        task.live = self.live.evolve(task, signal=task.supply_signals[-1])
        task.live.affected_node_ids = [node.id for node in affected]
        task.phase = TaskPhase.NEEDS_REPLAN
        task.messages.append(ChatMessage(
            role="system",
            content=f"Agent 主动观察到现实事件：{event.detail}",
        ))
        await self._save(task)
        return task, [node.id for node in affected]

    async def record_outcome_check_in(
        self,
        task: TaskSnapshot,
        response: str,
        note: str | None = None,
    ) -> TaskSnapshot:
        if (
            task.phase != TaskPhase.COMPLETED
            or task.outcome_check_in is None
            or task.live is None
            or task.live.actual_outcome is None
        ):
            raise ValueError("task is not waiting for an outcome check-in")
        if task.outcome_check_in.response is not None:
            raise ValueError("outcome check-in was already recorded")
        task.outcome_check_in.response = response
        task.outcome_check_in.note = note
        task.outcome_check_in.responded_at = utc_now()
        task.live.actual_outcome.goal_attainment = response
        evidence: list[PreferenceEvidence] = []
        if response in {"achieved", "partly"} and task.goal is not None:
            confidence = 0.7 if response == "achieved" else 0.5
            evidence = [
                PreferenceEvidence(
                    context_scope=task.context_scope,
                    dimension=f"fulfilled_goal:{preference}",
                    preference=preference,
                    source="fulfillment_outcome",
                    confidence=confidence,
                    task_id=task.id,
                )
                for preference in task.goal.preferences
            ]
        task.live.actual_outcome.preference_evidence = evidence
        changed = await self.preferences.ingest(task.user_id, evidence)
        task.applied_preference_fact_ids = [item.id for item in changed]
        copy = {
            "achieved": "目标效果已确认达成",
            "partly": "已记录：这次只达成了一部分",
            "not_achieved": "已记录：动作完成了，但目标效果没有达成",
        }
        task.messages.append(ChatMessage(role="agent", content=copy[response]))
        await self._save(task)
        return task

    async def apply_user_delay(
        self,
        task: TaskSnapshot,
        event: RealityEvent,
    ) -> tuple[TaskSnapshot, bool]:
        if task.policy is None or event.kind != "user_late" or event.magnitude <= 0:
            return task, False
        current = task.policy.primary_plan
        pending = next(
            (
                node for node in current.nodes
                if node.status not in {NodeStatus.COMPLETED, NodeStatus.COMPENSATED}
            ),
            None,
        )
        if pending is None:
            return task, False
        try:
            target = await self.planning.delay_target(
                current,
                pending.id,
                event.magnitude,
            )
            patch = self.planning.diff(current, target, trigger_source="supply_event")
            applied = await self.planning.apply_patch(current, patch, target)
        except ValueError:
            return task, False
        applied = await self.lifecycle.prepare_plan(task.id, applied)
        if (
            current.mandate.approved_at is not None
            and patch.authorization_effect == "within_mandate"
        ):
            applied.mandate.approved_at = current.mandate.approved_at
        task.policy.primary_plan = applied
        task.policy.alternatives = []
        changed_node_ids = {operation.node_id for operation in patch.operations}
        task.policy.decision_points = [
            point
            for point in task.policy.decision_points
            if any(node.id == point.node_id for node in applied.nodes)
            and point.node_id not in changed_node_ids
        ]
        task.last_patch = patch
        task.messages.append(ChatMessage(
            role="agent",
            content=(
                f"已先消化晚到的 {event.magnitude} 分钟，只顺延发生冲突的后继节点。"
            ),
        ))
        if applied.mandate.approved_at is not None:
            task.transaction_confirmation = self.planning.transaction_confirmation(
                task.id,
                applied,
            )
            task.phase = TaskPhase.AWAITING_TRANSACTION
        else:
            task.phase = TaskPhase.AWAITING_MANDATE
        await self._save(task)
        return task, True

    async def _save(self, task: TaskSnapshot, *, create: bool = False) -> None:
        expected_revision = None if create else task.revision
        task.advance()
        await self.store.save(
            self.task_namespace,
            task.id,
            task.model_dump(mode="json"),
            expected_revision=expected_revision,
        )
