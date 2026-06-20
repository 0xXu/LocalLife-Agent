"""Authentication compatibility endpoints."""

from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import ServiceContainer, get_current_user_id, get_services
from app.application.auth import DuplicateUserError, InvalidCredentialsError


router = APIRouter()


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    password: str
    city: str | None = None
    personaId: str | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    password: str


def _auth_payload(result: object) -> dict[str, object]:
    return {
        "success": True,
        "userId": result.user_id,  # type: ignore[attr-defined]
        "name": result.name,  # type: ignore[attr-defined]
        "token": result.token,  # type: ignore[attr-defined]
    }


@router.post("/register")
async def register(
    request: RegisterRequest, services: ServiceContainer = Depends(get_services)
) -> object:
    try:
        return _auth_payload(await services.auth.register(request.name, request.password))
    except DuplicateUserError as error:
        return JSONResponse(status_code=409, content={"success": False, "error": str(error)})


@router.post("/login")
async def login(
    request: LoginRequest, services: ServiceContainer = Depends(get_services)
) -> object:
    try:
        return _auth_payload(await services.auth.login(request.name, request.password))
    except InvalidCredentialsError as error:
        return JSONResponse(status_code=401, content={"success": False, "error": str(error)})


@router.get("/me")
async def me(
    user_id: str = Depends(get_current_user_id),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, object]:
    return await services.auth.user_info(user_id)


@router.get("/models")
async def models() -> list[dict[str, str]]:
    return [{"id": "openai", "name": "OpenAI", "region": "global"}]
