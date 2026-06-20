"""Favorite-route use cases with explicit per-user ownership checks."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Self


@dataclass(slots=True)
class Favorite:
    id: int | None
    user_id: str
    route_json: str
    route_name: str | None = None
    scene: str | None = None
    poi_count: int | None = None
    total_time: str | None = None
    total_cost: int | None = None
    created_at: datetime | None = None


class FavoriteStore(Protocol):
    async def save(self, favorite: Favorite) -> Favorite: ...

    async def get(self, user_id: str, favorite_id: int) -> Favorite | None: ...

    async def exists_for_another_user(self, user_id: str, favorite_id: int) -> bool: ...

    async def delete(self, user_id: str, favorite_id: int) -> bool: ...


class FavoritesService:
    def __init__(self, favorites: FavoriteStore) -> None:
        self._favorites = favorites

    async def save(self, favorite: Favorite) -> Favorite:
        saved = await self._favorites.save(favorite)
        await self.learn_from_favorite(saved)
        return saved

    async def delete(self, user_id: str, favorite_id: int) -> None:
        """Delete an owned favorite, preserving absent vs. foreign error semantics."""
        if await self._favorites.get(user_id, favorite_id) is None:
            if await self._favorites.exists_for_another_user(user_id, favorite_id):
                raise PermissionError("favorite belongs to another user")
            raise LookupError("favorite does not exist")
        if not await self._favorites.delete(user_id, favorite_id):
            raise LookupError("favorite does not exist")

    async def learn_from_favorite(self, favorite: Favorite) -> None:
        """Stable extension point for preference learning after a favorite is saved."""
        return None
