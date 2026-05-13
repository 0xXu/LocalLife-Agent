from backend.actions.policy import build_executable_actions


def _constraints(required_actions: list[str]) -> dict:
    return {
        "people": {"adults": 2, "children": [{"age": 7}]},
        "required_actions": required_actions,
    }


def test_policy_does_not_create_activity_reservation_without_booking_intent(monkeypatch):
    monkeypatch.setattr("backend.actions.policy.new_action_id", lambda: "act_1")
    plan = {
        "itinerary": [
            {"type": "activity", "title": "陶艺体验", "place_id": "poi_activity", "start": "14:00", "end": "15:30"},
        ]
    }
    candidate_lookup = {"poi_activity": {"id": "poi_activity", "name": "陶艺体验", "booking_supported": True}}

    actions = build_executable_actions("rev_1", plan, candidate_lookup, _constraints(["send_plan_message"]))

    assert actions == []


def test_policy_creates_restaurant_actions_only_when_requested_and_grounded(monkeypatch):
    action_ids = iter(["act_reserve", "act_coupon", "act_order"])
    monkeypatch.setattr("backend.actions.policy.new_action_id", lambda: next(action_ids))
    plan = {
        "itinerary": [
            {"type": "activity", "title": "陶艺体验", "place_id": "poi_activity", "start": "14:00", "end": "15:30"},
            {"type": "restaurant", "title": "绿荫轻食餐厅", "place_id": "poi_restaurant", "start": "16:00", "end": "17:00"},
        ]
    }
    candidate_lookup = {
        "poi_activity": {"id": "poi_activity", "name": "陶艺体验", "booking_supported": True},
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "绿荫轻食餐厅",
            "booking_supported": True,
            "coupon": {"id": "deal_1", "title": "双人套餐"},
            "menu": [{"id": "menu_1", "name": "低脂鸡胸沙拉"}],
        },
    }

    actions = build_executable_actions(
        "rev_1",
        plan,
        candidate_lookup,
        _constraints(["restaurant_reservation", "claim_coupon", "create_order"]),
    )

    assert [action["tool"] for action in actions] == ["create_reservation", "claim_coupon", "create_order"]
    assert actions == [
        {
            "action_id": "act_reserve",
            "revision_id": "rev_1",
            "tool": "create_reservation",
            "label": "预订餐厅",
            "target": "绿荫轻食餐厅",
            "status": "pending",
            "idempotency_key": "rev_1:act_reserve",
            "requires_confirmation": True,
            "payload": {"place_id": "poi_restaurant", "time": "16:00", "people": 3},
            "receipt_id": "",
        },
        {
            "action_id": "act_coupon",
            "revision_id": "rev_1",
            "tool": "claim_coupon",
            "label": "领取团购券",
            "target": "绿荫轻食餐厅",
            "status": "pending",
            "idempotency_key": "rev_1:act_coupon",
            "requires_confirmation": True,
            "payload": {"deal_id": "deal_1"},
            "receipt_id": "",
        },
        {
            "action_id": "act_order",
            "revision_id": "rev_1",
            "tool": "create_order",
            "label": "创建点单",
            "target": "绿荫轻食餐厅",
            "status": "pending",
            "idempotency_key": "rev_1:act_order",
            "requires_confirmation": True,
            "payload": {
                "shop_id": "poi_restaurant",
                "menu": [{"id": "menu_1", "name": "低脂鸡胸沙拉"}],
                "time": "16:00",
            },
            "receipt_id": "",
        },
    ]


def test_policy_omits_requested_restaurant_actions_when_candidate_data_is_ungrounded(monkeypatch):
    monkeypatch.setattr("backend.actions.policy.new_action_id", lambda: "act_should_not_be_used")
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "无预约餐厅", "place_id": "poi_restaurant", "start": "16:00", "end": "17:00"},
        ]
    }
    candidate_lookup = {
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "无预约餐厅",
            "booking_supported": False,
            "coupon": True,
            "menu": True,
        }
    }

    actions = build_executable_actions(
        "rev_1",
        plan,
        candidate_lookup,
        _constraints(["restaurant_reservation", "claim_coupon", "create_order"]),
    )

    assert actions == []
