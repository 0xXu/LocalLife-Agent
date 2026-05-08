import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.llm.config import LLMConfig


class LLMConfigTest(unittest.TestCase):
    def test_loads_openai_compatible_env_without_exposing_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "LLM_PROVIDER=mimo",
                        "LLM_API_PROTOCOL=openai",
                        "LLM_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1",
                        "LLM_API_KEY=secret-key-value",
                        "LLM_MODEL=MiMo-V2.5-Pro",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = LLMConfig.from_env_file(env_path)

        self.assertEqual(config.provider, "mimo")
        self.assertEqual(config.protocol, "openai")
        self.assertEqual(config.base_url, "https://token-plan-sgp.xiaomimimo.com/v1")
        self.assertEqual(config.model, "MiMo-V2.5-Pro")
        self.assertTrue(config.is_configured)
        self.assertNotIn("secret-key-value", str(config.safe_status()))
        self.assertEqual(config.safe_status()["api_key"], "configured")
        self.assertTrue(config.remote_enabled)

    def test_env_can_explicitly_disable_remote_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "LLM_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1",
                        "LLM_API_KEY=secret-key-value",
                        "LLM_MODEL=MiMo-V2.5-Pro",
                        "LLM_REMOTE_ENABLED=false",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = LLMConfig.from_env_file(env_path)

        self.assertFalse(config.remote_enabled)


if __name__ == "__main__":
    unittest.main()
