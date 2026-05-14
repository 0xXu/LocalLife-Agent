from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.models.schemas import ItineraryStep, ParsedConstraints, to_dict
from backend.validation.rules import validate_itinerary


class ValidatorAgent(BaseAgent):
    def __init__(self, llm: Any) -> None:
        super().__init__("ValidatorAgent", llm)

    def validate(
        self,
        itinerary: list[ItineraryStep],
        constraints_data: dict[str, Any],
        weather: dict[str, Any],
        candidate_lookup: dict[str, dict] | None = None,
        route: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        system_prompt = (
            "You are a plan validator for a local-life planner. Evaluate the itinerary holistically. "
            "Check: 1) Do activities match the scenario? 2) Are times reasonable? 3) Is budget appropriate? "
            "4) Does weather conflict with outdoor activities? 5) Is the route efficient? "
            "Return JSON: {\"valid\": bool, \"issues\": [{\"code\": \"...\", \"detail\": \"...\", \"severity\": \"blocking|warning\"}], "
            "\"suggestions\": [\"...\"], \"overall_score\": int(0-100)}"
        )
        context = {
            "itinerary": [to_dict(step) for step in itinerary],
            "constraints": constraints_data,
            "weather": weather,
        }

        result = self.run_llm(system_prompt, context)
        if result and "valid" in result:
            return result

        # Fallback: rule-based validation
        return self._rule_based_fallback(itinerary, constraints_data, weather, candidate_lookup, route)

    def _rule_based_fallback(
        self,
        itinerary: list[ItineraryStep],
        constraints_data: dict[str, Any],
        weather: dict[str, Any],
        candidate_lookup: dict[str, dict] | None,
        route: dict[str, Any] | None,
    ) -> dict[str, Any]:
        constraints = ParsedConstraints(
            scenario=constraints_data.get("scenario", "family"),
            origin=constraints_data.get("origin", {}),
            time_window=constraints_data.get("time_window", {}),
            people=constraints_data.get("people", {}),
            preferences={"budget_level": constraints_data.get("budget_level", "medium")},
            constraints=constraints_data.get("constraints", {}),
            required_actions=constraints_data.get("required_actions", []),
        )
        report = validate_itinerary(itinerary, constraints, candidate_lookup or {}, weather, route or {})
        return {
            "valid": report.valid,
            "issues": [{"code": issue["code"], "detail": str(issue), "severity": "blocking"} for issue in report.issues],
            "suggestions": [],
            "overall_score": 85 if report.valid else 40,
        }
