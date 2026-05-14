from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.models.schemas import ParsedConstraints


class RankerAgent(BaseAgent):
    def __init__(self, llm: Any) -> None:
        super().__init__("RankerAgent", llm)
        self.last_reasoning: str = ""

    def rank(self, candidates: dict[str, list[dict]], constraints: ParsedConstraints) -> dict[str, list[dict]]:
        system_prompt = (
            "You are a local-life planning ranker. Given candidates and user constraints, "
            "select the best items for each category (activities, restaurants, walks). "
            "Return JSON: {\"ranked\": {\"activities\": [{\"id\": \"...\", \"reason\": \"...\"}], "
            "\"restaurants\": [...], \"walks\": [...]}, \"reasoning\": \"...\"}\n"
            "Select 1-3 items per category. Prefer items matching user tags, closer distance, "
            "lower wait time, and appropriate budget level."
        )
        context = {
            "candidates": {k: [_candidate_brief(item) for item in v] for k, v in candidates.items()},
            "constraints": {
                "scenario": constraints.scenario,
                "activity_tags": constraints.preferences.get("activity", []),
                "diet_tags": constraints.preferences.get("diet", []),
                "budget_level": constraints.preferences.get("budget_level", "medium"),
                "radius_km": constraints.constraints.get("radius_km", 8),
                "max_wait_minutes": constraints.constraints.get("max_wait_minutes", 15),
                "people": constraints.people,
            },
        }

        result = self.run_llm(system_prompt, context)
        if result and "ranked" in result:
            self.last_reasoning = result.get("reasoning", "")
            return _merge_ranked_with_candidates(result["ranked"], candidates)

        # Fallback: deterministic ranking by existing score
        self.last_reasoning = "LLM unavailable, using deterministic fallback."
        return _deterministic_fallback(candidates)


def _candidate_brief(item: dict) -> dict:
    return {
        "id": item["id"],
        "name": item["name"],
        "rating": item.get("rating", 0),
        "tags": item.get("tags", []),
        "distance_km": item.get("distance_km", 0),
        "avg_price": item.get("avg_price", 0),
        "wait_minutes": item.get("wait_minutes", 0),
        "open_hours": item.get("open_hours", []),
        "risk_tags": item.get("risk_tags", []),
        "booking_supported": item.get("booking_supported", False),
        "duration_minutes": item.get("duration_minutes", 0),
        "reason": item.get("reason", ""),
        "review_count": item.get("review_count", 0),
        "source": item.get("source", ""),
    }


def _merge_ranked_with_candidates(ranked: dict[str, list[dict]], candidates: dict[str, list[dict]]) -> dict[str, list[dict]]:
    candidate_lookup: dict[str, dict] = {}
    for items in candidates.values():
        for item in items:
            candidate_lookup[item["id"]] = item

    result: dict[str, list[dict]] = {}
    for category in ("activities", "restaurants", "walks"):
        llm_selections = ranked.get(category, [])
        merged = []
        seen_ids: set[str] = set()
        for sel in llm_selections:
            sid = str(sel.get("id", ""))
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            full = candidate_lookup.get(sid, None)
            if full is not None:
                enriched = dict(full)
                enriched["llm_reason"] = sel.get("reason", "")
                merged.append(enriched)
        if not merged:
            # LLM returned IDs not in catalog; fall back to top candidates
            fallback_items = candidates.get(category, [])
            sorted_fallback = sorted(
                fallback_items,
                key=lambda x: (-float(x.get("rating", 0)), float(x.get("distance_km", 99))),
            )
            merged = sorted_fallback[:3]
        result[category] = merged
    return result


def _deterministic_fallback(candidates: dict[str, list[dict]]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for category, items in candidates.items():
        sorted_items = sorted(items, key=lambda x: (-float(x.get("rating", 0)), float(x.get("distance_km", 99))))
        result[category] = sorted_items[:3]
    return result
