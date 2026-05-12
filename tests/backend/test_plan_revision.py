from tests.backend.helpers import planning_service_with_fake_llm


def test_revision_applies_natural_language_feedback_and_returns_diff():
    service = planning_service_with_fake_llm()
    built = service.build_plan("今天下午朋友4个人出去玩，先活动再吃饭，预算适中")
    plan_id = built["plan"]["id"]
    restaurant_ids = [step["place_id"] for step in built["plan"]["itinerary"] if step["type"] == "restaurant"]
    assert restaurant_ids

    revised = service.revise_plan(
        plan_id,
        {
            "feedback_text": "太赶了，餐厅不想去了，换成轻松一点的散步和咖啡",
            "selected_issue_codes": ["too_rushed", "remove_restaurant"],
            "locked_nodes": [],
            "removed_nodes": restaurant_ids,
            "preference_updates": {"pace": "slow", "meal_required": False},
            "save_to_profile": True,
            "user_id": "user_1",
        },
    )

    assert revised["revision"]["revision_id"].startswith("rev_")
    assert "restaurant" not in [step["type"] for step in revised["plan"]["itinerary"]]
    assert revised["diff"]["removed"]
    assert revised["diff"]["changed_constraints"]["pace"] == ["medium", "slow"]
    assert revised["learned_preferences"][0]["key"] == "pace"


def test_revision_preserves_locked_nodes():
    service = planning_service_with_fake_llm()
    built = service.build_plan("想带狗狗找个能散步的地方，别太吵")
    plan_id = built["plan"]["id"]
    activity = next(step for step in built["plan"]["itinerary"] if step["type"] == "activity")

    revised = service.revise_plan(
        plan_id,
        {
            "feedback_text": "预算低一点，但这个活动保留",
            "selected_issue_codes": ["cheaper"],
            "locked_nodes": [activity["place_id"]],
            "removed_nodes": [],
            "preference_updates": {"budget_level": "low"},
            "save_to_profile": False,
            "user_id": "user_1",
        },
    )

    revised_activity = next(step for step in revised["plan"]["itinerary"] if step["type"] == "activity")
    assert revised_activity["place_id"] == activity["place_id"]
