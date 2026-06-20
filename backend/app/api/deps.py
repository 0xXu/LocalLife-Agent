"""Application-owned service wiring and request dependencies.

The container is attached to each FastAPI application instance.  This keeps
test doubles isolated and avoids a process-wide mutable service singleton.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from typing import Any, Protocol

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.auth import AuthService
from app.application.favorites import Favorite, FavoriteStore, FavoritesService
from app.application.planning import PlanningService, SessionStore
from app.domain.constraints import ConstraintEngine
from app.domain.models import Route
from app.domain.solver import GraphSearchSolver
from app.infrastructure.data_sources import DataSource, MockDataSource
from app.infrastructure.entities import RouteEntity, SessionEntity, UserProfileEntity
from app.security.jwt import AuthenticationError, decode_access_token
from app.settings import Settings


class FavoriteLister(FavoriteStore, Protocol):
    async def list(self, user_id: str) -> Sequence[Favorite]: ...


@dataclass(slots=True)
class ServiceContainer:
    """Services used by request handlers, supplied per application instance."""

    auth: AuthService
    planning: PlanningService
    favorites: FavoritesService
    data_source: DataSource
    sessions: SessionStore
    favorite_store: FavoriteLister
    profiles: list[dict[str, Any]]
    agent_runner: Any | None = None

    async def list_favorites(self, user_id: str) -> Sequence[Favorite]:
        return await self.favorite_store.list(user_id)

    async def routes_for_session(self, session_id: str, user_id: str) -> list[Route]:
        routes_for_session = getattr(self.sessions, "routes_for_session", None)
        if callable(routes_for_session):
            return await routes_for_session(session_id, user_id)
        return []


class InMemoryUserStore:
    def __init__(self) -> None:
        self._users: dict[str, UserProfileEntity] = {}
        self._ids = count(1)

    async def get_by_name(self, name: str) -> UserProfileEntity | None:
        return self._users.get(name)

    async def get_by_user_id(self, user_id: str) -> UserProfileEntity | None:
        return next((user for user in self._users.values() if user.user_id == user_id), None)

    async def create(self, user: UserProfileEntity) -> UserProfileEntity:
        user.id = next(self._ids)
        self._users[user.name] = user
        return user


class InMemorySessionStore:
    def __init__(self) -> None:
        self.items: dict[str, SessionEntity] = {}
        self._routes: dict[str, list[Route]] = {}

    async def get(self, session_id: str, user_id: str) -> SessionEntity | None:
        session = self.items.get(session_id)
        return session if session is not None and session.user_id == user_id else None

    async def save(self, user_id: str, session: SessionEntity) -> SessionEntity:
        session.user_id = user_id
        self.items[session.id] = session
        return session

    async def save_route(self, user_id: str, route: RouteEntity) -> RouteEntity:
        if await self.get(route.session_id, user_id) is None:
            raise PermissionError("session does not belong to user")
        # The planning response has already been validated.  Keeping the JSON
        # persistence form here also mirrors the PostgreSQL repository contract.
        self._routes.setdefault(route.session_id, []).append(
            Route.model_validate_json(route.segments_json)
        )
        return route

    async def routes_for_session(self, session_id: str, user_id: str) -> list[Route]:
        if await self.get(session_id, user_id) is None:
            return []
        return list(self._routes.get(session_id, []))


class InMemoryFavoriteStore:
    def __init__(self) -> None:
        self._items: dict[int, Favorite] = {}
        self._ids = count(1)

    async def save(self, favorite: Favorite) -> Favorite:
        favorite_id = favorite.id if favorite.id is not None else next(self._ids)
        saved = Favorite(
            id=favorite_id,
            user_id=favorite.user_id,
            route_json=favorite.route_json,
            route_name=favorite.route_name,
            scene=favorite.scene,
            poi_count=favorite.poi_count,
            total_time=favorite.total_time,
            total_cost=favorite.total_cost,
            created_at=favorite.created_at or datetime.now(UTC),
        )
        self._items[favorite_id] = saved
        return saved

    async def get(self, user_id: str, favorite_id: int) -> Favorite | None:
        favorite = self._items.get(favorite_id)
        return favorite if favorite is not None and favorite.user_id == user_id else None

    async def list(self, user_id: str) -> Sequence[Favorite]:
        return sorted(
            (item for item in self._items.values() if item.user_id == user_id),
            key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

    async def exists_for_another_user(self, user_id: str, favorite_id: int) -> bool:
        favorite = self._items.get(favorite_id)
        return favorite is not None and favorite.user_id != user_id

    async def delete(self, user_id: str, favorite_id: int) -> bool:
        if await self.get(user_id, favorite_id) is None:
            return False
        del self._items[favorite_id]
        return True


def build_in_memory_services(*, jwt_secret: str) -> ServiceContainer:
    """Build deterministic local/test services without database or OpenAI calls."""
    data_source = MockDataSource()
    engine = ConstraintEngine()
    sessions = InMemorySessionStore()
    favorites = InMemoryFavoriteStore()
    return ServiceContainer(
        auth=AuthService(InMemoryUserStore(), jwt_secret=jwt_secret),
        planning=PlanningService(
            data_source,
            engine,
            GraphSearchSolver(engine),
            session_repository=sessions,
        ),
        favorites=FavoritesService(favorites),
        data_source=data_source,
        sessions=sessions,
        favorite_store=favorites,
        profiles=[],
    )


def build_services(settings: Settings | None = None) -> ServiceContainer:
    """Construct the default local runtime container.

    Database-backed wiring is introduced by the persistence phase; using the
    deterministic data source here makes an unconfigured development server
    safe to start and keeps all request behavior explicit.
    """
    runtime = settings or Settings()
    secret = runtime.jwt_secret or "local-development-secret-not-for-production"
    return build_in_memory_services(jwt_secret=secret)


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


_bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    services: ServiceContainer = Depends(get_services),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return decode_access_token(credentials.credentials, services.auth._jwt_secret)
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
