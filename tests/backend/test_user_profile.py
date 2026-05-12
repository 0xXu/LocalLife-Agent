from pathlib import Path

from backend.models.schemas import ParsedConstraints
from backend.profile.models import UserPreference, UserProfile
from backend.profile.resolver import merge_profile_into_goal_context
from backend.profile.store import UserProfileStore


def test_profile_store_persists_explicit_and_learned_preferences(tmp_path: Path):
    store = UserProfileStore(tmp_path / "profiles.sqlite")
    profile = UserProfile(
        user_id="user_1",
        explicit_preferences=[
            UserPreference("pace", "slow", "explicit", 1.0, "long_term", "用户主动选择慢节奏"),
            UserPreference("budget_level", "low", "explicit", 1.0, "long_term", "用户主动选择低预算"),
        ],
        learned_preferences=[
            UserPreference("avoid", "long_queue", "feedback", 0.82, "long_term", "连续两次反馈不想排队"),
        ],
    )

    store.save(profile)
    loaded = store.get("user_1")

    assert loaded.user_id == "user_1"
    assert loaded.preference_value("pace") == "slow"
    assert loaded.preference_value("budget_level") == "low"
    assert loaded.preferences_by_key("avoid")[0].confidence == 0.82


def test_current_goal_overrides_profile_preferences():
    profile = UserProfile(
        user_id="user_1",
        explicit_preferences=[UserPreference("budget_level", "low", "explicit", 1.0, "long_term", "用户偏好低预算")],
        learned_preferences=[UserPreference("pace", "slow", "feedback", 0.8, "long_term", "用户常反馈太赶")],
    )
    constraints = ParsedConstraints(
        scenario="date",
        origin={"type": "current_location", "label": "home", "lat": 38.26, "lng": 140.88},
        time_window={"date": "today", "start": "14:00", "duration_hours": 3, "flexible": True},
        people={"adults": 2, "children": [], "relationship": "date"},
        preferences={"distance": "nearby", "diet": [], "activity": ["quiet"], "budget_level": "high"},
        constraints={"radius_km": 8, "max_wait_minutes": 15, "avoid": []},
        required_actions=["send_plan_message"],
    )

    merged = merge_profile_into_goal_context(constraints, profile)

    assert merged.preferences["budget_level"] == "high"
    assert merged.preferences["pace"] == "slow"
    assert "long_queue" not in merged.constraints["avoid"]
