from backend.actions.policy import build_executable_actions


def _constraints(required_actions: list[str], user_id: str | None = None) -> dict:
    constraints = {
        "people": {"adults": 2, "children": [{"age": 7}]},
        "required_actions": required_actions,
    }
    if user_id is not None:
        constraints["user_id"] = user_id
    return constraints


def _without_ids(actions: list[dict]) -> list[dict]:
    return [{key: value for key, value in action.items() if key not in {"action_id", "idempotency_key"}} for action in actions]


def _assert_deterministic(revision_id: str, plan: dict, candidate_lookup: dict, constraints: dict) -> list[dict]:
    first = build_executable_actions(revision_id, plan, candidate_lookup, constraints)
    second = build_executable_actions(revision_id, plan, candidate_lookup, constraints)
    assert first == second
    for action in first:
        assert action["action_id"].startswith("act_")
        assert action["idempotency_key"].startswith(f"{revision_id}:")
    return first


def test_policy_creates_global_message_action_without_place_bound_grounding():
    plan = {
        "title": "陶艺下午",
        "summary": "按时间和预算生成短计划。",
        "itinerary": [
            {"type": "activity", "title": "陶艺体验", "place_id": "poi_activity", "start": "14:00", "end": "15:30"},
        ]
    }
    candidate_lookup = {"poi_activity": {"id": "poi_activity", "name": "陶艺体验", "booking_supported": True}}

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, _constraints(["send_plan_message"]))

    assert _without_ids(actions) == [
        {
            "revision_id": "rev_1",
            "tool": "send_plan_message",
            "label": "发送计划",
            "target": "同行人",
            "status": "pending",
            "requires_confirmation": True,
            "payload": {
                "recipient": "同行人",
                "message": "陶艺下午\n按时间和预算生成短计划。",
                "plan_title": "陶艺下午",
            },
            "receipt_id": "",
        }
    ]


def test_policy_creates_global_calendar_action_without_place_bound_grounding():
    plan = {
        "title": "陶艺下午",
        "itinerary": [
            {"type": "activity", "title": "陶艺体验", "place_id": "poi_activity", "start": "14:00", "end": "15:30"},
        ]
    }
    candidate_lookup = {"poi_activity": {"id": "poi_activity", "name": "陶艺体验", "booking_supported": True}}

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, _constraints(["create_calendar_event"]))

    assert _without_ids(actions) == [
        {
            "revision_id": "rev_1",
            "tool": "create_calendar_event",
            "label": "创建日历",
            "target": "本地日历",
            "status": "pending",
            "requires_confirmation": True,
            "payload": {
                "itinerary": [
                    {"title": "陶艺体验", "start": "14:00", "end": "15:30", "type": "activity", "place_id": "poi_activity"}
                ],
                "participants": 3,
                "title": "陶艺下午",
            },
            "receipt_id": "",
        }
    ]


def test_policy_creates_activity_reservation_with_party_size_payload():
    plan = {
        "itinerary": [
            {"type": "activity", "title": "陶艺体验", "place_id": "poi_activity", "start": "14:00", "end": "15:30"},
        ]
    }
    candidate_lookup = {
        "poi_activity": {
            "id": "poi_activity",
            "name": "陶艺体验",
            "category": "social_activity",
            "booking_supported": True,
        }
    }

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, _constraints(["activity_reservation"]))

    assert _without_ids(actions) == [
        {
            "revision_id": "rev_1",
            "tool": "reserve_activity",
            "label": "预约活动",
            "target": "陶艺体验",
            "status": "pending",
            "requires_confirmation": True,
            "payload": {"place_id": "poi_activity", "time": "14:00", "party_size": 3},
            "receipt_id": "",
        }
    ]


def test_policy_omits_activity_reservation_when_candidate_category_is_restaurant():
    plan = {
        "itinerary": [
            {"type": "activity", "title": "陶艺体验", "place_id": "poi_activity", "start": "14:00"},
        ]
    }
    candidate_lookup = {
        "poi_activity": {
            "id": "poi_activity",
            "name": "陶艺体验",
            "category": "restaurant",
            "booking_supported": True,
        }
    }

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, _constraints(["activity_reservation"]))

    assert actions == []


def test_policy_omits_activity_reservation_when_candidate_category_is_missing():
    plan = {
        "itinerary": [
            {"type": "activity", "title": "陶艺体验", "place_id": "poi_activity", "start": "14:00"},
        ]
    }
    candidate_lookup = {
        "poi_activity": {
            "id": "poi_activity",
            "name": "陶艺体验",
            "booking_supported": True,
        }
    }

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, _constraints(["activity_reservation"]))

    assert actions == []


def test_policy_creates_restaurant_actions_only_when_requested_and_grounded():
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
            "category": "restaurant",
            "booking_supported": True,
            "coupon": {"id": "deal_1", "title": "双人套餐"},
            "menu": [{"id": "menu_1", "name": "低脂鸡胸沙拉"}],
        },
    }
    constraints = _constraints(["restaurant_reservation", "claim_coupon", "create_order"], user_id="user_1")

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, constraints)

    assert [action["tool"] for action in actions] == ["create_reservation", "claim_coupon", "create_order"]
    assert _without_ids(actions) == [
        {
            "revision_id": "rev_1",
            "tool": "create_reservation",
            "label": "预订餐厅",
            "target": "绿荫轻食餐厅",
            "status": "pending",
            "requires_confirmation": True,
            "payload": {"place_id": "poi_restaurant", "time": "16:00", "party_size": 3},
            "receipt_id": "",
        },
        {
            "revision_id": "rev_1",
            "tool": "claim_coupon",
            "label": "领取团购券",
            "target": "绿荫轻食餐厅",
            "status": "pending",
            "requires_confirmation": True,
            "payload": {"place_id": "poi_restaurant", "deal_id": "deal_1", "user_id": "user_1"},
            "receipt_id": "",
        },
        {
            "revision_id": "rev_1",
            "tool": "create_order",
            "label": "创建点单",
            "target": "绿荫轻食餐厅",
            "status": "pending",
            "requires_confirmation": True,
            "payload": {
                "shop_id": "poi_restaurant",
                "items": [{"id": "menu_1", "name": "低脂鸡胸沙拉"}],
                "pickup_time": "16:00",
                "party_size": 3,
            },
            "receipt_id": "",
        },
    ]


def test_policy_omits_claim_coupon_when_user_id_is_missing():
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "绿荫轻食餐厅", "place_id": "poi_restaurant", "start": "16:00"},
        ]
    }
    candidate_lookup = {
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "绿荫轻食餐厅",
            "category": "restaurant",
            "coupon": {"id": "deal_1", "title": "双人套餐"},
        },
    }

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, _constraints(["claim_coupon"]))

    assert actions == []


def test_policy_omits_requested_restaurant_actions_when_candidate_data_is_ungrounded():
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "无预约餐厅", "place_id": "poi_restaurant", "start": "16:00", "end": "17:00"},
        ]
    }
    candidate_lookup = {
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "无预约餐厅",
            "category": "restaurant",
            "booking_supported": False,
            "coupon": True,
            "menu": True,
        }
    }

    actions = _assert_deterministic(
        "rev_1",
        plan,
        candidate_lookup,
        _constraints(["restaurant_reservation", "claim_coupon", "create_order"], user_id="user_1"),
    )

    assert actions == []


def test_policy_requires_booking_supported_to_be_exactly_true():
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "字符串预约餐厅", "place_id": "poi_restaurant", "start": "16:00"},
        ]
    }

    for booking_supported in ("true", "false", 1):
        candidate_lookup = {
            "poi_restaurant": {
                "id": "poi_restaurant",
                "name": "字符串预约餐厅",
                "category": "restaurant",
                "booking_supported": booking_supported,
            }
        }
        actions = _assert_deterministic("rev_1", plan, candidate_lookup, _constraints(["restaurant_reservation"]))
        assert actions == []


def test_policy_omits_actions_for_candidate_identity_mismatch():
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "旧餐厅", "place_id": "poi_restaurant", "start": "16:00"},
        ]
    }
    candidate_lookup = {
        "poi_restaurant": {
            "id": "different_restaurant",
            "name": "旧餐厅",
            "category": "restaurant",
            "booking_supported": True,
            "coupon": {"id": "deal_1"},
            "menu": [{"id": "menu_1", "name": "沙拉"}],
        }
    }

    actions = _assert_deterministic(
        "rev_1",
        plan,
        candidate_lookup,
        _constraints(["restaurant_reservation", "claim_coupon", "create_order"], user_id="user_1"),
    )

    assert actions == []


def test_policy_requires_restaurant_category_when_candidate_category_is_present():
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "活动场地", "place_id": "poi_restaurant", "start": "16:00"},
        ]
    }
    candidate_lookup = {
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "活动场地",
            "category": "activity",
            "booking_supported": True,
            "coupon": {"id": "deal_1"},
            "menu": [{"id": "menu_1", "name": "沙拉"}],
        }
    }

    actions = _assert_deterministic(
        "rev_1",
        plan,
        candidate_lookup,
        _constraints(["restaurant_reservation", "claim_coupon", "create_order"], user_id="user_1"),
    )

    assert actions == []


def test_policy_omits_restaurant_actions_when_candidate_category_is_missing():
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "无分类餐厅", "place_id": "poi_restaurant", "start": "16:00"},
        ]
    }
    candidate_lookup = {
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "无分类餐厅",
            "booking_supported": True,
        }
    }

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, _constraints(["restaurant_reservation"]))

    assert actions == []


def test_policy_requires_non_empty_string_deal_id_and_concrete_menu_items():
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "无效餐厅", "place_id": "poi_restaurant", "start": "16:00"},
        ]
    }
    invalid_candidates = [
        {"id": "poi_restaurant", "category": "restaurant", "coupon": True, "menu": True},
        {"id": "poi_restaurant", "category": "restaurant", "deal_id": True, "menus": {"id": "menu_1"}},
        {"id": "poi_restaurant", "category": "restaurant", "coupon": {"id": ""}, "menu": [{"name": "沙拉"}]},
    ]

    for candidate in invalid_candidates:
        actions = _assert_deterministic(
            "rev_1",
            plan,
            {"poi_restaurant": candidate},
            _constraints(["claim_coupon", "create_order"], user_id="user_1"),
        )
        assert actions == []


def test_policy_action_id_and_idempotency_key_ignore_display_title_changes():
    base_step = {"type": "restaurant", "title": "旧标题", "place_id": "poi_restaurant", "start": "16:00"}
    plan = {"itinerary": [base_step]}
    changed_title_plan = {"itinerary": [{**base_step, "title": "新标题"}]}
    candidate_lookup = {
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "候选餐厅",
            "category": "restaurant",
            "booking_supported": True,
        }
    }
    constraints = _constraints(["restaurant_reservation"])

    original = _assert_deterministic("rev_1", plan, candidate_lookup, constraints)
    changed_title = _assert_deterministic("rev_1", changed_title_plan, candidate_lookup, constraints)

    assert original[0]["payload"] == changed_title[0]["payload"]
    assert original[0]["action_id"] == changed_title[0]["action_id"]
    assert original[0]["idempotency_key"] == changed_title[0]["idempotency_key"]


def test_policy_action_id_and_idempotency_key_ignore_unrelated_earlier_non_action_step():
    restaurant_step = {"type": "restaurant", "title": "绿荫轻食餐厅", "place_id": "poi_restaurant", "start": "16:00"}
    plan = {"itinerary": [restaurant_step]}
    inserted_step_plan = {
        "itinerary": [
            {"type": "activity", "title": "路过公园", "place_id": "poi_activity", "start": "15:00"},
            restaurant_step,
        ]
    }
    candidate_lookup = {
        "poi_activity": {"id": "poi_activity", "name": "路过公园", "category": "activity", "booking_supported": False},
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "绿荫轻食餐厅",
            "category": "restaurant",
            "booking_supported": True,
        },
    }
    constraints = _constraints(["restaurant_reservation"])

    original = _assert_deterministic("rev_1", plan, candidate_lookup, constraints)
    inserted = _assert_deterministic("rev_1", inserted_step_plan, candidate_lookup, constraints)

    assert [action["tool"] for action in inserted] == ["create_reservation"]
    assert original[0]["payload"] == inserted[0]["payload"]
    assert original[0]["action_id"] == inserted[0]["action_id"]
    assert original[0]["idempotency_key"] == inserted[0]["idempotency_key"]


def test_policy_party_size_counts_none_children_as_zero():
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "绿荫轻食餐厅", "place_id": "poi_restaurant", "start": "16:00"},
        ]
    }
    candidate_lookup = {
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "绿荫轻食餐厅",
            "category": "restaurant",
            "booking_supported": True,
        },
    }
    constraints = {"people": {"adults": 2, "children": None}, "required_actions": ["restaurant_reservation"]}

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, constraints)

    assert actions[0]["payload"]["party_size"] == 2


def test_policy_party_size_uses_int_children_count():
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "绿荫轻食餐厅", "place_id": "poi_restaurant", "start": "16:00"},
        ]
    }
    candidate_lookup = {
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "绿荫轻食餐厅",
            "category": "restaurant",
            "booking_supported": True,
        },
    }
    constraints = {"people": {"adults": 2, "children": 2}, "required_actions": ["restaurant_reservation"]}

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, constraints)

    assert actions[0]["payload"]["party_size"] == 4


def test_policy_party_size_defaults_invalid_adults_to_zero():
    plan = {
        "itinerary": [
            {"type": "restaurant", "title": "绿荫轻食餐厅", "place_id": "poi_restaurant", "start": "16:00"},
        ]
    }
    candidate_lookup = {
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "绿荫轻食餐厅",
            "category": "restaurant",
            "booking_supported": True,
        },
    }
    constraints = {"people": {"adults": "bad", "children": [{"age": 7}]}, "required_actions": ["restaurant_reservation"]}

    actions = _assert_deterministic("rev_1", plan, candidate_lookup, constraints)

    assert actions[0]["payload"]["party_size"] == 1
