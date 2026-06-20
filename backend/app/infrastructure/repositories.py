"""Async PostgreSQL repositories with tenant-scoped access to user data."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.favorites import Favorite
from app.infrastructure.entities import (
    FavoriteEntity,
    RouteEntity,
    SessionEntity,
    SnapshotEntity,
    UserProfileEntity,
)


class UserProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> UserProfileEntity | None:
        return await self._session.scalar(
            select(UserProfileEntity).where(UserProfileEntity.user_id == user_id)
        )

    async def get_by_name(self, name: str) -> UserProfileEntity | None:
        return await self._session.scalar(
            select(UserProfileEntity).where(UserProfileEntity.name == name)
        )

    async def create(self, user: UserProfileEntity) -> UserProfileEntity:
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def update(self, user_id: str, **values: object) -> bool:
        allowed = {
            key: value
            for key, value in values.items()
            if key in UserProfileEntity.__table__.columns and key not in {"id", "user_id"}
        }
        if not allowed:
            return False
        result = await self._session.execute(
            update(UserProfileEntity)
            .where(UserProfileEntity.user_id == user_id)
            .values(**allowed)
        )
        await self._session.commit()
        return bool(result.rowcount)


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, session_id: str, user_id: str) -> SessionEntity | None:
        return await self._session.scalar(
            select(SessionEntity).where(
                SessionEntity.id == session_id,
                SessionEntity.user_id == user_id,
            )
        )

    async def save(self, user_id: str, session: SessionEntity) -> SessionEntity:
        session.user_id = user_id
        self._session.add(session)
        await self._session.commit()
        await self._session.refresh(session)
        return session

    async def update(self, session_id: str, user_id: str, **values: object) -> bool:
        allowed = {
            key: value
            for key, value in values.items()
            if key in {"intent_json", "updated_at"}
        }
        if not allowed:
            return False
        result = await self._session.execute(
            update(SessionEntity)
            .where(SessionEntity.id == session_id, SessionEntity.user_id == user_id)
            .values(**allowed)
        )
        await self._session.commit()
        return bool(result.rowcount)

    async def delete(self, session_id: str, user_id: str) -> bool:
        result = await self._session.execute(
            delete(SessionEntity).where(
                SessionEntity.id == session_id,
                SessionEntity.user_id == user_id,
            )
        )
        await self._session.commit()
        return bool(result.rowcount)


class RouteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, route_id: str, user_id: str) -> RouteEntity | None:
        return await self._session.scalar(
            select(RouteEntity).where(RouteEntity.id == route_id, RouteEntity.user_id == user_id)
        )

    async def list_for_session(self, session_id: str, user_id: str) -> Sequence[RouteEntity]:
        result = await self._session.scalars(
            select(RouteEntity).where(
                RouteEntity.session_id == session_id,
                RouteEntity.user_id == user_id,
            )
        )
        return result.all()

    async def save(self, user_id: str, route: RouteEntity) -> RouteEntity:
        route.user_id = user_id
        self._session.add(route)
        await self._session.commit()
        await self._session.refresh(route)
        return route

    async def update(self, route_id: str, user_id: str, **values: object) -> bool:
        allowed = {
            key: value
            for key, value in values.items()
            if key
            in {
                "name",
                "description",
                "segments_json",
                "total_cost",
                "total_travel_time",
                "total_rating",
                "optimization_goal",
                "score",
            }
        }
        if not allowed:
            return False
        result = await self._session.execute(
            update(RouteEntity)
            .where(RouteEntity.id == route_id, RouteEntity.user_id == user_id)
            .values(**allowed)
        )
        await self._session.commit()
        return bool(result.rowcount)

    async def delete(self, route_id: str, user_id: str) -> bool:
        result = await self._session.execute(
            delete(RouteEntity).where(RouteEntity.id == route_id, RouteEntity.user_id == user_id)
        )
        await self._session.commit()
        return bool(result.rowcount)


class SnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_session(self, session_id: str, user_id: str) -> Sequence[SnapshotEntity]:
        result = await self._session.scalars(
            select(SnapshotEntity)
            .join(SessionEntity, SessionEntity.id == SnapshotEntity.session_id)
            .where(SnapshotEntity.session_id == session_id, SessionEntity.user_id == user_id)
            .order_by(SnapshotEntity.version)
        )
        return result.all()

    async def latest(self, session_id: str, user_id: str) -> SnapshotEntity | None:
        return await self._session.scalar(
            select(SnapshotEntity)
            .join(SessionEntity, SessionEntity.id == SnapshotEntity.session_id)
            .where(SnapshotEntity.session_id == session_id, SessionEntity.user_id == user_id)
            .order_by(SnapshotEntity.version.desc())
            .limit(1)
        )

    async def save(self, user_id: str, snapshot: SnapshotEntity) -> SnapshotEntity:
        """Save only when the parent session belongs to the supplied user."""
        owns_session = await self._session.scalar(
            select(SessionEntity.id).where(
                SessionEntity.id == snapshot.session_id,
                SessionEntity.user_id == user_id,
            )
        )
        if owns_session is None:
            raise PermissionError("session does not belong to user")
        self._session.add(snapshot)
        await self._session.commit()
        await self._session.refresh(snapshot)
        return snapshot

    async def delete(self, snapshot_id: int, user_id: str) -> bool:
        result = await self._session.execute(
            delete(SnapshotEntity).where(
                SnapshotEntity.id == snapshot_id,
                SnapshotEntity.session_id.in_(
                    select(SessionEntity.id).where(SessionEntity.user_id == user_id)
                ),
            )
        )
        await self._session.commit()
        return bool(result.rowcount)


class FavoriteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str, favorite_id: int) -> Favorite | None:
        entity = await self._session.scalar(
            select(FavoriteEntity).where(
                FavoriteEntity.id == favorite_id,
                FavoriteEntity.user_id == user_id,
            )
        )
        return self._to_model(entity) if entity is not None else None

    async def list(self, user_id: str) -> Sequence[Favorite]:
        entities = await self._session.scalars(
            select(FavoriteEntity).where(FavoriteEntity.user_id == user_id)
        )
        return [self._to_model(entity) for entity in entities.all()]

    async def save(self, favorite: Favorite) -> Favorite:
        entity = FavoriteEntity(
            user_id=favorite.user_id,
            route_json=favorite.route_json,
            route_name=favorite.route_name,
            scene=favorite.scene,
            poi_count=favorite.poi_count,
            total_time=favorite.total_time,
            total_cost=favorite.total_cost,
            created_at=favorite.created_at,
        )
        if favorite.id is not None:
            entity.id = favorite.id
        self._session.add(entity)
        await self._session.commit()
        await self._session.refresh(entity)
        return self._to_model(entity)

    async def exists_for_another_user(self, user_id: str, favorite_id: int) -> bool:
        """Distinguish a foreign favorite without exposing it to the caller."""
        entity = await self._session.scalar(
            select(FavoriteEntity.id).where(
                FavoriteEntity.id == favorite_id,
                FavoriteEntity.user_id != user_id,
            )
        )
        return entity is not None

    async def delete(self, user_id: str, favorite_id: int) -> bool:
        result = await self._session.execute(
            delete(FavoriteEntity).where(
                FavoriteEntity.id == favorite_id,
                FavoriteEntity.user_id == user_id,
            )
        )
        await self._session.commit()
        return bool(result.rowcount)

    @staticmethod
    def _to_model(entity: FavoriteEntity) -> Favorite:
        return Favorite(
            id=entity.id,
            user_id=entity.user_id or "",
            route_json=entity.route_json,
            route_name=entity.route_name,
            scene=entity.scene,
            poi_count=entity.poi_count,
            total_time=entity.total_time,
            total_cost=entity.total_cost,
            created_at=entity.created_at,
        )
