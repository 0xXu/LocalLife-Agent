"""JWT-scoped favorite route endpoints."""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import ServiceContainer, get_current_user_id, get_services
from app.application.favorites import Favorite


router = APIRouter()


class SaveFavoriteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    user_id: str | None = Field(default=None, alias="userId")
    route_json: str = Field(alias="routeJson")
    route_name: str | None = Field(default=None, alias="routeName")
    scene: str | None = None
    poi_count: int | None = Field(default=None, alias="poiCount")
    total_time: str | None = Field(default=None, alias="totalTime")
    total_cost: int | None = Field(default=None, alias="totalCost")


def _payload(favorite: Favorite) -> dict[str, Any]:
    value = asdict(favorite)
    return {
        "id": value["id"],
        "userId": value["user_id"],
        "routeJson": value["route_json"],
        "routeName": value["route_name"],
        "scene": value["scene"],
        "poiCount": value["poi_count"],
        "totalTime": value["total_time"],
        "totalCost": value["total_cost"],
        "createdAt": value["created_at"].isoformat() if value["created_at"] else None,
    }


@router.post("")
async def save(
    request: SaveFavoriteRequest,
    user_id: str = Depends(get_current_user_id),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    saved = await services.favorites.save(
        Favorite(
            id=None,
            user_id=user_id,
            route_json=request.route_json,
            route_name=request.route_name,
            scene=request.scene,
            poi_count=request.poi_count or 0,
            total_time=request.total_time,
            total_cost=request.total_cost or 0,
        )
    )
    return _payload(saved)


@router.get("")
async def list_favorites(
    _: str = Depends(get_current_user_id),
    services: ServiceContainer = Depends(get_services),
    user_id: str = Depends(get_current_user_id),
) -> list[dict[str, Any]]:
    return [_payload(item) for item in await services.list_favorites(user_id)]


@router.delete("/{favorite_id}")
async def delete(
    favorite_id: int,
    user_id: str = Depends(get_current_user_id),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    try:
        await services.favorites.delete(user_id, favorite_id)
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return {"success": True, "id": favorite_id}
