from __future__ import annotations

from backend.models.schemas import ItineraryStep, ParsedConstraints, PlanVariant


def build_itinerary_variants(
    base_steps: list[ItineraryStep],
    activity_candidates: list[dict],
    restaurant_candidates: list[dict],
    walk_candidates: list[dict],
    constraints: ParsedConstraints,
    base_score: int,
) -> list[PlanVariant]:
    experience_title = "孩子优先版" if constraints.scenario == "family" else "体验优先版"
    experience_kind = "child_first" if constraints.scenario == "family" else "experience_first"
    selected_main = selected_places(base_steps)
    specs = [
        ("main", "主方案", "综合距离、可订性和偏好匹配。", 0, "ranked"),
        ("budget", "省钱版", "优先使用低客单价且仍满足约束的点位。", -5, "budget"),
        ("comfort", "舒适版", "减少等待和路程，优先高评分点位。", 2, "comfort"),
        (experience_kind, experience_title, "优先照顾活动体验和节奏。", -1, "experience"),
    ]
    variants: list[PlanVariant] = []
    seen: set[tuple[str, ...]] = set()
    for kind, title, summary, score_delta, strategy in specs:
        picks = {
            "activity": pick_candidate(activity_candidates, strategy, selected_main.get("activity")),
            "restaurant": pick_candidate(restaurant_candidates, strategy, selected_main.get("restaurant")),
            "dessert_walk": pick_candidate(walk_candidates, strategy, selected_main.get("dessert_walk")),
        }
        steps = replace_steps(base_steps, picks, constraints)
        place_ids = tuple(step.place_id for step in steps if step.place_id and step.place_id != "origin_home")
        if place_ids in seen and strategy != "ranked":
            steps = replace_steps(base_steps, next_available_picks(picks, activity_candidates, restaurant_candidates, walk_candidates, seen), constraints)
            place_ids = tuple(step.place_id for step in steps if step.place_id and step.place_id != "origin_home")
        seen.add(place_ids)
        budget = estimate_budget(steps, picks)
        variants.append(
            PlanVariant(
                kind,
                title,
                summary,
                max(60, min(98, variant_score(steps, base_score + score_delta))),
                budget,
                steps,
            )
        )
    return variants


def selected_places(steps: list[ItineraryStep]) -> dict[str, str]:
    return {step.type: step.place_id for step in steps if step.place_id and step.place_id != "origin_home"}


def pick_candidate(candidates: list[dict], strategy: str, main_id: str | None) -> dict | None:
    if not candidates:
        return None
    ordered = list(candidates)
    if strategy == "budget":
        ordered.sort(key=lambda item: (int(item.get("avg_price", 0)), float(item.get("distance_km", 99))))
    elif strategy == "comfort":
        ordered.sort(key=lambda item: (int(item.get("wait_minutes", 99)), float(item.get("distance_km", 99)), -float(item.get("rating", 0))))
    elif strategy == "experience":
        ordered.sort(key=lambda item: (-float(item.get("rating", 0)), int(item.get("wait_minutes", 99)), float(item.get("distance_km", 99))))
    if strategy != "ranked":
        for item in ordered:
            if item.get("id") != main_id:
                return item
    return ordered[0]


def next_available_picks(
    picks: dict[str, dict | None],
    activity_candidates: list[dict],
    restaurant_candidates: list[dict],
    walk_candidates: list[dict],
    seen: set[tuple[str, ...]],
) -> dict[str, dict | None]:
    candidate_groups = {
        "activity": activity_candidates,
        "restaurant": restaurant_candidates,
        "dessert_walk": walk_candidates,
    }
    for key, candidates in candidate_groups.items():
        for candidate in candidates:
            trial = dict(picks)
            trial[key] = candidate
            place_ids = tuple(item["id"] for item in trial.values() if item)
            if place_ids not in seen:
                return trial
    return picks


def replace_steps(base_steps: list[ItineraryStep], picks: dict[str, dict | None], constraints: ParsedConstraints) -> list[ItineraryStep]:
    steps: list[ItineraryStep] = []
    for step in base_steps:
        place = picks.get(step.type)
        if not place:
            steps.append(copy_step(step))
            continue
        steps.append(
            ItineraryStep(
                step.start,
                step.end,
                step.type,
                place["name"],
                place["id"],
                place["reason"],
                f"约 {place['avg_price']} 元",
                step.travel,
                score_place(place, constraints),
                risk_text(place),
            )
        )
    return steps


def estimate_budget(steps: list[ItineraryStep], picks: dict[str, dict | None]) -> int:
    used_ids = {step.place_id for step in steps if step.place_id and step.place_id != "origin_home"}
    return sum(int(place.get("avg_price", 0)) for place in picks.values() if place and place.get("id") in used_ids)


def variant_score(steps: list[ItineraryStep], fallback: int) -> int:
    place_scores = [step.score for step in steps if step.place_id != "origin_home"]
    if not place_scores:
        return fallback
    return round((sum(place_scores) / len(place_scores) + fallback) / 2)


def score_place(item: dict, constraints: ParsedConstraints) -> int:
    tags = set(item.get("tags", []))
    preferred = set(constraints.preferences.get("activity", [])) | set(constraints.preferences.get("diet", []))
    score = 76 + int(float(item.get("rating", 4.0)) * 3)
    score += min(6, 2 * len(tags & preferred))
    score -= min(6, int(item.get("wait_minutes", 0)) // 8)
    return max(70, min(98, score))


def risk_text(poi: dict) -> str:
    return "周末可能排队，建议提前确认。" if poi.get("risk_tags") else "风险低。"


def copy_step(step: ItineraryStep) -> ItineraryStep:
    return ItineraryStep(step.start, step.end, step.type, step.title, step.place_id, step.reason, step.cost, step.travel, step.score, step.risk)
