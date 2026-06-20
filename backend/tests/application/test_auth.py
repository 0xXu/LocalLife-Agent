import asyncio
from datetime import datetime, timezone

import pytest

from app.application.auth import AuthService, InvalidCredentialsError
from app.security.jwt import AuthenticationError, create_access_token, decode_access_token


TEST_SECRET = "test-secret-that-is-longer-than-thirty-two-characters"


class FakeUsers:
    def __init__(self) -> None:
        self.users: dict[str, object] = {}

    async def get_by_name(self, name: str) -> object | None:
        return self.users.get(name)

    async def create(self, user: object) -> object:
        self.users[user.name] = user  # type: ignore[attr-defined]
        return user


def test_registration_hashes_password_with_argon2id_and_login_returns_token() -> None:
    async def scenario() -> None:
        users = FakeUsers()
        service = AuthService(users, jwt_secret=TEST_SECRET)

        registered = await service.register("alice", "correct horse battery staple")
        stored = await users.get_by_name("alice")
        logged_in = await service.login("alice", "correct horse battery staple")

        assert stored is not None
        assert stored.password_hash.startswith("$argon2id$")  # type: ignore[attr-defined]
        assert decode_access_token(registered.token, TEST_SECRET) == registered.user_id
        assert decode_access_token(logged_in.token, TEST_SECRET) == registered.user_id

    asyncio.run(scenario())


def test_login_rejects_bad_password() -> None:
    async def scenario() -> None:
        service = AuthService(FakeUsers(), jwt_secret=TEST_SECRET)
        await service.register("alice", "correct horse battery staple")

        with pytest.raises(InvalidCredentialsError):
            await service.login("alice", "wrong password")

    asyncio.run(scenario())


def test_token_decode_returns_user_id_and_invalid_tokens_raise_typed_error() -> None:
    token = create_access_token("user-1", TEST_SECRET)

    assert decode_access_token(token, TEST_SECRET) == "user-1"
    with pytest.raises(AuthenticationError):
        decode_access_token("not.a.jwt", TEST_SECRET)
