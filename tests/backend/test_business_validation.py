from datetime import date, timedelta

from backend.validation import validate_revision_for_approval


_DEFAULT_CHILDREN = object()


def _constraints(adults=2, children=_DEFAULT_CHILDREN):
    if children is _DEFAULT_CHILDREN:
        children = [{"age": 8}]
    return {
        "time_window": {"date": "2026-05-13"},
        "people": {"adults": adults, "children": children},
    }


def _plan(steps=None, route=None):
    return {
        "itinerary": steps
        or [
            {"type": "activity", "title": "Pottery", "place_id": "poi_activity", "start": "14:00", "end": "15:30"},
            {"type": "restaurant", "title": "Cafe", "place_id": "poi_restaurant", "start": "16:00", "end": "17:00"},
        ],
        "route": route
        if route is not None
        else {
            "legs": [
                {"from": "origin_home", "to": "poi_activity", "mode": "taxi"},
                {"from": "poi_activity", "to": "poi_restaurant", "mode": "walk"},
            ]
        },
    }


def _candidates():
    return {
        "poi_activity": {
            "id": "poi_activity",
            "name": "Pottery",
            "category": "activity",
            "tags": ["indoor"],
            "open_hours": [{"date": "2026-05-13", "start": "10:00", "end": "20:00"}],
        },
        "poi_restaurant": {
            "id": "poi_restaurant",
            "name": "Cafe",
            "category": "restaurant",
            "tags": ["food"],
            "open_hours": [{"date": "2026-05-13", "start": "11:00", "end": "22:00"}],
            "availability": [{"time": "16:00", "available": True, "capacity": 4}],
        },
    }


def _actions():
    return [
        {
            "tool": "create_reservation",
            "idempotency_key": "rev_1:create_reservation:abc",
            "payload": {"place_id": "poi_restaurant", "time": "16:00", "party_size": 3},
        }
    ]


def _codes(report, bucket="blocking"):
    return {issue["code"] for issue in report[bucket]}


def test_validation_blocks_mismatched_availability_slot():
    candidates = _candidates()
    candidates["poi_restaurant"]["availability"] = [{"time": "17:00", "available": True, "capacity": 4}]

    report = validate_revision_for_approval(_plan(), candidates, _constraints(), _actions(), {"condition": "clear"})

    assert not report["valid"]
    assert "availability_slot_mismatch" in _codes(report)


def test_validation_blocks_missing_origin_route_leg():
    plan = _plan(route={"legs": [{"from": "poi_activity", "to": "poi_restaurant", "mode": "walk"}]})

    report = validate_revision_for_approval(plan, _candidates(), _constraints(), _actions(), {"condition": "clear"})

    assert not report["valid"]
    assert "missing_origin_route_leg" in _codes(report)


def test_validation_passes_grounded_executable_plan():
    plan = _plan(
        steps=[
            {"type": "transport", "title": "Taxi", "place_id": "transit_1", "start": "13:40", "end": "14:00"},
            {"type": "activity", "title": "Pottery", "place_id": "poi_activity", "start": "14:00", "end": "15:30"},
            {"type": "restaurant", "title": "Cafe", "place_id": "poi_restaurant", "start": "16:00", "end": "17:00"},
        ]
    )

    report = validate_revision_for_approval(plan, _candidates(), _constraints(), _actions(), {"condition": "clear"})

    assert report == {"valid": True, "blocking": [], "warnings": []}


def test_weather_mismatch_is_warning_only_and_report_remains_valid_without_blockers():
    candidates = _candidates()
    candidates["poi_activity"]["tags"] = ["outdoor", "park"]

    report = validate_revision_for_approval(_plan(), candidates, _constraints(), _actions(), {"condition": "rain"})

    assert report["valid"]
    assert report["blocking"] == []
    assert "weather_mismatch" in _codes(report, "warnings")


def test_action_time_mismatch_or_missing_idempotency_key_blocks():
    actions = [
        {
            "tool": "create_reservation",
            "payload": {"place_id": "poi_restaurant", "time": "17:00", "party_size": 3},
        }
    ]

    report = validate_revision_for_approval(_plan(), _candidates(), _constraints(), actions, {"condition": "clear"})

    assert not report["valid"]
    assert _codes(report) >= {"missing_idempotency_key", "action_time_mismatch"}


def test_robust_party_size_children_none_and_invalid_adults_do_not_crash_zero_party_blocks():
    constraints = _constraints(adults="bad", children=None)

    report = validate_revision_for_approval(_plan(), _candidates(), constraints, [], {"condition": "clear"})

    assert not report["valid"]
    assert "party_size_missing" in _codes(report)


def test_today_day_open_hours_and_non_zero_padded_visit_time_match():
    candidates = _candidates()
    candidates["poi_activity"]["open_hours"] = [{"day": "today", "start": "09:00", "end": "17:00"}]
    constraints = _constraints()
    constraints["time_window"]["date"] = "today"
    plan = _plan(
        steps=[
            {"type": "activity", "title": "Pottery", "place_id": "poi_activity", "start": "9:00", "end": "10:00"},
        ],
        route={"legs": [{"from": "origin_home", "to": "poi_activity", "mode": "taxi"}]},
    )

    report = validate_revision_for_approval(plan, candidates, constraints, [], {"condition": "clear"})

    assert "closed_at_visit_time" not in _codes(report)


def test_relative_today_weekday_open_hours_match_only_today_weekday():
    candidates = _candidates()
    today_name = date.today().strftime("%A")
    other_day_name = (date.today() + timedelta(days=1)).strftime("%A")
    plan = _plan(
        steps=[
            {"type": "activity", "title": "Pottery", "place_id": "poi_activity", "start": "10:00", "end": "11:00"},
        ],
        route={"legs": [{"from": "origin_home", "to": "poi_activity", "mode": "taxi"}]},
    )
    constraints = _constraints()
    constraints["time_window"]["date"] = "today"

    candidates["poi_activity"]["open_hours"] = [{"day": today_name, "start": "09:00", "end": "17:00"}]
    matching_report = validate_revision_for_approval(plan, candidates, constraints, [], {"condition": "clear"})

    candidates["poi_activity"]["open_hours"] = [{"day": other_day_name, "start": "09:00", "end": "17:00"}]
    mismatching_report = validate_revision_for_approval(plan, candidates, constraints, [], {"condition": "clear"})

    assert "closed_at_visit_time" not in _codes(matching_report)
    assert "closed_at_visit_time" in _codes(mismatching_report)


def test_restaurant_empty_availability_blocks_slot_mismatch():
    candidates = _candidates()
    candidates["poi_restaurant"]["availability"] = []

    report = validate_revision_for_approval(_plan(), candidates, _constraints(), _actions(), {"condition": "clear"})

    assert not report["valid"]
    assert "availability_slot_mismatch" in _codes(report)


def test_send_plan_message_empty_payload_blocks_payload_missing():
    actions = [{"tool": "send_plan_message", "idempotency_key": "rev_1:send_plan_message:abc", "payload": {}}]

    report = validate_revision_for_approval(_plan(), _candidates(), _constraints(), actions, {"condition": "clear"})

    assert not report["valid"]
    assert "action_payload_missing" in _codes(report)


def test_place_bound_action_missing_place_or_shop_id_blocks_ungrounded_action():
    actions = [
        {
            "tool": "create_reservation",
            "idempotency_key": "rev_1:create_reservation:missing-place",
            "payload": {"time": "16:00", "party_size": 3},
        }
    ]

    report = validate_revision_for_approval(_plan(), _candidates(), _constraints(), actions, {"condition": "clear"})

    assert not report["valid"]
    assert "ungrounded_action" in _codes(report)


def test_leading_transport_step_from_origin_satisfies_origin_route_without_legs():
    plan = _plan(
        steps=[
            {"type": "transport", "title": "Taxi", "from": "origin_home", "to": "poi_activity", "start": "13:40", "end": "14:00"},
            {"type": "activity", "title": "Pottery", "place_id": "poi_activity", "start": "14:00", "end": "15:30"},
            {"type": "restaurant", "title": "Cafe", "place_id": "poi_restaurant", "start": "16:00", "end": "17:00"},
        ],
        route={"legs": []},
    )

    report = validate_revision_for_approval(plan, _candidates(), _constraints(), _actions(), {"condition": "clear"})

    assert "missing_origin_route_leg" not in _codes(report)


def test_reservation_action_missing_party_size_blocks():
    actions = [
        {
            "tool": "create_reservation",
            "idempotency_key": "rev_1:create_reservation:no-party",
            "payload": {"place_id": "poi_restaurant", "time": "16:00"},
        }
    ]

    report = validate_revision_for_approval(_plan(), _candidates(), _constraints(), actions, {"condition": "clear"})

    assert not report["valid"]
    assert "action_party_size_missing" in _codes(report)


def test_order_action_people_mismatch_blocks_against_computed_party_size():
    actions = [
        {
            "tool": "create_order",
            "idempotency_key": "rev_1:create_order:people-mismatch",
            "payload": {"shop_id": "poi_restaurant", "pickup_time": "16:00", "people": 2},
        }
    ]

    report = validate_revision_for_approval(_plan(), _candidates(), _constraints(), actions, {"condition": "clear"})

    assert not report["valid"]
    assert "action_party_size_mismatch" in _codes(report)


def test_create_order_shop_id_from_candidate_alias_is_grounded():
    candidates = _candidates()
    candidates["poi_restaurant"]["shop_id"] = "shop_cafe"
    actions = [
        {
            "tool": "create_order",
            "idempotency_key": "rev_1:create_order:shop-alias",
            "payload": {"shop_id": "shop_cafe", "pickup_time": "16:00", "party_size": 3},
        }
    ]

    report = validate_revision_for_approval(_plan(), candidates, _constraints(), actions, {"condition": "clear"})

    assert "ungrounded_action" not in _codes(report)
