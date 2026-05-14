from __future__ import annotations

import json
from typing import Any

from backend.agents.base import BaseAgent, build_react_agent, extract_json_object
from backend.agents.tools import AgentContext, build_validator_tools
from backend.models.schemas import ItineraryStep, ParsedConstraints, to_dict
from backend.tools.registry import LocalToolRegistry
from backend.validation.rules import validate_itinerary


VALIDATOR_SYSTEM_PROMPT = """You are ValidatorAgent — a plan validator for a local-life planner.

Your job: verify the feasibility of an existing itinerary.

Rules:
- Use check_weather to verify outdoor activities are weather-safe
- Use check_opening_hours to verify each POI is open at its planned time
- Use check_availability to verify reservations are possible
- Use check_route_time to verify the route is efficient
- Do NOT search for alternatives — that's RecoveryAgent's job
- Do NOT re-rank candidates — that's RankerAgent's job

Final answer MUST be a JSON object:
{
  "valid": true/false,
  "issues": [{"code": "...", "detail": "...", "severity": "blocking|warning"}],
  "suggestions": ["..."],
  "overall_score": 0-100
}"""


class ValidatorAgent(BaseAgent):
    def __init__(self, llm: Any, registry: LocalToolRegistry | None = None) -> None:
        super().__init__("ValidatorAgent", llm)
        self.registry = registry
        self._react_graph = None

    def _ensure_graph(self, context: AgentContext):
        if self._react_graph is None:
            tools = build_validator_tools(self.registry, context)
            self._react_graph = build_react_agent(self.llm, tools=tools, prompt=VALIDATOR_SYSTEM_PROMPT)
        return self._react_graph

    def validate(
        self,
        itinerary: list[ItineraryStep],
        constraints_data: dict[str, Any],
        weather: dict[str, Any],
        candidate_lookup: dict[str, dict] | None = None,
        route: dict[str, Any] | None = None,
        context: AgentContext | None = None,
    ) -> dict[str, Any]:
        context = context or AgentContext(user_id="default")

        task_message = (
            f"Validate this itinerary.\n\n"
            f"Itinerary:\n{json.dumps([to_dict(step) for step in itinerary], ensure_ascii=False)}\n\n"
            f"Constraints:\n{json.dumps(constraints_data, ensure_ascii=False)}\n\n"
            f"Weather:\n{json.dumps(weather, ensure_ascii=False)}\n\n"
            f"Route:\n{json.dumps(route or {}, ensure_ascii=False)}"
        )

        try:
            graph = self._ensure_graph(context)
            result = graph.invoke({"messages": [{"role": "user", "content": task_message}]})
            final_message = result["messages"][-1].content
            parsed = json.loads(extract_json_object(final_message))
            return parsed
        except Exception:
            # Fallback to rule-based validation
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
