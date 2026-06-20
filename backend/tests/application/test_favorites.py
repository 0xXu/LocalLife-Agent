import asyncio
from dataclasses import dataclass

import pytest

from app.application.favorites import Favorite, FavoritesService


@dataclass
class FakeFavorites:
    items: dict[int, Favorite]

    async def save(self, favorite: Favorite) -> Favorite:
        self.items[favorite.id] = favorite
        return favorite

    async def get(self, user_id: str, favorite_id: int) -> Favorite | None:
        favorite = self.items.get(favorite_id)
        return favorite if favorite and favorite.user_id == user_id else None

    async def exists_for_another_user(self, user_id: str, favorite_id: int) -> bool:
        favorite = self.items.get(favorite_id)
        return favorite is not None and favorite.user_id != user_id

    async def delete(self, user_id: str, favorite_id: int) -> bool:
        favorite = await self.get(user_id, favorite_id)
        if favorite is None:
            return False
        del self.items[favorite_id]
        return True


def test_save_returns_persisted_favorite() -> None:
    async def scenario() -> None:
        favorite = Favorite(id=1, user_id="user-1", route_json="{}")
        service = FavoritesService(FakeFavorites({}))

        assert await service.save(favorite) == favorite

    asyncio.run(scenario())


def test_delete_foreign_favorite_raises_permission_error() -> None:
    async def scenario() -> None:
        favorite = Favorite(id=1, user_id="owner", route_json="{}")
        service = FavoritesService(FakeFavorites({1: favorite}))

        with pytest.raises(PermissionError):
            await service.delete("intruder", 1)

    asyncio.run(scenario())

