from __future__ import annotations

import json
from typing import Any

from backend.agents.base import BaseAgent, build_react_agent, extract_json_object
from backend.agents.tools import AgentContext, build_recovery_tools
from backend.tools.registry import LocalToolRegistry


RECOVERY_SYSTEM_PROMPT = """You are RecoveryAgent — a plan recovery specialist.

Your job: find substitutes when the original plan fails validation.

Rules:
- Use search_alternatives to find replacement POIs (excluding the failed ones)
- Use check_availability to verify replacements are actually available
- Use compare_options to compare replacements against the original
- Use estimate_cost to check budget impact of replacements
- Do NOT re-rank the entire candidate pool — that's RankerAgent's job
- Do NOT validate the full plan — that's ValidatorAgent's job

Final answer MUST be a JSON object:
{
  "action": "replace|adjust|replan",
  "target_type": "activity|restaurant|walk",
  "target_id": "original_poi_id",
  "replacement_id": "new_poi_id",
  "adjustment": "description of adjustment",
  "reason": "why this recovery action"
}"""


class RecoveryAgent(BaseAgent):
    def __init__(self, llm: Any, registry: LocalToolRegistry | None = None) -> None:
        super().__init__("RecoveryAgent", llm)
        self.registry = registry
        self._react_graph = None

    def _ensure_graph(self, context: AgentContext):
        if self._react_graph is None:
            tools = build_recovery_tools(self.registry, context)
            self._react_graph = build_react_agent(self.llm, tools=tools, prompt=RECOVERY_SYSTEM_PROMPT)
        return self._react_graph

    def recover(
        self,
        issues: list[dict[str, Any]],
        itinerary_summary: list[dict[str, Any]],
        alternatives: dict[str, list[dict[str, Any]]],
        context: AgentContext | None = None,
    ) -> dict[str, Any]:
        context = context or AgentContext(user_id="default")

        task_message = (
            f"The validator found issues with this itinerary. Find a recovery plan.\n\n"
            f"Issues:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
            f"Current itinerary:\n{json.dumps(itinerary_summary, ensure_ascii=False)}\n\n"
            f"Available alternatives:\n{json.dumps({k: [{'id': i['id'], 'name': i.get('name','')} for i in v] for k, v in alternatives.items()}, ensure_ascii=False)}"
        )

        try:
            graph = self._ensure_graph(context)
            result = graph.invoke({"messages": [{"role": "user", "content": task_message}]})
            final_message = result["messages"][-1].content
            parsed = json.loads(extract_json_object(final_message))
            return parsed
        except Exception:
            return self._heuristic_fallback(issues, alternatives)

    def _heuristic_fallback(
        self,
        issues: list[dict[str, Any]],
        alternatives: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        blocking = [issue for issue in issues if issue.get("severity") == "blocking"]
        if not blocking:
            return {"action": "adjust", "reason": "No blocking issues, minor adjustments only."}

        first_issue = blocking[0]
        code = first_issue.get("code", "")

        if "restaurant" in code or "closed" in code:
            replacements = alternatives.get("restaurants", [])
            if replacements:
                return {
                    "action": "replace",
                    "target_type": "restaurant",
                    "replacement_id": replacements[0]["id"],
                    "reason": f"Heuristic: replacing restaurant due to {code}.",
                }

        if "weather" in code:
            replacements = alternatives.get("activities", [])
            indoor = [a for a in replacements if "indoor" in a.get("tags", [])]
            if indoor:
                return {
                    "action": "replace",
                    "target_type": "activity",
                    "replacement_id": indoor[0]["id"],
                    "reason": f"Heuristic: switching to indoor activity due to {code}.",
                }

        return {"action": "replan", "reason": f"Cannot heuristically recover from {code}, full replan needed."}
