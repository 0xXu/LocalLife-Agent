from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "test", "production"] = "local"
    openai_api_key: str = ""
    jwt_secret: str = ""
    database_url: str = (
        "postgresql+asyncpg://liquidroute:liquidroute@localhost:5433/liquidroute"
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment == "production":
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required in production")
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
        return self
