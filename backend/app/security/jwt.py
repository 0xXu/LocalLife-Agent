"""JWT creation and validation for authenticated API callers."""

from datetime import datetime, timedelta, timezone

import jwt
from jwt import PyJWTError


class AuthenticationError(ValueError):
    """Raised when credentials or a bearer token cannot be authenticated."""


def create_access_token(
    user_id: str,
    secret: str,
    *,
    expires_in: timedelta = timedelta(hours=24),
) -> str:
    """Create an HS256 token carrying the required subject and expiration claims."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + expires_in},
        secret,
        algorithm="HS256",
    )


def decode_access_token(token: str, secret: str) -> str:
    """Validate an HS256 access token and return its subject user id."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
    except PyJWTError as error:
        raise AuthenticationError("invalid or expired access token") from error

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise AuthenticationError("access token has an invalid subject")
    return user_id
