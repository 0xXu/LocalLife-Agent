from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any

from backend.llm.config import LLMConfig


class LLMClient:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env_file()

    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self.config.is_configured:
            raise RuntimeError("LLM is not configured. Check LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL.")
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError:
            return self._curl_chat(url, payload)

    def _curl_chat(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        binary = "curl.exe" if os.name == "nt" else "curl"
        command = [
            binary,
            "-sS",
            "--fail-with-body",
            "-X",
            "POST",
            url,
            "-H",
            f"Authorization: Bearer {self.config.api_key}",
            "-H",
            "Content-Type: application/json",
            "--data-binary",
            "@-",
        ]
        completed = subprocess.run(
            command,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.config.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            detail = "\n".join(part.strip() for part in [completed.stderr, completed.stdout] if part.strip())
            raise RuntimeError(f"LLM request failed via curl with exit {completed.returncode}: {detail}")
        return json.loads(completed.stdout)
