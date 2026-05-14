from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent


class RecoveryAgent(BaseAgent):
    def __init__(self, llm: Any) -> None:
        super().__init__("RecoveryAgent", llm)

    def recover(
        self,
        issues: list[dict[str, Any]],
        itinerary_summary: list[dict[str, Any]],
        alternatives: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        system_prompt = (
            "You are a plan recovery agent. The validator found issues with the itinerary. "
            "Decide how to fix it. Options:\n"
            "- 'replace': swap a problematic node with an alternative\n"
            "- 'adjust': keep the plan but modify timing/budget/optional components\n"
            "- 'replan': the plan is too broken, needs full re-ranking\n"
            "Return JSON: {\"action\": \"replace|adjust|replan\", \"target_type\": \"activity|restaurant|walk\", "
            "\"target_id\": \"...\", \"replacement_id\": \"...\", \"adjustment\": \"...\", \"reason\": \"...\"}"
        )
        context = {
            "issues": issues,
            "itinerary": itinerary_summary,
            "alternatives": {k: [{"id": item["id"], "name": item.get("name", "")} for item in v] for k, v in alternatives.items()},
        }

        result = self.run_llm(system_prompt, context)
        if result and "action" in result:
            return result

        # Fallback: simple heuristic recovery
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
