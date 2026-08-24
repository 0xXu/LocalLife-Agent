import pytest

from backend.domain.models import ActionKind, FulfillmentCommand, Vertical
from backend.storage import InMemoryDocumentStore
from backend.supply import SupplyTwin


async def test_initialize_adds_new_seed_domains_without_overwriting_live_state() -> None:
    store = InMemoryDocumentStore()
    await store.initialize()
    original = SupplyTwin(store)
    await original.initialize()
    await original.inject("dinner_full")

    legacy_store = InMemoryDocumentStore()
    await legacy_store.initialize()
    omitted = {"service_massage_wangjing", "delivery_congee_wangjing"}
    for payload in await store.scan(original.namespace):
        if payload["id"] not in omitted:
            await legacy_store.save(original.namespace, payload["id"], payload)

    restarted = SupplyTwin(legacy_store)
    await restarted.initialize()

    dinner = await restarted.get("food_yanlan")
    assert dinner is not None
    assert dinner.availability.value == "unavailable"
    assert await restarted.get("service_massage_wangjing") is not None
    assert await restarted.get("delivery_congee_wangjing") is not None


async def test_search_and_scenario_are_versioned(world: SupplyTwin) -> None:
    initial_version = await world.world_version()
    options = await world.search("food", query="安静", max_price_yuan=200)
    assert options[0].id == "food_yanlan"
    assert "food_courtyard_phone" in {item.id for item in options}

    changed = await world.inject("dinner_full")
    assert changed is not None
    assert changed.availability.value == "unavailable"
    assert await world.world_version() == initial_version + 1
    assert not any(item.id == "food_yanlan" for item in await world.search("food"))


async def test_priority_domains_publish_fulfillment_grade_facts(world: SupplyTwin) -> None:
    dining = await world.get("food_yanlan")
    experience = await world.get("activity_comedy")
    mobility = await world.get("mobility_home")
    assert dining is not None and experience is not None and mobility is not None

    assert {
        "party_capacity",
        "queue_minutes",
        "opening_status",
        "coupon_terms",
        "reservation_grace_minutes",
    }.issubset(dining.metadata)
    assert {
        "ticket_type",
        "admission_rule",
        "refund_rule",
        "change_rule",
    }.issubset(experience.metadata)
    assert {
        "eta_minutes",
        "distance_km",
        "walking_minutes",
        "fare_detail",
        "supports_multi_stop",
    }.issubset(mobility.metadata)


async def test_fulfillment_is_idempotent_and_ride_failure_is_consumed(world: SupplyTwin) -> None:
    command = FulfillmentCommand(
        id="fixed-command",
        task_id="task-1",
        node_id="dinner",
        action=ActionKind.RESERVE_TABLE,
        option_id="food_yanlan",
        amount_yuan=0,
    )
    first = await world.execute(command)
    second = await world.execute(command)
    assert first.status == "succeeded"
    assert second.receipt_id == first.receipt_id

    await world.inject("ride_cancelled")
    ride = FulfillmentCommand(
        task_id="task-1",
        node_id="home",
        action=ActionKind.REQUEST_RIDE,
        option_id="mobility_home",
        amount_yuan=42,
    )
    failed = await world.execute(ride)
    retried = await world.execute(ride.model_copy(update={"id": "retry-command"}))
    assert failed.status == "failed"
    assert retried.status == "succeeded"


async def test_local_service_supply_can_be_discovered_and_booked(world: SupplyTwin) -> None:
    options = await world.search(
        Vertical.SERVICE,
        query="望京 按摩 放松",
        max_price_yuan=300,
    )
    assert options[0].id == "service_massage_wangjing"

    command = FulfillmentCommand(
        task_id="task-service",
        node_id="massage",
        action=ActionKind.BOOK_SERVICE,
        option_id="service_massage_wangjing",
        amount_yuan=268,
    )
    event = await world.execute(command)
    assert event.status == "succeeded"
    assert event.action == ActionKind.BOOK_SERVICE
    assert "预约成功" in event.detail


async def test_delivery_supply_can_quote_and_place_an_order(world: SupplyTwin) -> None:
    options = await world.search(
        Vertical.DELIVERY,
        query="望京 感冒药 送到家",
        max_price_yuan=100,
    )
    assert options[0].id == "delivery_pharmacy_wangjing"
    assert options[0].metadata["delivery_minutes"] == 32
    assert options[0].price_yuan == 64
    assert options[0].metadata["goods_price_yuan"] == 58
    assert options[0].metadata["delivery_fee_yuan"] == 6

    command = FulfillmentCommand(
        task_id="task-delivery",
        node_id="medicine",
        action=ActionKind.PLACE_ORDER,
        option_id="delivery_pharmacy_wangjing",
        amount_yuan=58,
    )
    event = await world.execute(command)
    assert event.status == "succeeded"
    assert "下单成功" in event.detail


async def test_search_understands_compound_chinese_goal_terms(
    world: SupplyTwin,
) -> None:
    options = await world.search(Vertical.DELIVERY, query="清淡粥")

    assert [option.id for option in options] == ["delivery_congee_wangjing"]


async def test_search_ranks_within_the_requested_district(
    world: SupplyTwin,
) -> None:
    options = await world.search(
        Vertical.ACTIVITY,
        query="晚间活动 夜间 单人",
        district="国贸",
    )

    assert {option.id for option in options} == {
        "activity_comedy",
        "activity_cinema",
    }


async def test_navigation_is_a_free_fulfillment_action(world: SupplyTwin) -> None:
    options = await world.search(Vertical.MOBILITY, query="步行 导航 国贸")
    navigation = next(item for item in options if item.id == "mobility_navigation")
    assert navigation.price_yuan == 0

    command = FulfillmentCommand(
        task_id="task-navigation",
        node_id="walk",
        action=ActionKind.START_NAVIGATION,
        option_id=navigation.id,
        amount_yuan=0,
    )
    event = await world.execute(command)
    assert event.status == "succeeded"
    assert "导航已生成" in event.detail


async def test_family_activity_price_is_an_explicit_two_person_total(world: SupplyTwin) -> None:
    option = await world.get("activity_family_science")
    assert option is not None
    assert option.price_yuan == 168
    assert option.metadata["ticket_count"] == 2
    assert option.metadata["price_basis"] == "all_in_party_total"


@pytest.mark.parametrize(
    ("vertical", "query", "expected_id"),
    [
        (Vertical.FOOD, "望京 日料 安静", "food_sushi_wangjing"),
        (Vertical.FOOD, "国贸 火锅 聚会", "food_hotpot_guomao"),
        (Vertical.ACTIVITY, "亲子 室内 周末", "activity_family_science"),
        (Vertical.ACTIVITY, "展览 安静 一个人", "activity_art_exhibition"),
        (Vertical.SERVICE, "望京 理发 剪发", "service_hair_wangjing"),
        (Vertical.SERVICE, "国贸 美甲 两个人", "service_nails_guomao"),
        (Vertical.SERVICE, "常营 洗浴 汗蒸 放松", "service_bath_spa_changying"),
        (Vertical.SERVICE, "望京 宠物 洗护", "service_pet_grooming_wangjing"),
        (Vertical.DELIVERY, "望京 外卖 粥", "delivery_congee_wangjing"),
        (Vertical.DELIVERY, "国贸 鲜花 约会", "delivery_flowers_guomao"),
        (Vertical.DELIVERY, "望京 生日蛋糕", "delivery_cake_wangjing"),
        (Vertical.DELIVERY, "国贸 买菜 日用品", "delivery_grocery_guomao"),
        (Vertical.DELIVERY, "望京 宠物 猫砂 闪送", "delivery_pet_supplies_wangjing"),
    ],
)
async def test_catalog_covers_representative_local_life_goals(
    world: SupplyTwin,
    vertical: Vertical,
    query: str,
    expected_id: str,
) -> None:
    options = await world.search(vertical, query=query)
    assert options[0].id == expected_id


@pytest.mark.parametrize(
    ("option_id", "source_action", "compensation_action"),
    [
        ("service_massage_wangjing", ActionKind.BOOK_SERVICE, ActionKind.CANCEL_SERVICE),
        ("delivery_congee_wangjing", ActionKind.PLACE_ORDER, ActionKind.CANCEL_ORDER),
    ],
)
async def test_extended_commitments_can_be_compensated(
    world: SupplyTwin,
    option_id: str,
    source_action: ActionKind,
    compensation_action: ActionKind,
) -> None:
    source = await world.execute(FulfillmentCommand(
        id=f"source-{option_id}",
        task_id="task-compensation",
        node_id=option_id,
        action=source_action,
        option_id=option_id,
        amount_yuan=100,
    ))
    compensation = await world.execute(FulfillmentCommand(
        id=f"compensation-{option_id}",
        task_id="task-compensation",
        node_id=option_id,
        action=compensation_action,
        option_id=option_id,
        amount_yuan=0,
        related_receipt_id=source.receipt_id,
    ))
    assert compensation.status == "compensated"
