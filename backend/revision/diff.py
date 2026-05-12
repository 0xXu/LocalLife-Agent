from __future__ import annotations


def build_plan_diff(before: dict, after: dict, changed_constraints: dict) -> dict:
    before_steps = {step.get("place_id"): step for step in before.get("itinerary", []) if step.get("place_id")}
    after_steps = {step.get("place_id"): step for step in after.get("itinerary", []) if step.get("place_id")}
    kept = [step["title"] for place_id, step in after_steps.items() if place_id in before_steps]
    removed = [{"id": place_id, "title": step["title"], "reason": "user_feedback"} for place_id, step in before_steps.items() if place_id not in after_steps]
    added = [{"id": place_id, "title": step["title"]} for place_id, step in after_steps.items() if place_id not in before_steps]
    return {
        "kept": kept,
        "removed": removed,
        "added": added,
        "changed_constraints": changed_constraints,
    }
