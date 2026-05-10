from __future__ import annotations

import json
import os
import socket
import subprocess
import urllib.error
import urllib.request
from collections.abc import Generator
from typing import Any

from backend.llm.config import LLMConfig


class LLMClient:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env_file()

    def chat(self, messages: list[dict[str, str]], max_tokens: int | None = None) -> dict[str, Any]:
        if not self.config.is_configured:
            raise RuntimeError("LLM is not configured. Check LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL.")
        payload = self._build_payload(messages, max_tokens=max_tokens, stream=False)
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
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"LLM request timed out after {exc.timeout} seconds via curl.") from exc
        if completed.returncode != 0:
            detail = "\n".join(part.strip() for part in [completed.stderr, completed.stdout] if part.strip())
            raise RuntimeError(f"LLM request failed via curl with exit {completed.returncode}: {detail}")
        return json.loads(completed.stdout)

    def chat_stream(self, messages: list[dict[str, str]], max_tokens: int | None = None) -> Generator[str, None, None]:
        """Stream tokens from an OpenAI-compatible SSE endpoint."""
        if not self.config.is_configured:
            raise RuntimeError("LLM is not configured. Check LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL.")
        payload = self._build_payload(messages, max_tokens=max_tokens, stream=True)
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
                buffer = ""
                for chunk in iter(lambda: response.read(4096), b""):
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            return
                        try:
                            obj = json.loads(data)
                            delta = obj.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM stream failed with HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            fallback_payload = {**payload, "stream": False}
            response = self._curl_chat(url, fallback_payload)
            content = response.get("choices", [{}])[0].get("message", {}).get("content")
            if not content:
                raise RuntimeError("LLM stream fallback returned an empty response.")
            yield content

    def _build_payload(self, messages: list[dict[str, str]], max_tokens: int | None = None, stream: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": stream,
        }
        if self.config.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        if self.config.disable_thinking:
            payload["thinking"] = {"type": "disabled"}
        return payload

    def _curl_chat_stream(self, url: str, payload: dict[str, Any]) -> Generator[str, None, None]:
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
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        try:
            assert proc.stdin and proc.stdout
            proc.stdin.write(json.dumps(payload, ensure_ascii=False))
            proc.stdin.close()
            buffer = ""
            for chunk in iter(lambda: proc.stdout.read(4096), ""):
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    try:
                        obj = json.loads(data)
                        delta = obj.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue
        finally:
            proc.terminate()
