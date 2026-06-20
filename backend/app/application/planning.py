"""Application orchestration for deterministic route planning."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from app.domain.constraints import ConstraintEngine
from app.domain.models import POI, PlanResponse, Route, UserIntent, UserPreference
from app.domain.solver import GraphSearchSolver
from app.infrastructure.data_sources import DataSource
from app.infrastructure.entities import RouteEntity, SessionEntity


class SessionStore(Protocol):
    async def get(self, session_id: str, user_id: str) -> SessionEntity | None: ...

    async def save(self, user_id: str, session: SessionEntity) -> SessionEntity: ...


class PreferenceService(Protocol):
    async def get(self, user_id: str) -> object | None: ...


class PlanningService:
    """Keeps POI discovery, feasibility checks, and optional persistence explicit."""

    def __init__(
        self,
        data_source: DataSource,
        constraint_engine: ConstraintEngine,
        solver: GraphSearchSolver,
        session_repository: SessionStore | None = None,
        preference_service: PreferenceService | None = None,
    ) -> None:
        self._data_source = data_source
        self._constraint_engine = constraint_engine
        self._solver = solver
        self._sessions = session_repository
        self._preferences = preference_service

    async def plan(
        self,
        query: str,
        city: str,
        user_id: str | None,
        session_id: str | None = None,
        intent: UserIntent | None = None,
    ) -> PlanResponse:
        planning_intent = self._build_intent(query, city, intent)
        candidates = await self._discover_candidates(planning_intent)
        if not candidates:
            return PlanResponse(warning="未找到符合条件的地点，请调整条件后重试。", sessionId=session_id)

        constraints = self._constraint_engine.build_constraints(planning_intent)
        preference = await self._load_preference(user_id)
        proposed_routes = self._solver.generate_plans(
            candidates, constraints, planning_intent, preference=preference
        )
        routes = [
            route
            for route in proposed_routes
            if not self._constraint_engine.validate(route, constraints).has_hard_violations
        ]
        if not routes:
            return PlanResponse(warning="暂无可行路线，请调整条件后重试。", sessionId=session_id)

        persisted_session_id = await self._persist(
            user_id, session_id, planning_intent, routes
        )
        response_session_id = persisted_session_id or session_id
        return PlanResponse(
            routes=routes,
            recommendedRoute=routes[0],
            explanation="路线已按硬约束校验并按偏好评分排序。",
            sessionId=response_session_id,
        )

    async def adjust(
        self,
        adjustment: str,
        city: str,
        user_id: str | None,
        session_id: str,
        intent: UserIntent | None = None,
    ) -> PlanResponse:
        """Replan using a saved intent when a caller supplies a session context."""

        original_intent = intent or await self._load_session_intent(session_id, user_id)
        query = adjustment or (original_intent.query if original_intent else "调整路线")
        return await self.plan(
            query=query,
            city=city,
            user_id=user_id,
            session_id=session_id,
            intent=original_intent,
        )

    @staticmethod
    def _build_intent(query: str, city: str, intent: UserIntent | None) -> UserIntent:
        if intent is None:
            return UserIntent(query=query, city=city)
        return intent.model_copy(update={"query": query, "city": city})

    async def _discover_candidates(self, intent: UserIntent) -> list[POI]:
        categories = intent.preferred_categories or ["RESTAURANT", "ATTRACTION"]
        discovered: dict[str, POI] = {}
        for category in categories:
            async for poi in self._data_source.search_by_category(
                intent.city, intent.district, category
            ):
                discovered[poi.id] = poi
        return list(discovered.values())

    async def _load_preference(self, user_id: str | None) -> UserPreference | None:
        if user_id is None or self._preferences is None:
            return None
        profile = await self._preferences.get(user_id)
        if isinstance(profile, UserPreference):
            return profile
        raw_tags = getattr(profile, "preference_tags", None)
        if isinstance(raw_tags, str):
            try:
                tags = json.loads(raw_tags)
            except json.JSONDecodeError:
                return None
            if isinstance(tags, dict) and all(isinstance(value, (int, float)) for value in tags.values()):
                return UserPreference(tags={str(key): float(value) for key, value in tags.items()})
        return None

    async def _load_session_intent(
        self, session_id: str, user_id: str | None
    ) -> UserIntent | None:
        if self._sessions is None or user_id is None:
            return None
        session = await self._sessions.get(session_id, user_id)
        if session is None or not session.intent_json:
            return None
        try:
            return UserIntent.model_validate_json(session.intent_json)
        except ValueError:
            return None

    async def _persist(
        self,
        user_id: str | None,
        session_id: str | None,
        intent: UserIntent,
        routes: Sequence[Route],
    ) -> str | None:
        if self._sessions is None or user_id is None:
            return None
        persisted_session_id = session_id or f"session-{uuid4().hex[:24]}"
        now = datetime.now(UTC)
        await self._sessions.save(
            user_id,
            SessionEntity(
                id=persisted_session_id,
                user_id=user_id,
                intent_json=intent.model_dump_json(by_alias=True),
                created_at=now,
                updated_at=now,
            ),
        )
        save_route = getattr(self._sessions, "save_route", None)
        if callable(save_route):
            for route in routes:
                await save_route(user_id, self._route_entity(route, persisted_session_id, user_id))
        return persisted_session_id

    @staticmethod
    def _route_entity(route: Route, session_id: str, user_id: str) -> RouteEntity:
        return RouteEntity(
            id=route.id,
            session_id=session_id,
            user_id=user_id,
            name=route.name,
            description=None,
            segments_json=json.dumps(route.model_dump(by_alias=True), ensure_ascii=False),
            total_cost=route.total_cost,
            total_travel_time=sum(
                segment.travel_time_from_previous for segment in route.segments
            ),
            total_rating=sum(segment.poi.rating for segment in route.segments),
            optimization_goal="balanced",
            score=route.score,
            created_at=datetime.now(UTC),
        )
