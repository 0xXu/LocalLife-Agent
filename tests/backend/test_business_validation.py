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
