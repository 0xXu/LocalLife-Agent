from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.schemas import ParsedConstraints
from backend.providers.contracts import GroundedPlace


@dataclass
class RankedCandidate:
    place: GroundedPlace
    total_score: float
    breakdown: dict[str, float]
    explanation: str


@dataclass
class RankedCandidateSet:
    items: list[RankedCandidate]
    rejected: list[dict] = field(default_factory=list)


def rank_candidates(items: list[GroundedPlace], constraints: ParsedConstraints, top_k: int = 8) -> RankedCandidateSet:
    ranked: list[RankedCandidate] = []
    rejected: list[dict] = []
    radius_km = float(constraints.constraints.get("radius_km", 8))

    for item in items:
        if item.distance_km > radius_km:
            rejected.append({"id": item.id, "reason": "outside_radius", "distance_km": item.distance_km})
            continue
        breakdown = score_breakdown(item, constraints)
        total = round(sum(breakdown.values()), 3)
        ranked.append(RankedCandidate(item, total, breakdown, explanation_for(item, breakdown)))

    ranked.sort(key=lambda value: value.total_score, reverse=True)
    overflow = [{"id": item.place.id, "reason": "below_top_k"} for item in ranked[top_k:]]
    return RankedCandidateSet(items=ranked[:top_k], rejected=rejected + overflow)


def score_breakdown(item: GroundedPlace, constraints: ParsedConstraints) -> dict[str, float]:
    tags = set(item.tags)
    preferred = set(constraints.preferences.get("activity", [])) | set(constraints.preferences.get("diet", []))
    avoid = set(constraints.constraints.get("avoid", []))
    radius = max(float(constraints.constraints.get("radius_km", 8)), 1.0)
    max_wait = max(int(constraints.constraints.get("max_wait_minutes", 15)), 1)
    budget_level = str(constraints.preferences.get("budget_level", "medium"))
    risk_penalty = 0.2 if avoid & set(item.risk_tags) else 0.0
    return {
        "semantic": min(0.32, len(tags & preferred) * 0.09),
        "distance": max(0.0, 0.22 * (1 - item.distance_km / radius)),
        "quality": min(0.2, item.rating / 5 * 0.2),
        "wait": max(0.0, 0.14 * (1 - item.wait_minutes / max_wait)),
        "budget": budget_score(budget_level, item.avg_price),
        "provenance": min(0.08, item.provenance.confidence * 0.08),
        "risk": -risk_penalty,
    }


def budget_score(level: str, avg_price: int) -> float:
    if level == "low":
        return 0.12 if avg_price <= 160 else 0.05 if avg_price <= 260 else 0.0
    if level == "high":
        return 0.1 if avg_price <= 600 else 0.04
    return 0.12 if avg_price <= 360 else 0.05


def explanation_for(item: GroundedPlace, breakdown: dict[str, float]) -> str:
    best = max(breakdown, key=lambda key: breakdown[key])
    labels = {
        "semantic": "偏好匹配高",
        "distance": "距离更近",
        "quality": "评分较好",
        "wait": "等待更短",
        "budget": "预算更合适",
        "provenance": "来源可信度较高",
        "risk": "风险更低",
    }
    return f"{item.name}：{labels.get(best, '综合匹配较好')}。"
