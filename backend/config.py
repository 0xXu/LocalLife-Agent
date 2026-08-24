from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "local-life-agent"
    cors_origins: str = "http://127.0.0.1:4174,http://localhost:4174"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_thinking: Literal["disabled"] = "disabled"
    decision_llm_timeout_seconds: float = Field(default=45, ge=1)
    supply_query_timeout_seconds: float = Field(default=10, ge=1)

    database_url: str = "postgresql+asyncpg://locallife:locallife@postgres:5432/locallife"
    temporal_address: str = "temporal:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "local-life-fulfillment"
    supply_mcp_url: str = "http://supply-mcp:8790/mcp"
    supply_mcp_host: str = "0.0.0.0"
    supply_mcp_port: int = 8790
    supply_catalog_path: str = ""
    use_in_memory_store: bool = False
    enable_temporal: bool = True
    live_observation_interval_seconds: int = Field(default=15, ge=1)

    default_city: str = "北京"
    default_origin: str = "国贸"
    default_budget_yuan: int = Field(default=500, ge=1)
    default_party_size: int = Field(default=1, ge=1)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def deepseek_litellm_model(self) -> str:
        return f"deepseek/{self.deepseek_model}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
