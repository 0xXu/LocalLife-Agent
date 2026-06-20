"""Read-only, typed tool boundaries for the route-planning agent."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, TypeAlias

from agents import FunctionTool, function_tool
from pydantic import BaseModel

from app.application.planning import PlanningService
from app.application.profiles import ProfileService
from app.domain.constraints import ConstraintEngine, ValidationResult
from app.domain.models import Constraint, PlanResponse, Route, UserIntent

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
ParseIntentTool: TypeAlias = Callable[[str, str], Awaitable[JsonObject]]
SearchPoisTool: TypeAlias = Callable[[str, str, list[str]], Awaitable[list[JsonObject]]]
GetProfileTool: TypeAlias = Callable[[str], Awaitable[JsonObject]]
GenerateRoutesTool: TypeAlias = Callable[[str, str, JsonObject | None], Awaitable[JsonObject]]
CheckConstraintsTool: TypeAlias = Callable[[JsonObject, JsonObject], Awaitable[JsonObject]]
ScoreAndRankTool: TypeAlias = Callable[[JsonObject, JsonObject], Awaitable[JsonObject]]
ExplainRoutesTool: TypeAlias = Callable[[JsonObject], Awaitable[JsonObject]]


@dataclass(frozen=True, slots=True)
class RouteTools:
    """Local callables plus their SDK wrappers.

    Tests and non-LLM callers use the typed local callables.  The agent only
    receives ``sdk_tools``, which makes the same boundaries available to the
    OpenAI Agents SDK without coupling business logic to SDK input JSON.
    """

    parse_intent: ParseIntentTool
    search_pois: SearchPoisTool
    get_user_profile: GetProfileTool
    generate_routes: GenerateRoutesTool
    check_constraints: CheckConstraintsTool
    score_and_rank: ScoreAndRankTool
    explain_routes: ExplainRoutesTool
    sdk_tools: tuple[FunctionTool, ...]


class FinalRouteValidator:
    """Reject candidate route bundles which fail deterministic hard constraints."""

    def __init__(self, constraint_engine: ConstraintEngine) -> None:
        self._constraint_engine = constraint_engine

    def finalize(
        self,
        bundle: PlanResponse | Mapping[str, Any] | Sequence[Route],
        intent_or_constraints: UserIntent | Sequence[Constraint],
    ) -> PlanResponse:
        response = self._response_from_bundle(bundle)
        constraints = (
            self._constraint_engine.build_constraints(intent_or_constraints)
            if isinstance(intent_or_constraints, UserIntent)
            else list(intent_or_constraints)
        )
        hard_violations = [
            violation
            for route in response.routes
            for violation in self._constraint_engine.validate(route, constraints).hard_violations
        ]
        if hard_violations:
            ids = ", ".join(sorted({violation.id for violation in hard_violations}))
            raise ValueError(f"Route bundle failed hard constraint validation: {ids}")
        return response

    @staticmethod
    def _response_from_bundle(
        bundle: PlanResponse | Mapping[str, Any] | Sequence[Route],
    ) -> PlanResponse:
        if isinstance(bundle, PlanResponse):
            return bundle
        if isinstance(bundle, Mapping):
            return PlanResponse.model_validate(bundle)
        return PlanResponse(routes=list(bundle))


def build_route_tools(
    planning_service: PlanningService,
    profile_service: ProfileService | None = None,
) -> RouteTools:
    """Build read-only functions for one route-planning agent.

    Functions only query data, compute candidates, or validate model output.
    In particular ``generate_routes`` always passes ``None`` for user and
    session IDs, so it cannot create sessions or route records through
    ``PlanningService``.
    """

    constraint_engine = _constraint_engine_for(planning_service)
    final_validator = FinalRouteValidator(constraint_engine)

    async def parse_intent(query: str, city: str) -> dict[str, Any]:
        """Create a validated planning intent from a user query and city."""

        return _json_object(UserIntent(query=query, city=city))

    async def search_pois(
        query: str, city: str, categories: list[str]
    ) -> list[dict[str, Any]]:
        """Search the configured POI source using validated city and categories."""

        intent = UserIntent(
            query=query,
            city=city,
            preferredCategories=categories,
        )
        discover = getattr(planning_service, "_discover_candidates", None)
        if not callable(discover):
            return []
        return [_json_object(poi) for poi in await discover(intent)]

    async def get_user_profile(user_id: str) -> dict[str, Any]:
        """Fetch a sanitized user preference profile when profile access is configured."""

        if profile_service is None:
            return {}
        profile = await profile_service.get(user_id)
        return _json_object(profile) if profile is not None else {}

    async def generate_routes(
        query: str, city: str, intent: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Generate hard-validated routes without writing a session or route record."""

        validated_intent = _validated_intent(query, city, intent)
        response = await planning_service.plan(
            query=validated_intent.query,
            city=validated_intent.city,
            user_id=None,
            session_id=None,
            intent=validated_intent,
        )
        final_validator.finalize(response, validated_intent)
        return _json_object(response)

    async def check_constraints(
        route_bundle: dict[str, Any], intent: dict[str, Any]
    ) -> dict[str, Any]:
        """Run deterministic constraint validation against supplied candidate routes."""

        response = PlanResponse.model_validate(route_bundle)
        validated_intent = _validated_intent(
            str(intent.get("query", "路线")), str(intent.get("city", "北京")), intent
        )
        constraints = constraint_engine.build_constraints(validated_intent)
        results = [constraint_engine.validate(route, constraints) for route in response.routes]
        return {
            "valid": not any(result.has_hard_violations for result in results),
            "results": [_json_object(result) for result in results],
        }

    async def score_and_rank(
        route_bundle: dict[str, Any], intent: dict[str, Any]
    ) -> dict[str, Any]:
        """Score and rank routes using deterministic constraints only."""

        response = PlanResponse.model_validate(route_bundle)
        validated_intent = _validated_intent(
            str(intent.get("query", "路线")), str(intent.get("city", "北京")), intent
        )
        constraints = constraint_engine.build_constraints(validated_intent)
        ranked = sorted(
            (
                route.model_copy(update={"score": constraint_engine.score_route(route, constraints)})
                for route in response.routes
            ),
            key=lambda route: route.score,
            reverse=True,
        )
        ranked_response = response.model_copy(
            update={"routes": ranked, "recommendedRoute": ranked[0] if ranked else None}
        )
        final_validator.finalize(ranked_response, constraints)
        return _json_object(ranked_response)

    async def explain_routes(route_bundle: dict[str, Any]) -> dict[str, Any]:
        """Return a factual explanation derived solely from candidate route fields."""

        response = PlanResponse.model_validate(route_bundle)
        if not response.routes:
            return {"explanation": response.warning or "No feasible routes were generated."}
        best = response.recommendedRoute or response.routes[0]
        return {
            "explanation": (
                f"{best.name} contains {len(best.segments)} stops, costs {best.total_cost:g}, "
                f"and has deterministic score {best.score:g}."
            )
        }

    return RouteTools(
        parse_intent=parse_intent,
        search_pois=search_pois,
        get_user_profile=get_user_profile,
        generate_routes=generate_routes,
        check_constraints=check_constraints,
        score_and_rank=score_and_rank,
        explain_routes=explain_routes,
        sdk_tools=(
            # Route bundle payloads are dynamic JSON objects at this boundary;
            # the local functions immediately validate them with Pydantic.
            # The installed SDK rejects such ``dict[str, Any]`` parameters in
            # strict-schema mode, so these wrappers intentionally use its
            # supported permissive mode while retaining typed local callables.
            function_tool(parse_intent, strict_mode=False),
            function_tool(search_pois, strict_mode=False),
            function_tool(get_user_profile, strict_mode=False),
            function_tool(generate_routes, strict_mode=False),
            function_tool(check_constraints, strict_mode=False),
            function_tool(score_and_rank, strict_mode=False),
            function_tool(explain_routes, strict_mode=False),
        ),
    )


def _constraint_engine_for(planning_service: PlanningService) -> ConstraintEngine:
    engine = getattr(planning_service, "_constraint_engine", None)
    if not isinstance(engine, ConstraintEngine):
        raise TypeError("planning_service must expose a ConstraintEngine")
    return engine


def _validated_intent(query: str, city: str, raw_intent: JsonObject | None) -> UserIntent:
    candidate = dict(raw_intent or {})
    candidate.update({"query": query, "city": city})
    return UserIntent.model_validate(candidate)


def _json_object(value: object) -> JsonObject:
    serialized = _safe_json(value)
    if not isinstance(serialized, dict):
        raise TypeError("Tool result must serialize to a JSON object")
    return serialized


def _safe_json(value: object) -> JsonValue:
    if isinstance(value, BaseModel):
        value = value.model_dump(by_alias=True)
    elif is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)

    if isinstance(value, Mapping):
        return {
            str(key): _safe_json(item)
            for key, item in value.items()
            if not _is_sensitive_key(str(key))
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe_json(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "__dict__"):
        return _safe_json(vars(value))
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(
        fragment in normalized
        for fragment in ("database", "password", "secret", "token", "api_key", "url")
    )
