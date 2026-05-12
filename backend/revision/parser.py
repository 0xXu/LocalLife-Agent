from __future__ import annotations

from backend.revision.models import PlanFeedback, RevisionDelta, new_revision_delta


def parse_feedback(body: dict) -> PlanFeedback:
    return PlanFeedback(
        feedback_text=str(body.get("feedback_text", "")),
        selected_issue_codes=[str(item) for item in body.get("selected_issue_codes", [])],
        locked_nodes=[str(item) for item in body.get("locked_nodes", [])],
        removed_nodes=[str(item) for item in body.get("removed_nodes", [])],
        preference_updates=dict(body.get("preference_updates", {})),
        save_to_profile=bool(body.get("save_to_profile", False)),
        user_id=str(body.get("user_id", "local_demo_user")),
    )


def feedback_to_delta(body: dict) -> RevisionDelta:
    feedback = parse_feedback(body)
    updates = dict(feedback.preference_updates)
    text = feedback.feedback_text
    if "太赶" in text or "轻松" in text or "慢" in text:
        updates["pace"] = "slow"
        updates["duration_hours"] = max(float(updates.get("duration_hours", 4.0)), 4.0)
    if "不想吃" in text or "餐厅不想去" in text or "不要餐厅" in text:
        updates["meal_required"] = False
    if "预算低" in text or "便宜" in text or "省钱" in text:
        updates["budget_level"] = "low"
    feedback.preference_updates = updates
    return new_revision_delta(feedback)
