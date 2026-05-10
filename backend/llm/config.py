from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "mimo"
    protocol: str = "openai"
    base_url: str = ""
    api_key: str = ""
    model: str = "MiMo-V2.5-Pro"
    temperature: float = 0.2
    max_tokens: int = 2048
    timeout_seconds: int = 60
    remote_enabled: bool = False

    @classmethod
    def from_env_file(cls, env_path: Path | None = None) -> "LLMConfig":
        root = Path(__file__).resolve().parents[2]
        values = parse_env_file(env_path or root / ".env")
        merged = {**values, **os.environ}
        base_url = merged.get("LLM_BASE_URL", "")
        api_key = merged.get("LLM_API_KEY", "")
        model = merged.get("LLM_MODEL", "MiMo-V2.5-Pro")
        remote_raw = merged.get("LLM_REMOTE_ENABLED")
        remote_enabled = (
            remote_raw.lower() in {"1", "true", "yes", "on"}
            if remote_raw is not None
            else bool(base_url and api_key and model)
        )
        return cls(
            provider=merged.get("LLM_PROVIDER", "mimo"),
            protocol=merged.get("LLM_API_PROTOCOL", "openai"),
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=float(merged.get("LLM_TEMPERATURE", "0.2")),
            max_tokens=int(merged.get("LLM_MAX_TOKENS", "2048")),
            timeout_seconds=int(merged.get("LLM_TIMEOUT_SECONDS", "30")),
            remote_enabled=remote_enabled,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def safe_status(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "protocol": self.protocol,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": "configured" if self.api_key else "missing",
            "configured": self.is_configured,
            "remote_enabled": self.remote_enabled,
        }


def parse_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
