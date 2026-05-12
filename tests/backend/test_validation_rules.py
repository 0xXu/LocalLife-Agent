from backend.models.schemas import ItineraryStep, ParsedConstraints
from backend.validation.rules import validate_itinerary


def test_validation_flags_weather_and_opening_hours_risks():
    constraints = ParsedConstraints(
        scenario="rainy_indoor",
        origin={"type": "current_location", "label": "home", "lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 2, "flexible": True},
        people={"adults": 2, "children": [], "relationship": "friends"},
        preferences={"distance": "nearby", "diet": [], "activity": ["outdoor"], "budget_level": "medium"},
        constraints={"radius_km": 8, "max_wait_minutes": 15, "avoid": ["outdoor"]},
        required_actions=["send_plan_message"],
    )
    steps = [
        ItineraryStep("14:00", "15:30", "activity", "山野徒步步道", "poi_hike", "户外", "约 100 元", "到达活动点", 90, "风险低。")
    ]
    candidate_lookup = {
        "poi_hike": {"open_hours": [{"day": "sat", "start": "10:00", "end": "13:00"}], "tags": ["outdoor"], "avg_price": 100, "booking_supported": True}
    }

    report = validate_itinerary(steps, constraints, candidate_lookup, weather={"condition": "rain", "rain_probability": 0.86}, route={"total_travel_minutes": 12})

    assert not report.valid
    assert {issue["code"] for issue in report.issues} >= {"closed_at_visit_time", "weather_mismatch"}


def test_validation_passes_grounded_short_plan():
    constraints = ParsedConstraints(
        scenario="deep_work_cafe",
        origin={"type": "current_location", "label": "home", "lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 1, "flexible": True},
        people={"adults": 1, "children": [], "relationship": "solo"},
        preferences={"distance": "nearby", "diet": [], "activity": ["work", "quiet"], "budget_level": "medium"},
        constraints={"radius_km": 8, "max_wait_minutes": 15, "avoid": []},
        required_actions=["send_plan_message"],
    )
    steps = [
        ItineraryStep("14:00", "15:00", "activity", "自习咖啡馆", "poi_cafe", "安静", "约 80 元", "到达活动点", 90, "风险低。")
    ]
    candidate_lookup = {
        "poi_cafe": {"open_hours": [{"day": "sat", "start": "10:00", "end": "22:00"}], "tags": ["work", "quiet"], "avg_price": 80, "booking_supported": True}
    }

    report = validate_itinerary(steps, constraints, candidate_lookup, weather={"condition": "clear", "rain_probability": 0.1}, route={"total_travel_minutes": 12})

    assert report.valid
    assert report.issues == []
