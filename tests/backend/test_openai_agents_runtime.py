import unittest

from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.agents.runtime import ExecuteActionsRequest, PlanRunRequest, RuntimeContext


class OpenAIAgentsRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_local_dry_run_returns_grounded_plan_result(self):
        runtime = OpenAIAgentsRuntime(dry_run=True)
        events = []

        async def sink(event_type, payload):
            events.append((event_type, payload))

        result = await runtime.start_plan(
            PlanRunRequest(goal="family afternoon", user_id="user_1"),
            RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
            sink,
        )

        self.assertEqual(result.status, "approval_required")
        self.assertEqual(result.plan["id"], "plan_1")
        self.assertGreater(len(result.pending_actions), 0)
        self.assertIn(("agent.started", {"agent": "planner"}), events)

    async def test_execute_actions_uses_runtime_context_for_plan_identity(self):
        runtime = OpenAIAgentsRuntime(dry_run=True)
        events = []

        async def sink(event_type, payload):
            events.append((event_type, payload))

        result = await runtime.execute_actions(
            ExecuteActionsRequest(action_ids=["act_1"]),
            RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
            sink,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.receipts[0]["plan_id"], "plan_1")
        self.assertIn(("actions.execution.started", {"plan_id": "plan_1", "action_ids": ["act_1"]}), events)
