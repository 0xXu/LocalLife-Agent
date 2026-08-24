from __future__ import annotations

import asyncio
import json
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from backend.config import get_settings
from backend.domain.models import (
    ActionKind,
    Availability,
    FulfillmentCommand,
    SupplyOption,
    Vertical,
    utc_now,
)
from backend.mcp.catalog import load_capability_catalog
from backend.mcp.schemas import ToolEnvelope
from backend.storage import InMemoryDocumentStore, PostgresDocumentStore
from backend.supply import AiOutboundCallAdapter, SupplyLifecycleModule, SupplyTwin, TwinCallTransport

settings = get_settings()
mcp = FastMCP(
    "meituan-supply-mcp",
    instructions="Versioned local-life supply facts and provider-owned fulfillment lifecycle.",
    host=settings.supply_mcp_host,
    port=settings.supply_mcp_port,
    streamable_http_path="/mcp",
    json_response=True,
)
store = (
    InMemoryDocumentStore()
    if settings.use_in_memory_store
    else PostgresDocumentStore(settings.database_url)
)
twin = SupplyTwin(store, settings.supply_catalog_path or None)
outbound = (
    AiOutboundCallAdapter(settings, TwinCallTransport(twin))
    if settings.deepseek_api_key
    else None
)
lifecycle = SupplyLifecycleModule(store, twin, load_capability_catalog(), outbound)
_initialized = False
_init_lock = asyncio.Lock()


def _provider_resources() -> dict[str, Any]:
    path = Path(__file__).with_name("provider_resources.json")
    return json.loads(path.read_text(encoding="utf-8"))


async def _ready() -> SupplyTwin:
    global _initialized
    if not _initialized:
        async with _init_lock:
            if not _initialized:
                await store.initialize()
                await twin.initialize()
                _initialized = True
    return twin


async def _envelope(
    options: list[SupplyOption],
    warnings: list[str] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    observed = utc_now()
    world_version = await twin.world_version()
    result = ToolEnvelope(
        status=status or ("ok" if options else "no_supply"),
        observed_at=observed,
        valid_until=observed + timedelta(minutes=5),
        world_version=world_version,
        items=[item.model_dump(mode="json") for item in options],
        warnings=warnings or [],
    )
    return result.model_dump(mode="json")


def _within_slots(option: SupplyOption, earliest: str | None, latest: str | None) -> bool:
    def clock(value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"(?:[01]\d|2[0-3]):[0-5]\d", value)
        return match.group(0) if match else value

    earliest = clock(earliest)
    latest = clock(latest)
    if not earliest and not latest:
        return True
    return any(
        (not earliest or slot >= earliest) and (not latest or slot <= latest)
        for slot in option.time_slots
    )


def _route_between(
    origin: str,
    destination: str,
    places: list[SupplyOption] | None = None,
) -> dict[str, Any] | None:
    city = _provider_resources()["city"]
    districts = city["districts"]

    def resolve(value: str) -> str | None:
        normalized = value.casefold()
        matches = [district for district in districts if district.casefold() in normalized]
        if matches:
            return max(matches, key=len)
        place_name = re.sub(r"\W+", "", normalized)
        place_districts = {
            option.district
            for option in places or []
            if any(
                place_name in published or published in place_name
                for published in (
                    re.sub(r"\W+", "", option.name.casefold()),
                    re.sub(r"\W+", "", option.venue.casefold()),
                )
            )
        }
        return next(iter(place_districts)) if len(place_districts) == 1 else None

    start = resolve(origin)
    end = resolve(destination)
    if start is None or end is None:
        return None
    frontier = [(start, 0)]
    visited = {start}
    hops = None
    while frontier:
        node, depth = frontier.pop(0)
        if node == end:
            hops = depth
            break
        neighbors = set(city["adjacent"].get(node, []))
        neighbors.update(
            district
            for district, adjacent in city["adjacent"].items()
            if node in adjacent
        )
        for adjacent in neighbors:
            if adjacent not in visited:
                visited.add(adjacent)
                frontier.append((adjacent, depth + 1))
    if hops is None:
        return None
    route_model = city["route_model"]
    return {
        "origin_district": start,
        "destination_district": end,
        "hops": hops,
        "ride_minutes": (
            route_model["same_district_minutes"]
            if hops == 0
            else route_model["ride_minutes_per_hop"] * hops
        ),
        "walk_minutes": (
            route_model["same_district_minutes"]
            if hops == 0
            else route_model["walk_minutes_per_hop"] * hops
        ),
        "distance_km": round(route_model["distance_km_per_hop"] * max(hops, 0.25), 1),
        "walk_supported": hops <= route_model["max_walk_hops"],
        "on_demand_quote_horizon_minutes": route_model[
            "on_demand_quote_horizon_minutes"
        ],
        "departure_interval_minutes": route_model["departure_interval_minutes"],
    }


def _clock_after(value: str, minutes: int) -> str:
    hour, minute = map(int, value.split(":"))
    total = min(hour * 60 + minute + minutes, 23 * 60 + 59)
    return f"{total // 60:02d}:{total % 60:02d}"


def _clock_before(value: str, minutes: int) -> str:
    hour, minute = map(int, value.split(":"))
    total = max(hour * 60 + minute - minutes, 0)
    return f"{total // 60:02d}:{total % 60:02d}"


def _delivery_scheduling_metadata(
    option: SupplyOption,
    deliver_by: str | None,
) -> dict[str, Any]:
    if not option.time_slots:
        return {}
    window_end = max(option.time_slots)
    deadline = re.search(r"(?:[01]\d|2[0-3]):[0-5]\d", deliver_by or "")
    if deadline is not None:
        window_end = min(
            window_end,
            _clock_before(deadline.group(0), option.duration_minutes),
        )
    delivery_model = _provider_resources()["fulfillment"]["delivery"]
    return {
        "scheduling_window_start": min(option.time_slots),
        "scheduling_window_end": window_end,
        "scheduling_interval_minutes": delivery_model[
            "dispatch_interval_minutes"
        ],
    }


@mcp.resource(
    "meituan://taxonomy",
    name="Local-life taxonomy",
    description="Stable vertical and experience-tag vocabulary.",
    mime_type="application/json",
)
def taxonomy() -> str:
    return json.dumps(_provider_resources()["taxonomy"], ensure_ascii=False)


@mcp.resource(
    "meituan://city/beijing/districts",
    name="Beijing twin districts",
    description="District relationships used by the supply twin.",
    mime_type="application/json",
)
def districts() -> str:
    city = _provider_resources()["city"]
    return json.dumps(
        {"city": city["name"], "districts": city["districts"], "adjacent": city["adjacent"]},
        ensure_ascii=False,
    )


@mcp.resource(
    "meituan://fulfillment/capabilities",
    name="Fulfillment capabilities",
    description="Stable mapping from supply verticals to supported commitments.",
    mime_type="application/json",
)
def fulfillment_capabilities() -> str:
    return load_capability_catalog().model_dump_json()


@mcp.tool(name="food.search", structured_output=True)
async def food_search(
    query: str = "",
    district: str = "",
    tags: list[str] | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    """Retrieve planning candidates; budget, time, and capacity stay solver-owned."""
    world = await _ready()
    options = await world.search(
        Vertical.FOOD,
        " ".join([query, *(tags or [])]),
        None,
        limit * 2,
        district=district,
    )
    options = [
        item for item in options
        if item.metadata.get("opening_status", "open") == "open"
    ][:limit]
    warnings = [] if options else ["当前区域没有可用于规划的营业中餐饮供给"]
    return await _envelope(options, warnings)


@mcp.tool(name="food.get_availability", structured_output=True)
async def food_get_availability(
    supply_id: str,
    party_size: int,
    desired_time: str,
) -> dict[str, Any]:
    """Verify one restaurant's table and coupon inventory for a requested time."""
    world = await _ready()
    option = await world.get(supply_id)
    if option is None or option.vertical != Vertical.FOOD:
        return await _envelope([], status="no_supply")
    warnings: list[str] = []
    capacity = int(option.metadata.get("party_capacity", 0))
    if option.metadata.get("opening_status") != "open":
        warnings.append("商户当前不在营业状态")
    if desired_time not in option.time_slots:
        warnings.append("指定时间无桌位，可选择返回的相邻时段")
    if party_size > capacity:
        warnings.append(f"当前桌型最多容纳 {capacity} 人")
    queue_minutes = int(option.metadata.get("queue_minutes", 0))
    if queue_minutes:
        warnings.append(f"当前预计排队 {queue_minutes} 分钟")
    return await _envelope([option], warnings, "ok" if not warnings else "partial")


@mcp.tool(name="offline.call_verify", structured_output=True)
async def offline_call_verify(supply_id: str, request: str) -> dict[str, Any]:
    """Use the AI outbound-call adapter to verify merchant-only offline facts."""
    world = await _ready()
    option = await world.get(supply_id)
    if option is None:
        return await _envelope([], status="no_supply")
    if option.metadata.get("booking_channel") != "phone":
        return await _envelope([option], ["该供给无需电话核验"], "partial")
    if outbound is None:
        return await _envelope([option], ["AI 外呼 adapter 未配置"], "partial")
    result = await outbound.verify(option, request)
    observed = utc_now()
    return ToolEnvelope(
        status="ok" if result.status == "confirmed" else "partial",
        observed_at=observed,
        valid_until=observed + timedelta(minutes=5),
        world_version=await twin.world_version(),
        items=[result.model_dump(mode="json")],
        warnings=[] if result.status == "confirmed" else [result.summary],
    ).model_dump(mode="json")


@mcp.tool(name="activity.search", structured_output=True)
async def activity_search(
    query: str = "",
    district: str = "",
    tags: list[str] | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    """Retrieve session candidates; budget, time, and capacity stay solver-owned."""
    world = await _ready()
    options = await world.search(
        Vertical.ACTIVITY,
        " ".join([query, *(tags or [])]),
        None,
        limit * 2,
        district=district,
    )
    options = options[:limit]
    return await _envelope(options)


@mcp.tool(name="activity.get_sessions", structured_output=True)
async def activity_get_sessions(
    supply_id: str,
    party_size: int,
    earliest: str | None = None,
    latest: str | None = None,
) -> dict[str, Any]:
    """Verify one activity's sessions, seats, and price."""
    world = await _ready()
    option = await world.get(supply_id)
    if option is None or option.vertical != Vertical.ACTIVITY:
        return await _envelope([], status="no_supply")
    if not _within_slots(option, earliest, latest):
        return await _envelope([option], ["要求的时间窗内没有可售场次"], status="partial")
    remaining = int(option.metadata.get("remaining", 99))
    warnings = [] if remaining >= party_size else ["连座库存不足"]
    return await _envelope([option], warnings, "ok" if not warnings else "partial")


@mcp.tool(name="service.search", structured_output=True)
async def service_search(
    query: str = "",
    district: str = "",
    tags: list[str] | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    """Retrieve appointment candidates; budget, time, and capacity stay solver-owned."""
    world = await _ready()
    options = await world.search(
        Vertical.SERVICE,
        " ".join([query, *(tags or [])]),
        None,
        limit * 2,
        district=district,
    )
    options = options[:limit]
    return await _envelope(options)


@mcp.tool(name="service.get_slots", structured_output=True)
async def service_get_slots(
    supply_id: str,
    party_size: int = 1,
    earliest: str | None = None,
    latest: str | None = None,
) -> dict[str, Any]:
    """Verify one local service's appointment slots, recipient fit, capacity, and price."""
    world = await _ready()
    option = await world.get(supply_id)
    if option is None or option.vertical != Vertical.SERVICE:
        return await _envelope([], status="no_supply")
    warnings: list[str] = []
    if not _within_slots(option, earliest, latest):
        warnings.append("要求的时间窗内没有可预约时段")
    if int(option.metadata.get("remaining", 99)) < party_size:
        warnings.append("可同时预约的名额不足")
    return await _envelope([option], warnings, "partial" if warnings else "ok")


@mcp.tool(name="delivery.search", structured_output=True)
async def delivery_search(
    query: str = "",
    destination: str = "",
    district: str = "",
    deliver_by: str | None = None,
    tags: list[str] | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    """Retrieve delivery candidates; budget and arrival feasibility stay solver-owned."""
    world = await _ready()
    options = await world.search(
        Vertical.DELIVERY,
        " ".join([query, *(tags or [])]),
        None,
        limit * 2,
        district=district,
    )
    options = options[:limit]
    quoted_options: list[SupplyOption] = []
    for option in options:
        quoted = option.model_copy(deep=True)
        quoted.metadata.update({
            "destination": destination,
            "deliver_by": deliver_by,
            "payable_total_yuan": quoted.price_yuan,
            **_delivery_scheduling_metadata(quoted, deliver_by),
        })
        quoted_options.append(quoted)
    return await _envelope(quoted_options)


@mcp.tool(name="delivery.get_quote", structured_output=True)
async def delivery_get_quote(
    supply_id: str,
    destination: str,
    deliver_by: str | None = None,
) -> dict[str, Any]:
    """Verify delivery ETA, fee, and all-in payable price for one destination."""
    world = await _ready()
    option = await world.get(supply_id)
    if option is None or option.vertical != Vertical.DELIVERY:
        return await _envelope([], status="no_supply")
    quoted = option.model_copy(deep=True)
    quoted.metadata["destination"] = destination
    quoted.metadata["deliver_by"] = deliver_by
    quoted.metadata["payable_total_yuan"] = quoted.price_yuan
    quoted.metadata.update(_delivery_scheduling_metadata(quoted, deliver_by))
    warnings = [] if _within_slots(quoted, None, deliver_by) else ["无法在要求时间前送达"]
    return await _envelope([quoted], warnings, "partial" if warnings else "ok")


@mcp.tool(name="mobility.quote", structured_output=True)
async def mobility_quote(
    origin: str,
    destination: str,
    depart_at: str,
    party_size: int = 2,
) -> dict[str, Any]:
    """Return current ride quotes and estimated pickup time."""
    world = await _ready()
    route = _route_between(origin, destination, await world.list_options())
    departure = re.search(r"(?:[01]\d|2[0-3]):[0-5]\d", depart_at)
    if route is None or departure is None:
        return await _envelope(
            [],
            ["供给侧无法解析这条路线或出发时间"],
            "invalid_query",
        )
    options = [
        item
        for item in await world.search(Vertical.MOBILITY)
        if ActionKind.REQUEST_RIDE in item.actions
    ]
    quoted_options = []
    for option in options:
        quoted = option.model_copy(deep=True)
        quoted.duration_minutes = route["ride_minutes"] + int(
            quoted.metadata.get("route_delay_minutes", 0)
        )
        quoted.time_slots = [departure.group(0)]
        quoted.venue = f"{origin} → {destination}"
        service_level = str(quoted.metadata.get("service_level", quoted.name))
        quoted.name = f"{service_level} · {origin}到{destination}"
        quoted.metadata.update({
            "origin": origin,
            "destination": destination,
            "depart_at": departure.group(0),
            "on_demand": True,
            "scheduling_window_start": departure.group(0),
            "scheduling_window_end": _clock_after(
                departure.group(0),
                route["on_demand_quote_horizon_minutes"],
            ),
            "scheduling_interval_minutes": route["departure_interval_minutes"],
            **route,
        })
        quoted_options.append(quoted)
    warnings = [] if party_size <= 4 else ["需要六座车型，当前报价仅供参考"]
    return await _envelope(quoted_options, warnings)


@mcp.tool(name="mobility.estimate_route", structured_output=True)
async def mobility_estimate_route(
    stops: list[str],
    depart_at: str,
) -> dict[str, Any]:
    """Estimate deterministic travel segments between ordered stops."""
    world = await _ready()
    places = await world.list_options()
    if len(stops) < 2:
        observed = utc_now()
        return ToolEnvelope(
            status="invalid_query",
            observed_at=observed,
            valid_until=observed + timedelta(minutes=5),
            world_version=await twin.world_version(),
            warnings=["至少需要两个地点"],
        ).model_dump(mode="json")
    segments = []
    for start, end in zip(stops, stops[1:]):
        route = _route_between(start, end, places)
        if route is None:
            observed = utc_now()
            return ToolEnvelope(
                status="no_supply",
                observed_at=observed,
                valid_until=observed + timedelta(minutes=5),
                world_version=await twin.world_version(),
                warnings=[f"供给侧无法解析 {start} 到 {end} 的路线"],
            ).model_dump(mode="json")
        segments.append({
            "from": start,
            "to": end,
            "duration_minutes": route["ride_minutes"],
            "distance_km": route["distance_km"],
            "origin_district": route["origin_district"],
            "destination_district": route["destination_district"],
        })
    observed = utc_now()
    return ToolEnvelope(
        status="ok",
        observed_at=observed,
        valid_until=observed + timedelta(minutes=5),
        world_version=await twin.world_version(),
        items=[{"depart_at": depart_at, "segments": segments}],
    ).model_dump(mode="json")


@mcp.tool(name="mobility.plan_navigation", structured_output=True)
async def mobility_plan_navigation(
    origin: str,
    destination: str,
    depart_at: str,
    mode: str = "walk",
) -> dict[str, Any]:
    """Return navigation evidence; unresolved venues must use their published district."""
    world = await _ready()
    route = _route_between(origin, destination, await world.list_options())
    departure = re.search(r"(?:[01]\d|2[0-3]):[0-5]\d", depart_at)
    if route is None or departure is None:
        return await _envelope([], ["供给侧无法解析这条导航路线"], "invalid_query")
    if mode == "walk" and not route["walk_supported"]:
        return await _envelope(
            [],
            ["这条路线超出步行导航的合理范围，请改用出行报价"],
            "no_supply",
        )
    option = await world.get("mobility_navigation")
    if option is None:
        return await _envelope([], status="no_supply")
    planned = option.model_copy(deep=True)
    planned.duration_minutes = (
        route["walk_minutes"] if mode == "walk" else route["ride_minutes"]
    )
    planned.time_slots = [departure.group(0)]
    planned.venue = f"{origin} → {destination}"
    planned.name = f"{origin}到{destination}导航"
    planned.metadata.update({
        "origin": origin,
        "destination": destination,
        "depart_at": departure.group(0),
        "on_demand": False,
        "scheduling_window_start": departure.group(0),
        "scheduling_window_end": _clock_after(
            departure.group(0),
            route["on_demand_quote_horizon_minutes"],
        ),
        "scheduling_interval_minutes": route["departure_interval_minutes"],
        "route_mode": mode,
        "distance_km": route["distance_km"],
        "eta_minutes": planned.duration_minutes,
        **route,
    })
    return await _envelope([planned])


@mcp.tool(name="supply.get", structured_output=True)
async def supply_get(supply_id: str) -> dict[str, Any]:
    """Read one supply item by its stable ID."""
    world = await _ready()
    option = await world.get(supply_id)
    return await _envelope([option] if option else [], status="ok" if option else "no_supply")


@mcp.tool(name="supply.refresh", structured_output=True)
async def supply_refresh(supply_ids: list[str]) -> dict[str, Any]:
    """Refresh final candidates before a plan is proposed."""
    world = await _ready()
    options = [item for item in [await world.get(key) for key in supply_ids] if item]
    warnings = [
        f"{item.name} 已不可用"
        for item in options
        if item.availability == Availability.UNAVAILABLE
    ]
    status = "ok" if len(options) == len(supply_ids) and not warnings else "partial"
    return await _envelope(options, warnings, status)


@mcp.tool(name="supply.quote_and_hold", structured_output=True)
async def supply_quote_and_hold(
    task_id: str,
    node_id: str,
    capability_id: str,
    supply_id: str,
) -> dict[str, Any]:
    """Create a versioned quote and temporary inventory hold for one stable supply ID."""
    await _ready()
    reference = await lifecycle.quote_and_hold(
        task_id=task_id,
        node_id=node_id,
        capability_id=capability_id,
        supply_id=supply_id,
    )
    observed = utc_now()
    return ToolEnvelope(
        status="ok",
        observed_at=observed,
        valid_until=reference.hold_expires_at or observed,
        world_version=reference.world_version,
        items=[reference.model_dump(mode="json")],
    ).model_dump(mode="json")


@mcp.tool(name="supply.observe", structured_output=True)
async def supply_observe(task_id: str, node_id: str) -> dict[str, Any]:
    """Observe lifecycle drift for a previously held or committed supply reference."""
    await _ready()
    signals = await lifecycle.observe(task_id, node_id)
    observed = utc_now()
    return ToolEnvelope(
        status="partial" if signals else "ok",
        observed_at=observed,
        valid_until=observed + timedelta(minutes=1),
        world_version=await twin.world_version(),
        items=[item.model_dump(mode="json") for item in signals],
    ).model_dump(mode="json")


@mcp.tool(name="supply.commit", structured_output=True)
async def supply_commit(command: dict[str, Any]) -> dict[str, Any]:
    """Commit, change, cancel, or refund a held supply through its published lifecycle."""
    await _ready()
    event = await lifecycle.execute(FulfillmentCommand.model_validate(command))
    observed = utc_now()
    return ToolEnvelope(
        status="ok" if event.status != "failed" else "partial",
        observed_at=observed,
        valid_until=observed + timedelta(minutes=5),
        world_version=await twin.world_version(),
        items=[event.model_dump(mode="json")],
        warnings=[event.detail] if event.status == "failed" else [],
    ).model_dump(mode="json")


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
