import tempfile
import unittest
from pathlib import Path

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

            config = LLMConfig.from_env_file(env_path)

        self.assertEqual(config.provider, "mimo")
        self.assertEqual(config.protocol, "openai")
        self.assertEqual(config.base_url, "https://token-plan-sgp.xiaomimimo.com/v1")
        self.assertEqual(config.model, "MiMo-V2.5-Pro")
        self.assertTrue(config.is_configured)
        self.assertNotIn("secret-key-value", str(config.safe_status()))
        self.assertEqual(config.safe_status()["api_key"], "configured")


if __name__ == "__main__":
    unittest.main()
