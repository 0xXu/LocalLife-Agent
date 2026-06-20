"""Profile and session use cases with repository-provided tenant scoping."""

from typing import Protocol, TypeVar

from app.infrastructure.entities import SessionEntity, UserProfileEntity


class ProfileStore(Protocol):
    async def get_by_user_id(self, user_id: str) -> UserProfileEntity | None: ...

    async def update(self, user_id: str, **values: object) -> bool: ...


class ProfileService:
    def __init__(self, profiles: ProfileStore) -> None:
        self._profiles = profiles

    async def get(self, user_id: str) -> UserProfileEntity | None:
        return await self._profiles.get_by_user_id(user_id)

    async def update(self, user_id: str, **values: object) -> bool:
        return await self._profiles.update(user_id, **values)


SessionT = TypeVar("SessionT")


class SessionStore(Protocol[SessionT]):
    async def get(self, session_id: str, user_id: str) -> SessionT | None: ...


class SessionService:
    def __init__(self, sessions: SessionStore[SessionT]) -> None:
        self._sessions = sessions

    async def get(self, session_id: str, user_id: str) -> SessionT | None:
        """Return a session only when it is owned by the requested user."""
        return await self._sessions.get(session_id, user_id)
