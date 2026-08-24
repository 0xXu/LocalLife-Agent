from backend.mcp import server
from backend.mcp.server import _route_between, _within_slots, mcp
from backend.mcp import load_capability_catalog


async def test_mcp_normalizes_date_prefixed_clock_values(world) -> None:
    hair = await world.get("service_hair_wangjing")
    science = await world.get("activity_family_science")
    assert hair is not None
    assert science is not None

    assert _within_slots(hair, "明天15:00", "明天16:00")
    assert _within_slots(science, "周六14:00", "周六17:00")


async def test_mobility_tools_ground_the_requested_route(
    world,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "twin", world)
    monkeypatch.setattr(server, "_initialized", True)

    route = _route_between("望京", "国贸")
    assert route is not None
    assert route["walk_supported"] is False

    quote = await server.mobility_quote("望京", "国贸", "21:15", 1)
    assert quote["status"] == "ok"
    assert quote["items"]
    assert all(item["time_slots"] == ["21:15"] for item in quote["items"])
    assert all(
        item["metadata"]["origin"] == "望京"
        and item["metadata"]["destination"] == "国贸"
        and item["metadata"]["on_demand"] is True
        and item["metadata"]["scheduling_window_start"] == "21:15"
        and item["actions"] == ["request_ride"]
        for item in quote["items"]
    )

    navigation = await server.mobility_plan_navigation(
        "望京",
        "国贸",
        "21:15",
        "walk",
    )
    assert navigation["status"] == "no_supply"
    assert navigation["items"] == []

    nearby_navigation = await server.mobility_plan_navigation(
        "国贸",
        "大望路",
        "19:00",
        "walk",
    )
    assert nearby_navigation["status"] == "ok"
    metadata = nearby_navigation["items"][0]["metadata"]
    assert metadata["on_demand"] is False
    assert metadata["scheduling_window_start"] == "19:00"
    assert metadata["scheduling_window_end"] == "22:00"

    venue_navigation = await server.mobility_plan_navigation(
        "宴岚国贸店",
        "英皇电影城",
        "20:00",
        "walk",
    )
    assert venue_navigation["status"] == "ok"
    assert venue_navigation["items"][0]["metadata"]["destination_district"] == "国贸"


async def test_delivery_entry_search_returns_planning_ready_quote_fields(
    world,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "twin", world)
    monkeypatch.setattr(server, "_initialized", True)

    result = await server.delivery_search(
        query="清淡粥",
        destination="望京SOHO 3号楼",
        deliver_by="22:00",
    )

    assert [item["id"] for item in result["items"]] == [
        "delivery_congee_wangjing"
    ]
    assert all(
        item["metadata"]["destination"] == "望京SOHO 3号楼"
        and item["metadata"]["deliver_by"] == "22:00"
        and item["metadata"]["payable_total_yuan"] == item["price_yuan"]
        and item["metadata"]["scheduling_window_start"] == "18:00"
        and item["metadata"]["scheduling_window_end"] == "21:25"
        and item["metadata"]["scheduling_interval_minutes"] == 5
        for item in result["items"]
    )


def test_mcp_exposes_only_confirmed_read_surface() -> None:
    published_tools = {
        tool
        for capability in load_capability_catalog().capabilities
        for tool in capability.tools
    }
    published_tools.update(load_capability_catalog().lifecycle_tools)
    assert published_tools == set(mcp._tool_manager._tools)
    assert set(mcp._resource_manager._resources) == {
        "meituan://taxonomy",
        "meituan://city/beijing/districts",
        "meituan://fulfillment/capabilities",
    }


def test_retrieval_entry_schema_does_not_pre_prune_solver_owned_constraints() -> None:
    for tool_name in ["food.search", "activity.search", "service.search"]:
        properties = mcp._tool_manager._tools[tool_name].parameters["properties"]
        assert {"budget_yuan", "party_size", "earliest", "latest"}.isdisjoint(
            properties
        )
    delivery_properties = mcp._tool_manager._tools["delivery.search"].parameters[
        "properties"
    ]
    assert "budget_yuan" not in delivery_properties
