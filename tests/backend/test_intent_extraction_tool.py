import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.agents.intent_extraction_tool import IntentExtractionTool
from backend.agents.runtime import PlanRunRequest


class IntentExtractionToolTest(unittest.IsolatedAsyncioTestCase):
    async def test_tool_extracts_constraints_and_missing_fields_from_llm_output(self):
        async def fake_runner_run(_agent, prompt):
            self.assertIn("User goal:", prompt)
            return SimpleNamespace(
                final_output='{"constraints":{"time_window":"今天下午 2 点"},"missing_fields":["start_location","party_size"]}'
            )

        tool = IntentExtractionTool(dry_run=False, model="demo-model")

        with patch("backend.agents.intent_extraction_tool.Runner.run", side_effect=fake_runner_run):
            result = await tool.extract(
                PlanRunRequest(goal="我想出去玩", user_id="user_1"),
                base_constraints={},
                sink=lambda _event_type, _payload: async_noop(),
            )

        self.assertEqual(result["time_window"], "今天下午 2 点")
        self.assertEqual(result["__llm_missing_fields"], ["start_location", "party_size"])


async def async_noop():
    return None
