"""Authentication compatibility endpoints."""

from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import ServiceContainer, get_services
from app.application.auth import DuplicateUserError, InvalidCredentialsError
from app.security.jwt import AuthenticationError, decode_access_token


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
        return _auth_payload(await services.auth.register(request.name, request.password, request.city))
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
    request: Request,
    services: ServiceContainer = Depends(get_services),
) -> object:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {"success": False, "error": "未登录"}
    try:
        return await services.auth.user_info(decode_access_token(auth[7:], services.auth._jwt_secret))
    except AuthenticationError:
        return {"success": False, "error": "Token 无效或已过期"}


@router.get("/models")
async def models() -> list[dict[str, str]]:
    return [{"id": "openai", "name": "OpenAI", "region": "global", "apiKeyUrl": "https://platform.openai.com/api-keys"}]
