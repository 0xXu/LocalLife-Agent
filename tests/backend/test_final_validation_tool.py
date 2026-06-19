import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.agents.final_validation_tool import FinalValidationTool
from backend.agents.runtime import PlanRunRequest


class FinalValidationToolTest(unittest.IsolatedAsyncioTestCase):
    async def test_tool_returns_remaining_missing_fields_from_llm_output(self):
        async def fake_runner_run(_agent, prompt):
            self.assertIn("Confirmed constraints JSON:", prompt)
            return SimpleNamespace(
                final_output='{"constraints":{"time_window":"今天下午 2 点"},"missing_fields":["start_location"]}'
            )

        tool = FinalValidationTool(dry_run=False, model="demo-model")

        with patch("backend.agents.final_validation_tool.Runner.run", side_effect=fake_runner_run):
            result = await tool.validate(
                PlanRunRequest(goal="我想出去玩", user_id="user_1"),
                constraints={"time_window": "今天下午 2 点"},
                sink=lambda _event_type, _payload: async_noop(),
            )

        self.assertEqual(result["constraints"]["time_window"], "今天下午 2 点")
        self.assertEqual(result["missing_fields"], ["start_location"])


async def async_noop():
    return None
