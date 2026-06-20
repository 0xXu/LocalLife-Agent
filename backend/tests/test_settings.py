import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_production_requires_openai_and_jwt_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", openai_api_key="", jwt_secret="")
