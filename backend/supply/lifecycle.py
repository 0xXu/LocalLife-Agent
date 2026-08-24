from __future__ import annotations

from datetime import timedelta

from backend.domain.models import (
    ActionKind,
    Availability,
    FulfillmentCommand,
    FulfillmentEvent,
    PlanGraph,
    SupplyLifecycleStage,
    SupplyReference,
    SupplySignal,
    utc_now,
)
from backend.mcp.catalog import CapabilityCatalog
from backend.storage import DocumentStore
from backend.supply.twin import SupplyTwin
from backend.supply.outbound import AiOutboundCallAdapter


class SupplyLifecycleModule:
    """Keeps one stable supply identity from quote through after-sales."""

    namespace = "supply_references"

    def __init__(
        self,
        store: DocumentStore,
        supply: SupplyTwin,
        catalog: CapabilityCatalog,
        outbound: AiOutboundCallAdapter | None = None,
    ) -> None:
        self.store = store
        self.supply = supply
        self.catalog = catalog
        self.outbound = outbound

    async def prepare_plan(self, task_id: str, plan: PlanGraph) -> PlanGraph:
        prepared = plan.model_copy(deep=True)
        for node in prepared.nodes:
            persisted = await self._load(task_id, node.id)
            if (
                node.supply_reference is not None
                and node.supply_reference.supply_id == node.option_id
                and node.supply_reference.stage not in {
                    SupplyLifecycleStage.EXPIRED,
                    SupplyLifecycleStage.CANCELLED,
                    SupplyLifecycleStage.REFUNDED,
                }
                and persisted is not None
                and persisted.supply_id == node.option_id
                and persisted.stage not in {
                    SupplyLifecycleStage.EXPIRED,
                    SupplyLifecycleStage.CANCELLED,
                    SupplyLifecycleStage.REFUNDED,
                }
            ):
                node.supply_reference = persisted
                continue
            reference = await self.quote_and_hold(
                task_id=task_id,
                node_id=node.id,
                capability_id=node.capability_id,
                supply_id=node.option_id,
            )
            node.supply_reference = reference
        return prepared

    async def quote_and_hold(
        self,
        *,
        task_id: str,
        node_id: str,
        capability_id: str,
        supply_id: str,
    ) -> SupplyReference:
        option = await self.supply.get(supply_id)
        if option is None or option.availability == Availability.UNAVAILABLE:
            raise ValueError(f"supply unavailable before hold: {supply_id}")
        capability = next(
            item for item in self.catalog.capabilities if item.id == capability_id
        )
        world_version = await self.supply.world_version()
        lifecycle = capability.lifecycle
        reference = SupplyReference(
            task_id=task_id,
            node_id=node_id,
            capability_id=capability_id,
            supply_id=option.id,
            stage=SupplyLifecycleStage.HELD,
            quote_id=f"quote_{reference_token(task_id, node_id, world_version)}",
            hold_id=f"hold_{reference_token(task_id, node_id, world_version)}",
            quoted_total_yuan=option.price_yuan,
            hold_expires_at=utc_now() + timedelta(seconds=lifecycle.hold_ttl_seconds),
            world_version=world_version,
            terms=[
                f"价格与库存占位 {lifecycle.hold_ttl_seconds} 秒",
                "提交前按能力目录要求刷新",
            ],
        )
        if (
            lifecycle.offline_verification
            and option.metadata.get("booking_channel") == "phone"
            and self.outbound is not None
        ):
            verification = await self.outbound.verify(
                option,
                f"核验 {node_id} 的价格、库存和时间是否可履约",
            )
            if verification.status != "confirmed":
                raise ValueError(verification.summary)
            reference.terms.append(f"AI 外呼核验：{verification.summary}")
        await self._save(reference)
        return reference

    async def observe(self, task_id: str, node_id: str) -> list[SupplySignal]:
        reference = await self._load(task_id, node_id)
        if reference is None:
            return []
        option = await self.supply.get(reference.supply_id)
        version = await self.supply.world_version()
        if (
            reference.stage in {SupplyLifecycleStage.QUOTED, SupplyLifecycleStage.HELD}
            and reference.hold_expires_at
            and reference.hold_expires_at <= utc_now()
        ):
            return [SupplySignal(
                supply_id=reference.supply_id,
                kind="hold_expired",
                detail="供给占位已过期",
                world_version=version,
            )]
        if option is None or option.availability == Availability.UNAVAILABLE:
            return [SupplySignal(
                supply_id=reference.supply_id,
                kind="inventory_unavailable",
                detail="供给已不可用",
                world_version=version,
            )]
        if reference.quoted_total_yuan != option.price_yuan:
            return [SupplySignal(
                supply_id=reference.supply_id,
                kind="price_increase",
                detail=f"报价变为 ¥{option.price_yuan}",
                magnitude=option.price_yuan - (reference.quoted_total_yuan or 0),
                world_version=version,
            )]
        return []

    async def execute(self, command: FulfillmentCommand) -> FulfillmentEvent:
        reference = await self._load(command.task_id, command.node_id)
        if reference is None or reference.supply_id != command.option_id:
            return self._failure(command, "没有与当前供给一致的报价占位")
        if (
            reference.stage in {SupplyLifecycleStage.QUOTED, SupplyLifecycleStage.HELD}
            and reference.hold_expires_at
            and reference.hold_expires_at <= utc_now()
        ):
            reference.stage = SupplyLifecycleStage.EXPIRED
            await self._save(reference)
            return self._failure(command, "供给占位已过期，需要刷新报价")

        option = await self.supply.get(reference.supply_id)
        if option is None or option.availability == Availability.UNAVAILABLE:
            return self._failure(command, "提交前刷新发现供给已失效")
        capability = next(
            item for item in self.catalog.capabilities if item.id == reference.capability_id
        )
        is_after_sales = command.related_receipt_id is not None
        is_change = command.action in capability.lifecycle.change_actions
        if is_change:
            if not command.related_receipt_id or reference.commitment_id is None:
                return self._failure(command, "修改动作需要已有承诺回执")
            reference.stage = SupplyLifecycleStage.CHANGED
            reference.updated_at = utc_now()
            await self._save(reference)
            return FulfillmentEvent(
                task_id=command.task_id,
                node_id=command.node_id,
                action=command.action,
                status="succeeded",
                detail="供给变更已受理",
                receipt_id=reference.commitment_id,
                actual_amount_yuan=0,
                lifecycle_stage=reference.stage,
            )
        if is_after_sales:
            allowed = set(capability.lifecycle.compensation_actions.values())
            if command.action not in allowed:
                return self._failure(command, "该供给未发布此售后动作")
        elif command.action not in option.actions:
            return self._failure(command, "该供给未发布此履约动作")

        if (
            not is_after_sales
            and capability.lifecycle.refresh_before_commit
            and reference.world_version != await self.supply.world_version()
            and reference.quoted_total_yuan != option.price_yuan
        ):
            return self._failure(command, "报价在提交前发生变化，需要重新确认")

        event = await self.supply.execute(command)
        if event.status == "succeeded":
            reference.stage = SupplyLifecycleStage.COMMITTED
            reference.commitment_id = event.receipt_id
            if event.receipt_id:
                reference.commitments[command.action] = event.receipt_id
            event.lifecycle_stage = reference.stage
            event.actual_amount_yuan = command.amount_yuan
            event.compensation_action = capability.lifecycle.compensation_actions.get(
                command.action
            )
        elif event.status == "compensated":
            original = next(
                (
                    source
                    for source, compensation in capability.lifecycle.compensation_actions.items()
                    if compensation == command.action
                ),
                None,
            )
            reference.stage = (
                SupplyLifecycleStage.COMMITTED
                if original is not None
                and any(action != original for action in reference.commitments)
                else SupplyLifecycleStage.REFUNDED
                if original in {ActionKind.BUY_COUPON, ActionKind.BUY_TICKET}
                else SupplyLifecycleStage.CANCELLED
            )
            if original is not None:
                reference.commitments.pop(original, None)
            reference.commitment_id = next(
                reversed(reference.commitments.values()),
                None,
            )
            event.lifecycle_stage = reference.stage
            event.actual_amount_yuan = 0
        if event.status != "failed":
            reference.updated_at = utc_now()
            await self._save(reference)
        return event

    async def observe_plan(self, plan: PlanGraph) -> list[SupplySignal]:
        signals: list[SupplySignal] = []
        current_version = await self.supply.world_version()
        for node in plan.nodes:
            reference = node.supply_reference or await self._load("", node.id)
            if reference is None:
                continue
            option = await self.supply.get(reference.supply_id)
            if (
                reference.stage in {SupplyLifecycleStage.QUOTED, SupplyLifecycleStage.HELD}
                and reference.hold_expires_at
                and reference.hold_expires_at <= utc_now()
            ):
                signals.append(SupplySignal(
                    supply_id=reference.supply_id,
                    kind="hold_expired",
                    detail=f"{node.title} 的占位已过期",
                    world_version=current_version,
                ))
            elif option is None or option.availability == Availability.UNAVAILABLE:
                signals.append(SupplySignal(
                    supply_id=reference.supply_id,
                    kind="inventory_unavailable",
                    detail=f"{node.title} 已不可用",
                    world_version=current_version,
                ))
            elif reference.quoted_total_yuan != option.price_yuan:
                signals.append(SupplySignal(
                    supply_id=reference.supply_id,
                    kind="price_increase",
                    detail=f"{node.title} 当前报价为 ¥{option.price_yuan}",
                    magnitude=option.price_yuan - (reference.quoted_total_yuan or 0),
                    world_version=current_version,
                ))
        return signals

    async def _load(self, task_id: str, node_id: str) -> SupplyReference | None:
        if task_id:
            payload = await self.store.load(self.namespace, f"{task_id}:{node_id}")
            return SupplyReference.model_validate(payload) if payload else None
        for payload in await self.store.scan(self.namespace):
            if payload.get("node_id") == node_id:
                return SupplyReference.model_validate(payload)
        return None

    async def _save(self, reference: SupplyReference) -> None:
        await self.store.save(
            self.namespace,
            f"{reference.task_id}:{reference.node_id}",
            reference.model_dump(mode="json"),
        )

    @staticmethod
    def _failure(command: FulfillmentCommand, detail: str) -> FulfillmentEvent:
        return FulfillmentEvent(
            task_id=command.task_id,
            node_id=command.node_id,
            action=command.action,
            status="failed",
            detail=detail,
        )


def reference_token(task_id: str, node_id: str, version: int) -> str:
    return f"{task_id[-6:]}_{node_id}_{version}"
