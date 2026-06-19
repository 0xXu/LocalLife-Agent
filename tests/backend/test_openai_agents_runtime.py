import unittest

from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.agents.runtime import ExecuteActionsRequest, PlanRunRequest, RuntimeContext
from backend.llm.config import LLMConfig


class OpenAIAgentsRuntimeTest(unittest.IsolatedAsyncioTestCase):
    def test_remote_llm_config_builds_non_dry_run_runtime(self):
        runtime = OpenAIAgentsRuntime.from_llm_config(
            LLMConfig(
                base_url="https://example.com/v1",
                api_key="secret",
                model="demo-model",
                remote_enabled=True,
            )
        )

        self.assertFalse(runtime.dry_run)
        self.assertEqual(runtime.model, "demo-model")

    def test_disabled_remote_llm_config_builds_dry_run_runtime(self):
        runtime = OpenAIAgentsRuntime.from_llm_config(
            LLMConfig(
                base_url="https://example.com/v1",
                api_key="secret",
                model="demo-model",
                remote_enabled=False,
            )
        )

        self.assertTrue(runtime.dry_run)

    async def test_local_dry_run_asks_one_clarification_before_approval(self):
        runtime = OpenAIAgentsRuntime(dry_run=True)
        events = []

        async def sink(event_type, payload):
            events.append((event_type, payload))

        result = await runtime.start_plan(
            PlanRunRequest(goal="下午帮我安排个地方玩一下", user_id="user_1"),
            RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
            sink,
        )

        self.assertEqual(result.status, "needs_clarification")
        self.assertEqual(result.clarification["question"]["id"], "time_window")
        self.assertEqual([event[0] for event in events], ["agent.started", "clarification.required"])

    async def test_local_dry_run_returns_grounded_plan_result(self):
        runtime = OpenAIAgentsRuntime(dry_run=True)
        events = []

        async def sink(event_type, payload):
            events.append((event_type, payload))

        result = await runtime.start_plan(
            PlanRunRequest(
                goal="family afternoon",
                user_id="user_1",
                answers={"time_window": "today afternoon 2pm"},
            ),
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
