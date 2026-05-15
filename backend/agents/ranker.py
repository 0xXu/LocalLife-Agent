from __future__ import annotations

import json
from typing import Any

from backend.agents.base import BaseAgent, build_react_agent, extract_json_object
from backend.agents.tools import AgentContext, build_ranker_tools
from backend.models.schemas import ParsedConstraints
from backend.tools.registry import LocalToolRegistry


RANKER_SYSTEM_PROMPT = """You are RankerAgent — a local-life planning ranker.

Your job: discover and rank candidate POIs for activities, restaurants, and walks.

Rules:
- Use search_places to find candidates if needed
- Use get_poi_details to check promising candidates before ranking
- Use check_availability only for top candidates (not all)
- Use compare_pois when you need to decide between close options
- Do NOT validate full itinerary feasibility — that's ValidatorAgent's job
- Do NOT search for alternatives to failed plans — that's RecoveryAgent's job

Final answer MUST be a JSON object:
{
  "ranked": {
    "activities": [{"id": "poi_xxx", "reason": "..."}],
    "restaurants": [{"id": "poi_yyy", "reason": "..."}],
    "walks": [{"id": "poi_zzz", "reason": "..."}]
  },
  "reasoning": "..."
}
Select 1-3 items per category. Prefer items matching user tags, closer distance, lower wait time."""


class RankerAgent(BaseAgent):
    def __init__(self, llm: Any, registry: LocalToolRegistry | None = None, memory_store=None) -> None:
        super().__init__("RankerAgent", llm)
        self.registry = registry
        self.memory_store = memory_store
        self.last_reasoning: str = ""
        self._react_graph = None

    def _ensure_graph(self, context: AgentContext):
        if self._react_graph is None:
            tools = build_ranker_tools(self.registry, context)
            self._react_graph = build_react_agent(self.llm, tools=tools, prompt=RANKER_SYSTEM_PROMPT)
        return self._react_graph

    def rank(self, candidates: dict[str, list[dict]], constraints: ParsedConstraints, context: AgentContext | None = None) -> dict[str, list[dict]]:
        context = context or AgentContext(user_id="default")

        # Build task message with candidates and constraints
        memory_context = ""
        if self.memory_store:
            memory_context = f"\n\nUser memory:\n{self.memory_store.build_context_message(context.user_id)}"

        task_message = (
            f"Rank these candidates for the user.\n\n"
            f"Scenario: {constraints.scenario}\n"
            f"Activity tags: {constraints.preferences.get('activity', [])}\n"
            f"Diet tags: {constraints.preferences.get('diet', [])}\n"
            f"Budget: {constraints.preferences.get('budget_level', 'medium')}\n"
            f"Radius: {constraints.constraints.get('radius_km', 8)}km\n"
            f"People: {constraints.people}\n\n"
            f"Candidates:\n{json.dumps({k: [{'id': i['id'], 'name': i['name'], 'rating': i.get('rating',0), 'tags': i.get('tags',[]), 'distance_km': i.get('distance_km',0)} for i in v[:8]] for k, v in candidates.items()}, ensure_ascii=False)}"
            f"{memory_context}"
        )

        try:
            graph = self._ensure_graph(context)
            result = graph.invoke({"messages": [{"role": "user", "content": task_message}]})
            final_message = result["messages"][-1].content
            parsed = json.loads(extract_json_object(final_message))
            self.last_reasoning = parsed.get("reasoning", "")
            return _merge_ranked_with_candidates(parsed.get("ranked", {}), candidates)
        except Exception:
            self.last_reasoning = "ReAct agent failed, using deterministic fallback."
            return _deterministic_fallback(candidates)



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
