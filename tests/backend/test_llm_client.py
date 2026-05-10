import json
import subprocess
import unittest
import urllib.error
from unittest.mock import patch

from backend.llm.client import LLMClient
from backend.llm.config import LLMConfig


class LLMClientTest(unittest.TestCase):
    def test_chat_falls_back_to_curl_when_urllib_tls_fails(self):
        config = LLMConfig(
            base_url="https://token-plan-sgp.xiaomimimo.com/v1",
            api_key="secret-key-value",
            model="MiMo-V2.5-Pro",
        )
        expected = {"choices": [{"message": {"content": "{\"ok\": true}"}}]}
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(expected),
            stderr="",
        )

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("tls failed")):
            with patch("subprocess.run", return_value=completed) as run:
                response = LLMClient(config).chat([{"role": "user", "content": "ping"}])

        self.assertEqual(response, expected)
        command = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertIn(command[0], {"curl", "curl.exe"})
        self.assertIn("Authorization: Bearer secret-key-value", command)
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")

    def test_curl_timeout_error_does_not_expose_api_key(self):
        config = LLMConfig(
            base_url="https://token-plan-sgp.xiaomimimo.com/v1",
            api_key="secret-key-value",
            model="mimo-v2.5-pro",
            timeout_seconds=1,
        )

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("tls failed")):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["curl.exe", "Authorization: Bearer secret-key-value"], 1)):
                with self.assertRaises(RuntimeError) as raised:
                    LLMClient(config).chat([{"role": "user", "content": "ping"}])

        self.assertNotIn("secret-key-value", str(raised.exception))
        self.assertIn("timed out", str(raised.exception))

    def test_chat_stream_curl_fallback_uses_bounded_non_stream_request(self):
        config = LLMConfig(
            base_url="https://token-plan-sgp.xiaomimimo.com/v1",
            api_key="secret-key-value",
            model="mimo-v2.5-pro",
            timeout_seconds=3,
        )
        expected = {"choices": [{"message": {"content": "{\"scenario\":\"friends\"}"}}]}
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(expected),
            stderr="",
        )

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("tls failed")):
            with patch("subprocess.run", return_value=completed) as run:
                chunks = list(LLMClient(config).chat_stream([{"role": "user", "content": "ping"}]))

        self.assertEqual(chunks, ['{"scenario":"friends"}'])
        payload = json.loads(run.call_args.kwargs["input"])
        self.assertIs(payload.get("stream"), False)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(run.call_args.kwargs["timeout"], 3)

    def test_chat_requests_json_content_and_disables_provider_reasoning(self):
        config = LLMConfig(
            base_url="https://token-plan-sgp.xiaomimimo.com/v1",
            api_key="secret-key-value",
            model="mimo-v2.5-pro",
            response_format="json_object",
            disable_thinking=True,
        )
        expected = {"choices": [{"message": {"content": "{\"ok\": true}"}}]}
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(expected),
            stderr="",
        )

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("tls failed")):
            with patch("subprocess.run", return_value=completed) as run:
                LLMClient(config).chat([{"role": "user", "content": "ping"}])

        payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["thinking"], {"type": "disabled"})


if __name__ == "__main__":
    unittest.main()
