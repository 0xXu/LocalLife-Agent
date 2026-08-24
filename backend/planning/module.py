from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.domain.models import (
    ActionKind,
    DecisionPoint,
    FulfillmentCommand,
    FallbackPolicy,
    FeasiblePlanCandidate,
    FeasiblePlanSet,
    GoalContract,
    GroundedCandidateSet,
    NodeStatus,
    PlanAlternative,
    PlanGraph,
    PlanEditIntent,
    PlanEditOperation,
    PlanPatch,
    PlanPatchOperation,
    PlanPolicy,
    PlanNode,
    ExecutionMandate,
    SupplyOption,
    TemporalConstraint,
    TransactionConfirmation,
    TransactionLine,
    TriggerCondition,
    utc_now,
)
from backend.planning.feasibility import FeasibilitySolver
from backend.planning.recovery import RecoveryCandidate, RecoveryEnumerator
from backend.mcp import load_capability_catalog
from backend.supply import SupplyTwin


class PlanIssue(BaseModel):
    code: str
    message: str
    node_id: str | None = None
    severity: Literal["blocking", "warning"] = "blocking"


class PlanValidation(BaseModel):
    valid: bool
    issues: list[PlanIssue] = Field(default_factory=list)


def _minutes(value: str) -> int:
    parsed = datetime.strptime(value, "%H:%M")
    return parsed.hour * 60 + parsed.minute


def _clock(value: int) -> str:
    if not 0 <= value < 24 * 60:
        raise ValueError("plan edit moved a node outside the same calendar day")
    return f"{value // 60:02d}:{value % 60:02d}"


class PlanningModule:
    """Owns every invariant of a PlanGraph and exposes only validated transitions."""

    free_actions = {
        ActionKind.RESERVE_TABLE,
        ActionKind.START_NAVIGATION,
    }
    transaction_labels = {
        ActionKind.BUY_COUPON: "购买餐饮优惠券",
        ActionKind.BUY_TICKET: "购买娱乐门票",
        ActionKind.REQUEST_RIDE: "授权叫车费用上限",
        ActionKind.BOOK_SERVICE: "预约到店服务",
        ActionKind.PLACE_ORDER: "提交配送订单",
    }

    def __init__(self, supply: SupplyTwin) -> None:
        self.supply = supply
        self.feasibility = FeasibilitySolver()
        self.recovery = RecoveryEnumerator(self.feasibility)
        self.minimum_commitments = {
            capability.id: capability.planning.minimum_commitments
            for capability in load_capability_catalog().capabilities
        }

    def solve(
        self,
        goal: GoalContract,
        candidate_sets: list[GroundedCandidateSet],
        temporal_constraints: list[TemporalConstraint],
    ) -> FeasiblePlanSet:
        return self.feasibility.solve(goal, candidate_sets, temporal_constraints)

    def recover(
        self,
        goal: GoalContract,
        candidate_sets: list[GroundedCandidateSet],
        temporal_constraints: list[TemporalConstraint],
        infeasible: FeasiblePlanSet,
    ) -> list[RecoveryCandidate]:
        return self.recovery.enumerate(
            goal,
            candidate_sets,
            temporal_constraints,
            infeasible,
        )

    async def materialize_policy(
        self,
        goal: GoalContract,
        feasible_set: FeasiblePlanSet,
        candidate_id: str,
        alternative_candidate_ids: list[str],
        *,
        title: str,
        selection_reasons: dict[str, str],
        supply_evidence: dict[str, SupplyOption] | None = None,
    ) -> PlanPolicy:
        candidate_index = {item.id: item for item in feasible_set.candidates}
        if candidate_id not in feasible_set.pareto_candidate_ids:
            raise ValueError("planner selected a candidate outside the Pareto frontier")
        primary_candidate = candidate_index[candidate_id]
        alternatives = [
            candidate_index[item]
            for item in alternative_candidate_ids
            if item in feasible_set.pareto_candidate_ids and item != candidate_id
        ][:2]
        primary_plan = await self._materialize_candidate(
            goal,
            primary_candidate,
            title=title,
            selection_reasons=selection_reasons,
            alternatives=alternatives,
            supply_evidence=supply_evidence or {},
        )
        plan_alternatives = [
            self._describe_alternative(primary_candidate, item)
            for item in alternatives
        ]
        decision_points = await self._build_decision_points(
            primary_plan,
            primary_candidate,
            alternatives,
        )
        return PlanPolicy(
            primary_plan=primary_plan,
            alternatives=plan_alternatives,
            decision_points=decision_points,
        )

    async def _materialize_candidate(
        self,
        goal: GoalContract,
        candidate: FeasiblePlanCandidate,
        *,
        title: str,
        selection_reasons: dict[str, str],
        alternatives: list[FeasiblePlanCandidate],
        supply_evidence: dict[str, SupplyOption],
    ) -> PlanGraph:
        alternative_options: dict[str, list[str]] = {}
        for alternative in alternatives:
            for selection in alternative.selections:
                alternative_options.setdefault(selection.capability_id, []).append(
                    selection.option_id
                )
        nodes: list[PlanNode] = []
        capability_counts: dict[str, int] = {}
        previous_timed_node_id: str | None = None
        for selection in candidate.selections:
            option = supply_evidence.get(selection.option_id)
            if option is not None:
                option = option.model_copy(deep=True)
            else:
                option = await self.supply.get(selection.option_id)
            if option is None:
                raise ValueError(f"feasible candidate references unknown supply: {selection.option_id}")
            verified_substitutes: list[str] = []
            for alternative_id in alternative_options.get(selection.capability_id, []):
                if alternative_id == option.id:
                    continue
                alternative_option = supply_evidence.get(alternative_id)
                if alternative_option is not None:
                    alternative_option = alternative_option.model_copy(deep=True)
                else:
                    alternative_option = await self.supply.get(alternative_id)
                if alternative_option is None:
                    continue
                if (
                    option.substitution_group is not None
                    and alternative_option.substitution_group != option.substitution_group
                ):
                    continue
                verified_substitutes.append(alternative_id)
            capability_counts[selection.capability_id] = (
                capability_counts.get(selection.capability_id, 0) + 1
            )
            suffix = capability_counts[selection.capability_id]
            node_id = (
                selection.capability_id
                if suffix == 1
                else f"{selection.capability_id}_{suffix}"
            )
            node = PlanNode(
                id=node_id,
                capability_id=selection.capability_id,
                vertical=option.vertical,
                title=option.name,
                option_id=option.id,
                starts_at=selection.starts_at,
                ends_at=selection.ends_at,
                price_yuan=option.price_yuan,
                venue=option.venue,
                reason=selection_reasons.get(
                    option.id,
                    "它满足你当前的时间、预算和地点要求。",
                ),
                consumes_user_time=selection.consumes_user_time,
                trigger_kind=selection.trigger_kind,
                actions=option.actions,
                depends_on=(
                    [previous_timed_node_id]
                    if selection.consumes_user_time and previous_timed_node_id
                    else []
                ),
                alternatives=list(dict.fromkeys(verified_substitutes))[:2],
                evidence=option.evidence,
            )
            nodes.append(node)
            if selection.consumes_user_time:
                previous_timed_node_id = node.id
        schedule = "；".join(
            f"{node.starts_at} {node.title}（¥{node.price_yuan}）" for node in nodes
        )
        thesis = (
            f"{schedule}。预计总计 ¥{candidate.objectives.total_yuan}，"
            f"保留 {candidate.slack_minutes} 分钟整体余量。"
        )
        return PlanGraph(
            title=title,
            thesis=thesis,
            goal=goal,
            nodes=nodes,
            total_yuan=candidate.objectives.total_yuan,
            rationale=[node.reason for node in nodes],
            tradeoffs=[],
            mandate=self._mandate_for(goal, nodes),
        )

    @staticmethod
    def _mandate_for(goal: GoalContract, nodes: list[PlanNode]) -> ExecutionMandate:
        return ExecutionMandate(
            max_total_yuan=goal.budget_yuan,
            deadline=goal.deadline,
            allowed_verticals=list(dict.fromkeys(node.vertical for node in nodes)),
        )

    @staticmethod
    def _describe_alternative(
        primary: FeasiblePlanCandidate,
        alternative: FeasiblePlanCandidate,
    ) -> PlanAlternative:
        left = primary.objectives
        right = alternative.objectives
        if right.total_yuan < left.total_yuan:
            direction = "cheaper"
            summary = f"少花 ¥{left.total_yuan - right.total_yuan}"
        elif right.movement_minutes < left.movement_minutes:
            direction = "less_movement"
            summary = f"少移动 {left.movement_minutes - right.movement_minutes} 分钟"
        elif right.completion_minute < left.completion_minute:
            direction = "earlier"
            summary = f"提前 {left.completion_minute - right.completion_minute} 分钟完成"
        elif right.elapsed_minutes < left.elapsed_minutes:
            direction = "less_elapsed"
            summary = f"行程压缩 {left.elapsed_minutes - right.elapsed_minutes} 分钟"
        else:
            direction = "stronger_experience"
            summary = (
                "体验评分提高 "
                f"{(right.experience_milli - left.experience_milli) / 1000:.1f}"
            )
        completion = right.completion_minute
        return PlanAlternative(
            candidate_id=alternative.id,
            direction=direction,
            summary=summary,
            total_yuan=right.total_yuan,
            completion_time=f"{completion // 60:02d}:{completion % 60:02d}",
            option_ids=[item.option_id for item in alternative.selections],
        )

    async def _build_decision_points(
        self,
        primary_plan: PlanGraph,
        primary_candidate: FeasiblePlanCandidate,
        alternatives: list[FeasiblePlanCandidate],
    ) -> list[DecisionPoint]:
        primary_by_capability = {
            selection.capability_id: selection
            for selection in primary_candidate.selections
        }
        fallback_by_capability: dict[str, FeasiblePlanCandidate] = {}
        for alternative in alternatives:
            for selection in alternative.selections:
                primary = primary_by_capability.get(selection.capability_id)
                if primary and primary.option_id != selection.option_id:
                    fallback_by_capability.setdefault(selection.capability_id, alternative)
        decision_points: list[DecisionPoint] = []
        deadline = _minutes(primary_plan.goal.deadline)
        for index, node in enumerate(primary_plan.nodes):
            next_start = (
                _minutes(primary_plan.nodes[index + 1].starts_at)
                if index + 1 < len(primary_plan.nodes)
                else deadline
            )
            slack = max(0, next_start - _minutes(node.ends_at))
            capability_id = next(
                selection.capability_id
                for selection in primary_candidate.selections
                if selection.option_id == node.option_id
            )
            fallback_candidate = fallback_by_capability.get(capability_id)
            fallbacks: list[FallbackPolicy] = []
            if fallback_candidate:
                replacement_selection = next(
                    selection
                    for selection in fallback_candidate.selections
                    if selection.capability_id == capability_id
                    and selection.option_id != node.option_id
                )
                replacement_option = await self.supply.get(replacement_selection.option_id)
                if replacement_option:
                    price_increase = replacement_option.price_yuan - node.price_yuan
                    within_mandate = (
                        primary_plan.mandate.allow_auto_substitution
                        and price_increase <= primary_plan.mandate.max_price_increase_yuan
                        and fallback_candidate.objectives.total_yuan
                        <= primary_plan.mandate.max_total_yuan
                    )
                    replacement = node.model_copy(update={
                        "title": replacement_option.name,
                        "option_id": replacement_option.id,
                        "starts_at": replacement_selection.starts_at,
                        "ends_at": replacement_selection.ends_at,
                        "price_yuan": replacement_option.price_yuan,
                        "venue": replacement_option.venue,
                        "actions": replacement_option.actions,
                        "evidence": replacement_option.evidence,
                        "reason": "主供给触发切换条件时使用的已核验候补。",
                    }, deep=True)
                    fallbacks.append(FallbackPolicy(
                        node_id=node.id,
                        replacement=replacement,
                        affected_node_ids=[
                            item.id for item in primary_plan.nodes[index + 1:]
                            if _minutes(replacement.ends_at) > _minutes(item.starts_at)
                        ],
                        authorization_effect=(
                            "within_mandate" if within_mandate
                            else "confirmation_required"
                        ),
                    ))
            trigger_kind = node.trigger_kind
            decision_lead = max(5, min(30, slack))
            decision_minute = max(0, _minutes(node.starts_at) - decision_lead)
            decision_points.append(DecisionPoint(
                node_id=node.id,
                trigger=TriggerCondition(
                    kind=trigger_kind,
                    node_id=node.id,
                    threshold=slack if trigger_kind != "inventory_unavailable" else 0,
                ),
                slack_minutes=slack,
                decision_deadline=(
                    f"{decision_minute // 60:02d}:{decision_minute % 60:02d}"
                ),
                fallbacks=fallbacks,
            ))
        return decision_points

    async def validate(self, plan: PlanGraph) -> PlanValidation:
        issues: list[PlanIssue] = []
        node_ids = {node.id for node in plan.nodes}
        options: dict[str, SupplyOption | None] = {
            node.option_id: await self.supply.get(node.option_id) for node in plan.nodes
        }

        if plan.total_yuan > plan.goal.budget_yuan:
            issues.append(PlanIssue(code="budget_exceeded", message="计划总价超过用户预算"))
        if plan.total_yuan > plan.mandate.max_total_yuan:
            issues.append(PlanIssue(code="mandate_exceeded", message="计划总价超过建议授权上限"))

        previous_end: int | None = None
        for node in plan.nodes:
            option = options[node.option_id]
            if option is None:
                issues.append(PlanIssue(
                    code="unknown_supply", message="计划引用了不存在的供给", node_id=node.id
                ))
                continue
            if option.availability.value == "unavailable":
                issues.append(PlanIssue(
                    code="supply_unavailable", message=f"{option.name} 已无库存", node_id=node.id
                ))
            if node.price_yuan != option.price_yuan:
                issues.append(PlanIssue(
                    code="stale_price",
                    message=f"{option.name} 的价格已变化",
                    node_id=node.id,
                ))
            if node.evidence.inventory_version != option.evidence.inventory_version:
                issues.append(PlanIssue(
                    code="stale_evidence",
                    message=f"{option.name} 的库存证据已过期",
                    node_id=node.id,
                ))
            if not set(node.actions).issubset(set(option.actions)):
                issues.append(PlanIssue(
                    code="unsupported_action",
                    message=f"{option.name} 不支持计划中的履约动作",
                    node_id=node.id,
                ))
            missing_dependencies = [item for item in node.depends_on if item not in node_ids]
            if missing_dependencies:
                issues.append(PlanIssue(
                    code="missing_dependency",
                    message=f"依赖节点不存在：{', '.join(missing_dependencies)}",
                    node_id=node.id,
                ))
            start = _minutes(node.starts_at)
            end = _minutes(node.ends_at)
            if end <= start:
                issues.append(PlanIssue(
                    code="invalid_time_window", message="结束时间必须晚于开始时间", node_id=node.id
                ))
            if node.consumes_user_time and previous_end is not None and start < previous_end:
                issues.append(PlanIssue(
                    code="time_overlap", message="活动时间发生冲突", node_id=node.id
                ))
            if node.consumes_user_time:
                previous_end = end

        if plan.nodes and _minutes(plan.nodes[-1].ends_at) > _minutes(plan.goal.deadline):
            issues.append(PlanIssue(
                code="deadline_missed",
                message=f"计划无法满足“{plan.goal.deadline_label} {plan.goal.deadline}”",
            ))

        return PlanValidation(valid=not any(item.severity == "blocking" for item in issues), issues=issues)

    async def edit_target(
        self,
        plan: PlanGraph,
        intent: PlanEditIntent,
    ) -> PlanGraph:
        """Translate a direct edit intent into a locally repaired target graph."""
        if intent.operation is None:
            raise ValueError("direct plan edit requires an operation")
        target = plan.model_copy(deep=True)

        if intent.operation == PlanEditOperation.ADJUST_BUDGET:
            assert intent.budget_yuan is not None
            target.goal.budget_yuan = intent.budget_yuan
            target.mandate.max_total_yuan = intent.budget_yuan
        else:
            node = next(
                (item for item in target.nodes if item.id == intent.node_id),
                None,
            )
            if node is None:
                raise ValueError(f"plan node does not exist: {intent.node_id}")

            if intent.operation == PlanEditOperation.REMOVE_NODE:
                remaining_commitments = sum(
                    item.capability_id == node.capability_id
                    for item in target.nodes
                ) - 1
                if remaining_commitments < self.minimum_commitments[node.capability_id]:
                    raise ValueError(
                        f"{node.title} is required by the current goal; replace it instead"
                    )
                inherited_dependencies = list(node.depends_on)
                target.nodes = [item for item in target.nodes if item.id != node.id]
                for downstream in target.nodes:
                    if node.id in downstream.depends_on:
                        downstream.depends_on = list(dict.fromkeys(
                            dependency
                            for current in downstream.depends_on
                            for dependency in (
                                inherited_dependencies if current == node.id else [current]
                            )
                        ))
                target.locked_node_ids = [
                    item for item in target.locked_node_ids if item != node.id
                ]
            elif intent.operation in {
                PlanEditOperation.ADJUST_NODE,
                PlanEditOperation.REPLACE_NODE,
            }:
                if intent.operation == PlanEditOperation.REPLACE_NODE:
                    if intent.option_id is None:
                        raise ValueError("replace_node without a selected option requires Agent replanning")
                    if intent.option_id not in node.alternatives:
                        raise ValueError("replacement must be one of the node's verified alternatives")
                    option = await self.supply.get(intent.option_id)
                    if option is None:
                        raise ValueError("replacement supply no longer exists")
                    previous_option_id = node.option_id
                    previous_alternatives = list(node.alternatives)
                    node.title = option.name
                    node.option_id = option.id
                    node.price_yuan = option.price_yuan
                    node.venue = option.venue
                    node.actions = option.actions
                    node.evidence = option.evidence
                    node.reason = "用户选择了该节点的已核验候选，其他部分优先保持不变。"
                    node.supply_reference = None
                    node.alternatives = list(dict.fromkeys([
                        previous_option_id,
                        *(
                            item
                            for item in previous_alternatives
                            if item != option.id
                        ),
                    ]))[:2]
                    node.ends_at = _clock(_minutes(node.starts_at) + option.duration_minutes)
                else:
                    assert intent.starts_at is not None
                    duration = _minutes(node.ends_at) - _minutes(node.starts_at)
                    node.starts_at = intent.starts_at
                    node.ends_at = _clock(_minutes(intent.starts_at) + duration)
                self._repair_downstream_schedule(target, node.id)
            else:
                raise ValueError(f"operation is not a graph edit: {intent.operation}")

        target.version = plan.version + 1
        target.total_yuan = sum(item.price_yuan for item in target.nodes)
        self.refresh_consumer_summary(target)
        target.updated_at = utc_now()
        return target

    @staticmethod
    def refresh_consumer_summary(plan: PlanGraph) -> None:
        """Project mutable graph facts into consumer copy after a local edit."""
        if not plan.nodes:
            plan.title = "待补充安排"
            plan.thesis = "当前计划没有可执行步骤。"
            return
        titles = [node.title for node in plan.nodes]
        plan.title = (
            titles[0]
            if len(titles) == 1
            else " · ".join(titles[:2])
            if len(titles) == 2
            else f"{' · '.join(titles[:2])}等 {len(titles)} 项安排"
        )
        itinerary = "，".join(
            f"{node.starts_at} {node.title}（¥{node.price_yuan}）"
            for node in plan.nodes
        )
        plan.thesis = (
            f"{itinerary}。预计总计 ¥{plan.total_yuan}，"
            f"预计 {plan.nodes[-1].ends_at} 完成。"
        )

    async def delay_target(
        self,
        plan: PlanGraph,
        node_id: str,
        delay_minutes: int,
    ) -> PlanGraph:
        if delay_minutes <= 0:
            raise ValueError("user delay must be positive")
        node = next((item for item in plan.nodes if item.id == node_id), None)
        if node is None:
            raise ValueError(f"plan node does not exist: {node_id}")
        return await self.edit_target(plan, PlanEditIntent(
            source="direct",
            instruction=f"现场晚到 {delay_minutes} 分钟",
            operation=PlanEditOperation.ADJUST_NODE,
            node_id=node_id,
            starts_at=_clock(_minutes(node.starts_at) + delay_minutes),
        ))

    @staticmethod
    def _repair_downstream_schedule(plan: PlanGraph, edited_node_id: str) -> None:
        """Push only overlapping successors, preserving unaffected time gaps."""
        edited_seen = False
        previous_end: int | None = None
        for node in plan.nodes:
            if node.id == edited_node_id:
                edited_seen = True
            if not node.consumes_user_time:
                continue
            start = _minutes(node.starts_at)
            end = _minutes(node.ends_at)
            if edited_seen and previous_end is not None and start < previous_end:
                duration = end - start
                node.starts_at = _clock(previous_end)
                node.ends_at = _clock(previous_end + duration)
                end = previous_end + duration
            previous_end = end

    def approve_mandate(self, plan: PlanGraph) -> PlanGraph:
        approved = plan.model_copy(deep=True)
        approved.mandate.approved_at = utc_now()
        approved.updated_at = utc_now()
        return approved

    def transaction_confirmation(self, task_id: str, plan: PlanGraph) -> TransactionConfirmation:
        commands = self.commands(task_id, plan, require_transaction=False)
        lines = [
            TransactionLine(
                node_id=command.node_id,
                action=command.action,
                label=self.transaction_labels[command.action],
                amount_yuan=command.amount_yuan,
            )
            for command in commands
            if command.action not in self.free_actions
        ]
        return TransactionConfirmation(
            lines=lines,
            total_cap_yuan=sum(line.amount_yuan for line in lines),
        )

    def approve_transaction(
        self,
        plan: PlanGraph,
        confirmation: TransactionConfirmation,
    ) -> tuple[PlanGraph, TransactionConfirmation]:
        approved = plan.model_copy(deep=True)
        for node in approved.nodes:
            if node.status == NodeStatus.PROPOSED:
                node.status = NodeStatus.APPROVED
        approved.updated_at = utc_now()
        confirmed = confirmation.model_copy(update={"confirmed_at": utc_now()}, deep=True)
        return approved, confirmed

    def commands(
        self,
        task_id: str,
        plan: PlanGraph,
        *,
        require_transaction: bool = True,
        transaction: TransactionConfirmation | None = None,
    ) -> list[FulfillmentCommand]:
        if plan.mandate.approved_at is None:
            raise ValueError("plan must be approved before fulfillment")
        if require_transaction and (transaction is None or transaction.confirmed_at is None):
            raise ValueError("transaction must be confirmed before paid fulfillment")
        return [
            FulfillmentCommand(
                task_id=task_id,
                node_id=node.id,
                action=action,
                option_id=node.option_id,
                amount_yuan=node.price_yuan if index == 0 else 0,
                commitment_context={
                    "title": node.title,
                    "venue": node.venue,
                    "starts_at": node.starts_at,
                    "ends_at": node.ends_at,
                },
            )
            for node in plan.nodes
            for index, action in enumerate(node.actions)
        ]

    def free_commands(self, task_id: str, plan: PlanGraph) -> list[FulfillmentCommand]:
        return [
            command
            for command in self.commands(task_id, plan, require_transaction=False)
            if command.action in self.free_actions
        ]

    def paid_commands(
        self,
        task_id: str,
        plan: PlanGraph,
        transaction: TransactionConfirmation,
    ) -> list[FulfillmentCommand]:
        return [
            command
            for command in self.commands(task_id, plan, transaction=transaction)
            if command.action not in self.free_actions
        ]

    def diff(
        self,
        current: PlanGraph,
        proposed: PlanGraph,
        *,
        trigger_source: Literal[
            "goal_edit", "plan_edit", "supply_event", "policy_trigger"
        ],
    ) -> PlanPatch:
        current_nodes = {node.id: node for node in current.nodes}
        proposed_nodes = {node.id: node for node in proposed.nodes}
        operations: list[PlanPatchOperation] = []

        for node_id, node in current_nodes.items():
            replacement = proposed_nodes.get(node_id)
            if replacement is None:
                operations.append(PlanPatchOperation(
                    operation="remove",
                    node_id=node_id,
                    reason=f"移除 {node.title}",
                ))
            elif replacement.model_dump(
                exclude={
                    "status",
                    "evidence",
                    "supply_reference",
                    "reason",
                    "alternatives",
                }
            ) != node.model_dump(
                exclude={
                    "status",
                    "evidence",
                    "supply_reference",
                    "reason",
                    "alternatives",
                }
            ):
                operations.append(PlanPatchOperation(
                    operation="replace",
                    node_id=node_id,
                    node=replacement,
                    reason=f"{node.title} 的供给、时间或费用发生变化",
                ))

        for node_id, node in proposed_nodes.items():
            if node_id not in current_nodes:
                operations.append(PlanPatchOperation(
                    operation="add",
                    node_id=node_id,
                    node=node,
                    reason=f"新增 {node.title}",
                ))

        commitment_changed = any(
            operation.node_id in current_nodes
            and current_nodes[operation.node_id].status in {
                NodeStatus.EXECUTING,
                NodeStatus.COMPLETED,
                NodeStatus.COMPENSATED,
            }
            for operation in operations
        )
        changed_verticals = {
            operation.node.vertical
            for operation in operations
            if operation.node is not None
        }
        within_mandate = (
            current.mandate.allow_auto_substitution
            and not commitment_changed
            and proposed.total_yuan <= current.mandate.max_total_yuan
            and proposed.total_yuan - current.total_yuan
            <= current.mandate.max_price_increase_yuan
            and changed_verticals.issubset(set(current.mandate.allowed_verticals))
            and _minutes(proposed.goal.deadline) <= _minutes(current.mandate.deadline)
        )
        authorization_effect = (
            "within_mandate" if within_mandate else "confirmation_required"
        )
        return PlanPatch(
            from_version=current.version,
            to_version=current.version + 1,
            summary=(
                f"计划共 {len(operations)} 处变化，"
                f"总价从 ¥{current.total_yuan} 调整为 ¥{proposed.total_yuan}"
            ),
            operations=operations,
            requires_confirmation=authorization_effect == "confirmation_required",
            trigger_source=trigger_source,
            authorization_effect=authorization_effect,
        )

    async def activate_fallback(
        self,
        policy: PlanPolicy,
        node_id: str,
    ) -> tuple[PlanPolicy, PlanPatch] | None:
        """Apply one pre-verified local branch; affected downstream nodes require a re-solve."""
        decision = next(
            (item for item in policy.decision_points if item.node_id == node_id),
            None,
        )
        if decision is None:
            return None
        fallback = next(
            (item for item in decision.fallbacks if not item.affected_node_ids),
            None,
        )
        if fallback is None:
            return None
        current = policy.primary_plan
        replacement = fallback.replacement.model_copy(deep=True)
        replacement.status = (
            NodeStatus.APPROVED
            if current.mandate.approved_at is not None
            else NodeStatus.PROPOSED
        )
        nodes = [
            replacement if item.id == node_id else item.model_copy(deep=True)
            for item in current.nodes
        ]
        target = current.model_copy(
            update={
                "version": current.version + 1,
                "nodes": nodes,
                "total_yuan": sum(item.price_yuan for item in nodes),
                "thesis": (
                    f"{current.thesis} 已按现实触发条件将"
                    f"{next(item.title for item in current.nodes if item.id == node_id)}"
                    f"替换为{replacement.title}。"
                ),
            },
            deep=True,
        )
        patch = self.diff(current, target, trigger_source="policy_trigger")
        applied = await self.apply_patch(current, patch, target)
        if (
            current.mandate.approved_at is not None
            and patch.authorization_effect == "within_mandate"
        ):
            applied.mandate.approved_at = current.mandate.approved_at
        updated = policy.model_copy(
            update={
                "primary_plan": applied,
                "decision_points": [
                    item for item in policy.decision_points if item.node_id != node_id
                ],
            },
            deep=True,
        )
        return updated, patch

    def preserve_locked_nodes(
        self,
        current: PlanGraph,
        proposed: PlanGraph,
    ) -> PlanGraph:
        """Make node locks an invariant before a candidate becomes a patch."""
        locked = set(current.locked_node_ids)
        current_nodes = {node.id: node for node in current.nodes}
        proposed_nodes = {node.id: node for node in proposed.nodes}
        for node_id in locked:
            proposed_nodes[node_id] = current_nodes[node_id].model_copy(deep=True)
        order = [node.id for node in proposed.nodes]
        order.extend(node.id for node in current.nodes if node.id in locked and node.id not in order)
        nodes = [proposed_nodes[node_id] for node_id in order]
        return proposed.model_copy(
            update={
                "nodes": nodes,
                "total_yuan": sum(node.price_yuan for node in nodes),
                "locked_node_ids": sorted(locked),
            },
            deep=True,
        )

    async def apply_patch(
        self,
        plan: PlanGraph,
        patch: PlanPatch,
        target: PlanGraph,
    ) -> PlanGraph:
        if patch.from_version != plan.version or patch.to_version != plan.version + 1:
            raise ValueError("patch version does not continue the current plan")
        nodes = {node.id: node.model_copy(deep=True) for node in plan.nodes}
        order = [node.id for node in plan.nodes]
        for operation in patch.operations:
            current = nodes.get(operation.node_id)
            if operation.node_id in plan.locked_node_ids:
                raise ValueError(f"locked node cannot be changed: {operation.node_id}")
            if current and current.status in {
                NodeStatus.EXECUTING,
                NodeStatus.COMPLETED,
                NodeStatus.COMPENSATED,
            }:
                raise ValueError(f"committed node cannot be replaced: {operation.node_id}")
            if operation.operation == "remove":
                nodes.pop(operation.node_id, None)
                order = [item for item in order if item != operation.node_id]
            elif operation.operation in {"add", "replace", "update"}:
                if operation.node is None:
                    raise ValueError(f"{operation.operation} requires a node")
                nodes[operation.node_id] = operation.node
                if operation.node_id not in order:
                    order.append(operation.node_id)

        changed = plan.model_copy(
            update={
                "version": patch.to_version,
                "nodes": [nodes[item] for item in order if item in nodes],
                "title": target.title,
                "thesis": target.thesis,
                "goal": target.goal,
                "rationale": target.rationale,
                "tradeoffs": target.tradeoffs,
                "mandate": target.mandate,
                "locked_node_ids": target.locked_node_ids,
                "updated_at": utc_now(),
            },
            deep=True,
        )
        changed.total_yuan = sum(node.price_yuan for node in changed.nodes)
        validation = await self.validate(changed)
        if not validation.valid:
            detail = "; ".join(issue.message for issue in validation.issues)
            raise ValueError(f"patched plan is invalid: {detail}")
        return PlanGraph.model_validate(changed.model_dump())
