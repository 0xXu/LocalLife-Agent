from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.domain.models import (
    ActualOutcome,
    FulfillmentEvent,
    LiveState,
    LiveStep,
    NodeStatus,
    SupplySignal,
    TaskSnapshot,
    utc_now,
)
from backend.mcp.catalog import CapabilityCatalog


class LiveCompanionModule:
    """Projects execution events and world signals into one actionable live state."""

    def __init__(self, catalog: CapabilityCatalog) -> None:
        self.capabilities = {item.id: item for item in catalog.capabilities}

    def completion_window(self, node) -> tuple[bool, str]:
        rule = self.capabilities[node.capability_id].lifecycle.completion
        now = datetime.now(ZoneInfo(rule.timezone))
        start_hour, start_minute = map(int, node.starts_at.split(":"))
        end_hour, end_minute = map(int, node.ends_at.split(":"))
        start = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        end = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        if end < start:
            end += timedelta(days=1)
        earliest = start + timedelta(
            minutes=rule.user_confirmation_earliest_minutes_from_start
        )
        latest = end + timedelta(
            minutes=rule.user_confirmation_latest_minutes_from_end
        )
        if now < earliest:
            return False, f"{earliest.strftime('%H:%M')} 后可确认现实完成"
        if now > latest:
            return False, "完成确认窗口已结束，请等待供给状态更新"
        return True, "可由你确认，供给核销或到达状态也会自动完成"

    def accepts_completion(self, task: TaskSnapshot, node, evidence) -> bool:
        rule = self.capabilities[node.capability_id].lifecycle.completion
        source = evidence.source if evidence else "user_confirmation"
        if source not in rule.evidence_sources:
            return False
        if source == "provider_status":
            return bool(
                evidence
                and evidence.provider_status in rule.provider_statuses
            )
        if source == "user_confirmation":
            return self.completion_window(node)[0]
        return True

    def evolve(
        self,
        task: TaskSnapshot,
        *,
        event: FulfillmentEvent | None = None,
        signal: SupplySignal | None = None,
    ) -> LiveState:
        if task.policy is None:
            return LiveState(agent_activity="等待方案进入履约")
        plan = task.policy.primary_plan
        pending = next(
            (node for node in plan.nodes if node.status not in {NodeStatus.COMPLETED, NodeStatus.COMPENSATED}),
            None,
        )
        next_step = None
        available_actions = []
        action_node = (
            pending
            if pending and pending.supply_reference and pending.supply_reference.commitment_id
            else next(
            (
                node
                for node in reversed(plan.nodes)
                if node.supply_reference and node.supply_reference.commitment_id
            ),
            None,
            )
        )
        if pending:
            status = "blocked" if signal and pending.option_id == signal.supply_id else (
                "in_progress" if pending.status == NodeStatus.EXECUTING else "ready"
            )
            completion_available, completion_hint = self.completion_window(pending)
            next_step = LiveStep(
                node_id=pending.id,
                title=pending.title,
                instruction=f"{pending.starts_at} 前往 {pending.venue}",
                due_at=pending.starts_at,
                status=status,
                completion_available=completion_available,
                completion_hint=completion_hint,
            )
        if action_node:
            lifecycle = self.capabilities[action_node.capability_id].lifecycle
            available_actions = [
                *lifecycle.change_actions,
                *lifecycle.compensation_actions.values(),
            ]

        actual_outcome = None
        terminal = all(
            node.status in {NodeStatus.COMPLETED, NodeStatus.COMPENSATED}
            for node in plan.nodes
        )
        if terminal:
            compensated_receipts = {
                item.receipt_id
                for item in task.fulfillment_events
                if item.status == "compensated" and item.receipt_id
            }
            completed_node_ids = [
                node.id for node in plan.nodes if node.status == NodeStatus.COMPLETED
            ]
            compensated_node_ids = [
                node.id for node in plan.nodes if node.status == NodeStatus.COMPENSATED
            ]
            if not completed_node_ids and compensated_node_ids:
                summary = "任务已取消，相关预约、订单或票券已处理"
            elif compensated_node_ids:
                summary = "目标已完成，部分未发生的承诺已取消或退款"
            else:
                summary = "现实履约结果已归档"
            actual_outcome = ActualOutcome(
                total_yuan=sum(
                    item.actual_amount_yuan or 0
                    for item in task.fulfillment_events
                    if item.status == "succeeded"
                    and item.receipt_id not in compensated_receipts
                ),
                completed_node_ids=completed_node_ids,
                compensated_node_ids=compensated_node_ids,
                completed_at=utc_now(),
                summary=summary,
                preference_evidence=[],
            )

        if signal:
            activity = f"已观察到变化：{signal.detail}，正在保护未受影响的承诺"
        elif event:
            activity = event.detail
        elif actual_outcome:
            activity = actual_outcome.summary
        else:
            activity = "持续观察库存、时间与履约状态"
        return LiveState(
            next_step=next_step,
            risk=signal.detail if signal else None,
            affected_node_ids=(
                [node.id for node in plan.nodes if signal and node.option_id == signal.supply_id]
            ),
            agent_activity=activity,
            waiting_for="局部重规划" if signal else None,
            available_actions=list(dict.fromkeys(available_actions)),
            last_signal=signal,
            actual_outcome=actual_outcome,
        )
