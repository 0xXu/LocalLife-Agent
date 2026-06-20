"""Registration and login use cases using Argon2id and signed access tokens."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from app.infrastructure.entities import UserProfileEntity
from app.security.jwt import AuthenticationError, create_access_token
from app.security.passwords import hash_password, verify_password


class InvalidCredentialsError(AuthenticationError):
    """Raised when a username does not exist or its password is incorrect."""


class DuplicateUserError(ValueError):
    """Raised when a registration name is already in use."""


class UserStore(Protocol):
    async def get_by_name(self, name: str) -> UserProfileEntity | None: ...

    async def get_by_user_id(self, user_id: str) -> UserProfileEntity | None: ...

    async def create(self, user: UserProfileEntity) -> UserProfileEntity: ...


@dataclass(frozen=True, slots=True)
class AuthResult:
    user_id: str
    name: str
    token: str


class AuthService:
    def __init__(self, users: UserStore, *, jwt_secret: str) -> None:
        self._users = users
        self._jwt_secret = jwt_secret

    async def register(self, name: str, password: str, city: str | None = None) -> AuthResult:
        if await self._users.get_by_name(name) is not None:
            raise DuplicateUserError("name is already registered")

        user = UserProfileEntity(
            user_id=str(uuid4()),
            name=name,
            password_hash=hash_password(password),
            profile_name=f"{city or '北京'}探索者",
            preferred_city=city or "北京",
            created_at=datetime.now(timezone.utc),
        )
        saved = await self._users.create(user)
        return self._result(saved)

    async def login(self, name: str, password: str) -> AuthResult:
        user = await self._users.get_by_name(name)
        if user is None or not user.password_hash or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("invalid name or password")
        return self._result(user)

    async def user_info(self, user_id: str) -> dict[str, object]:
        user = await self._users.get_by_user_id(user_id)
        if user is None:
            raise InvalidCredentialsError("user no longer exists")
        return {"success": "true", "userId": user.user_id, "name": user.name,
                "profileName": user.profile_name or "", "preferredCity": user.preferred_city or "北京",
                "hasApiKey": "false"}

    def _result(self, user: UserProfileEntity) -> AuthResult:
        return AuthResult(
            user_id=user.user_id,
            name=user.name,
            token=create_access_token(user.user_id, self._jwt_secret),
        )
