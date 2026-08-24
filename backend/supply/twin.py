from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from backend.domain.models import (
    ActionKind,
    Availability,
    FulfillmentCommand,
    FulfillmentEvent,
    SupplyOption,
)
from backend.storage import DocumentStore


def _catalog_options(catalog_path: Path) -> list[SupplyOption]:
    path = catalog_path
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [SupplyOption.model_validate(row) for row in rows]


class SupplyTwin:
    """Stateful local-life world behind one search/act interface."""

    namespace = "supply"
    meta_namespace = "supply_meta"
    result_namespace = "fulfillment_results"

    def __init__(self, store: DocumentStore, catalog_path: str | Path | None = None) -> None:
        self.store = store
        self.catalog_path = (
            Path(catalog_path)
            if catalog_path
            else Path(__file__).with_name("local_catalog.json")
        )

    async def initialize(self) -> None:
        existing = await self.store.scan(self.namespace)
        if not existing:
            await self.reset()
            return

        existing_ids = {item["id"] for item in existing}
        missing = [
            option for option in _catalog_options(self.catalog_path)
            if option.id not in existing_ids
        ]
        for option in missing:
            await self.store.save(self.namespace, option.id, option.model_dump(mode="json"))
        if missing:
            await self._bump_world()

    async def reset(self) -> None:
        current = await self.world_version()
        for option in _catalog_options(self.catalog_path):
            await self.store.save(self.namespace, option.id, option.model_dump(mode="json"))
        await self.store.save(self.meta_namespace, "world", {"version": current + 1})

    async def world_version(self) -> int:
        payload = await self.store.load(self.meta_namespace, "world")
        return int(payload["version"]) if payload else 0

    async def _bump_world(self) -> int:
        version = await self.world_version() + 1
        await self.store.save(self.meta_namespace, "world", {"version": version})
        return version

    async def list_options(self) -> list[SupplyOption]:
        return [SupplyOption.model_validate(item) for item in await self.store.scan(self.namespace)]

    async def get(self, option_id: str) -> SupplyOption | None:
        payload = await self.store.load(self.namespace, option_id)
        return SupplyOption.model_validate(payload) if payload else None

    async def search(
        self,
        vertical: Vertical,
        query: str = "",
        max_price_yuan: int | None = None,
        limit: int = 6,
        *,
        district: str = "",
    ) -> list[SupplyOption]:
        tokens = [token.strip().lower() for token in query.replace("，", " ").split() if token.strip()]
        options = [
            option
            for option in await self.list_options()
            if option.vertical == vertical
            and option.availability != Availability.UNAVAILABLE
            and (not district or option.district == district)
            and (max_price_yuan is None or option.price_yuan <= max_price_yuan)
        ]
        relevance: dict[str, int] = {}
        if tokens:
            for option in options:
                fields = [
                    (option.name.lower(), 4),
                    (option.district.lower(), 3),
                    (option.venue.lower(), 2),
                    *((tag.lower(), 2) for tag in option.tags),
                ]
                relevance[option.id] = sum(
                    max(
                        (
                            weight
                            for value, weight in fields
                            if token in value or value in token
                        ),
                        default=0,
                    )
                    for token in tokens
                )
            matched = [option for option in options if relevance[option.id] > 0]
            if matched:
                options = matched
        options.sort(key=lambda item: (
            -relevance.get(item.id, 0),
            item.availability != Availability.AVAILABLE,
            -item.rating,
            item.price_yuan,
        ))
        return options[:limit]

    async def inject(self, scenario: str) -> SupplyOption | None:
        if scenario == "reset":
            await self.reset()
            return None
        mapping = {
            "dinner_full": "food_yanlan",
            "show_sold_out": "activity_comedy",
            "ride_cancelled": "mobility_home",
            "price_jump": "activity_cinema",
        }
        option_id = mapping.get(scenario)
        if option_id is None:
            raise ValueError(f"unknown scenario: {scenario}")
        option = await self.get(option_id)
        if option is None:
            raise ValueError(f"unknown supply option: {option_id}")
        option = option.model_copy(deep=True)
        option.evidence.inventory_version += 1
        if scenario in {"dinner_full", "show_sold_out"}:
            option.availability = Availability.UNAVAILABLE
            option.evidence.detail = "环境事件：库存刚刚售罄"
        elif scenario == "ride_cancelled":
            option.metadata["fail_next"] = True
            option.evidence.detail = "环境事件：下一位司机可能取消"
        else:
            option.price_yuan += 60
            option.evidence.detail = "环境事件：供给价格上涨 ¥60"
        await self.store.save(self.namespace, option.id, option.model_dump(mode="json"))
        await self._bump_world()
        return option

    async def execute(self, command: FulfillmentCommand) -> FulfillmentEvent:
        previous = await self.store.load(self.result_namespace, command.id)
        if previous:
            return FulfillmentEvent.model_validate(previous)

        async def finish(event: FulfillmentEvent) -> FulfillmentEvent:
            await self.store.save(
                self.result_namespace,
                command.id,
                event.model_dump(mode="json"),
            )
            return event

        option = await self.get(command.option_id)
        if option is None or option.availability == Availability.UNAVAILABLE:
            return await finish(FulfillmentEvent(
                task_id=command.task_id,
                node_id=command.node_id,
                action=command.action,
                status="failed",
                detail="供给已失效，需要重新规划",
            ))
        if command.related_receipt_id:
            return await finish(FulfillmentEvent(
                task_id=command.task_id,
                node_id=command.node_id,
                action=command.action,
                status="compensated",
                detail=f"{option.venue} · 售后动作已受理",
                receipt_id=command.related_receipt_id,
            ))
        if command.action not in option.actions:
            return await finish(FulfillmentEvent(
                task_id=command.task_id,
                node_id=command.node_id,
                action=command.action,
                status="failed",
                detail="当前供给不支持该履约动作",
            ))
        if option.metadata.get("fail_next"):
            changed = option.model_copy(deep=True)
            changed.metadata["fail_next"] = False
            changed.evidence.inventory_version += 1
            changed.evidence.detail = "司机取消，本次叫车未完成"
            await self.store.save(self.namespace, changed.id, changed.model_dump(mode="json"))
            return await finish(FulfillmentEvent(
                task_id=command.task_id,
                node_id=command.node_id,
                action=command.action,
                status="failed",
                detail="司机取消，需重新叫车或调整返程",
            ))
        labels = {
            ActionKind.RESERVE_TABLE: "订座成功",
            ActionKind.BUY_COUPON: "优惠券购买成功",
            ActionKind.BUY_TICKET: "连座票购买成功",
            ActionKind.REQUEST_RIDE: "司机已接单",
            ActionKind.BOOK_SERVICE: "到店服务预约成功",
            ActionKind.PLACE_ORDER: "配送订单下单成功",
            ActionKind.START_NAVIGATION: "导航已生成",
        }
        venue = str(command.commitment_context.get("venue", option.venue))
        label = labels[command.action]
        starts_at = command.commitment_context.get("starts_at")
        if command.action == ActionKind.REQUEST_RIDE and isinstance(starts_at, str):
            label = f"已预约 {starts_at} 出发"
        return await finish(FulfillmentEvent(
            task_id=command.task_id,
            node_id=command.node_id,
            action=command.action,
            status="succeeded",
            detail=f"{venue} · {label}",
            receipt_id=f"LL-{uuid4().hex[:10].upper()}",
        ))
