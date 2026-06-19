import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.agents.intent_extraction_tool import LLM_MISSING_FIELDS_KEY
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

    async def test_extracted_time_window_moves_to_next_missing_question(self):
        def fake_llm_extractor(request):
            self.assertEqual(request.goal, "今天下午两点我想去玩")
            return {"time_window": "今天下午两点"}

        runtime = OpenAIAgentsRuntime(dry_run=True, constraint_extractor=fake_llm_extractor)
        events = []

        async def sink(event_type, payload):
            events.append((event_type, payload))

        result = await runtime.start_plan(
            PlanRunRequest(goal="今天下午两点我想去玩", user_id="user_1"),
            RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
            sink,
        )

        self.assertEqual(result.status, "needs_clarification")
        self.assertEqual(result.clarification["question"]["id"], "start_location")
        self.assertIn("clarification.required", [event[0] for event in events])

    async def test_clarification_queue_reuses_initial_extraction(self):
        extractor_calls = 0

        def fake_llm_extractor(_request):
            nonlocal extractor_calls
            extractor_calls += 1
            return {"time_window": "今天下午 2 点"}

        runtime = OpenAIAgentsRuntime(dry_run=True, constraint_extractor=fake_llm_extractor)

        async def sink(_event_type, _payload):
            return None

        first = await runtime.start_plan(
            PlanRunRequest(goal="我想出去玩", user_id="user_1"),
            RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
            sink,
        )
        second = await runtime.start_plan(
            PlanRunRequest(
                goal="我想出去玩",
                user_id="user_1",
                constraints=first.clarification["partial_constraints"],
                answers={"start_location": "家附近"},
            ),
            RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
            sink,
        )
        third = await runtime.start_plan(
            PlanRunRequest(
                goal="我想出去玩",
                user_id="user_1",
                constraints=second.clarification["partial_constraints"],
                answers={"start_location": "家附近", "party_size": 2},
            ),
            RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
            sink,
        )

        self.assertEqual(extractor_calls, 1)
        self.assertEqual(first.clarification["question"]["id"], "start_location")
        self.assertEqual(second.clarification["question"]["id"], "party_size")
        self.assertEqual(third.clarification["question"]["id"], "activity_preference")

    async def test_runtime_uses_injected_intent_tool_boundary(self):
        class FakeIntentTool:
            def __init__(self):
                self.calls = 0

            async def extract(self, _request, *, base_constraints, sink):
                self.calls += 1
                await sink("agent.completed", {"agent": "intent_tool"})
                return {
                    **base_constraints,
                    "time_window": "今天下午 2 点",
                    LLM_MISSING_FIELDS_KEY: ["start_location"],
                }

        tool = FakeIntentTool()
        runtime = OpenAIAgentsRuntime(dry_run=True, intent_tool=tool)
        events = []

        async def sink(event_type, payload):
            events.append((event_type, payload))

        result = await runtime.start_plan(
            PlanRunRequest(goal="我想出去玩", user_id="user_1"),
            RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
            sink,
        )

        self.assertEqual(tool.calls, 1)
        self.assertEqual(result.status, "needs_clarification")
        self.assertEqual(result.clarification["question"]["id"], "start_location")
        self.assertIn(("agent.completed", {"agent": "intent_tool"}), events)

    async def test_local_dry_run_returns_grounded_plan_result(self):
        runtime = OpenAIAgentsRuntime(dry_run=True)
        events = []

        async def sink(event_type, payload):
            events.append((event_type, payload))

        result = await runtime.start_plan(
            PlanRunRequest(
                goal="family afternoon",
                user_id="user_1",
                answers={
                    "time_window": "today afternoon 2pm",
                    "start_location": "home",
                    "party_size": 3,
                    "activity_preference": "park and cafe",
                },
            ),
            RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
            sink,
        )

        self.assertEqual(result.status, "approval_required")
        self.assertEqual(result.plan["id"], "plan_1")
        self.assertGreater(len(result.pending_actions), 0)
        self.assertIn(("agent.started", {"agent": "planner"}), events)

    async def test_remote_planner_requires_approval_before_completion(self):
        def fake_llm_extractor(_request):
            return {
                "time_window": "今天下午 2 点",
                "start_location": "家附近",
                "party_size": 2,
                "activity_preference": "散步逛逛",
            }

        async def fake_runner_run(_agent, _prompt):
            return SimpleNamespace(final_output="推荐一个下午轻量出行方案")

        runtime = OpenAIAgentsRuntime(dry_run=False, constraint_extractor=fake_llm_extractor)
        events = []

        async def sink(event_type, payload):
            events.append((event_type, payload))

        with patch("backend.agents.openai_runtime.Runner.run", side_effect=fake_runner_run):
            result = await runtime.start_plan(
                PlanRunRequest(goal="我想出去玩", user_id="user_1"),
                RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
                sink,
            )

        self.assertEqual(result.status, "approval_required")
        self.assertEqual(result.plan["status"], "approval_required")
        self.assertEqual(result.pending_actions[0]["action_id"], "act_send_plan_summary")
        self.assertIn("推荐一个下午轻量出行方案", result.plan["summary"])
        self.assertIn("approval.required", [event[0] for event in events])

    async def test_remote_planner_prompt_includes_clarified_constraints(self):
        def fake_llm_extractor(_request):
            return {
                "time_window": "今天下午 2 点",
                "start_location": "家附近",
                "party_size": 2,
                "activity_preference": "散步逛逛",
            }

        prompts = []

        async def fake_runner_run(_agent, prompt):
            prompts.append(prompt)
            return SimpleNamespace(final_output="按家附近、两人、下午两点散步安排")

        runtime = OpenAIAgentsRuntime(dry_run=False, constraint_extractor=fake_llm_extractor)

        async def sink(_event_type, _payload):
            return None

        with patch("backend.agents.openai_runtime.Runner.run", side_effect=fake_runner_run):
            await runtime.start_plan(
                PlanRunRequest(goal="我想出去玩", user_id="user_1"),
                RuntimeContext(run_id="run_1", plan_id="plan_1", user_id="user_1"),
                sink,
            )

        self.assertEqual(len(prompts), 1)
        self.assertIn('"time_window": "今天下午 2 点"', prompts[0])
        self.assertIn('"start_location": "家附近"', prompts[0])
        self.assertIn('"party_size": 2', prompts[0])
        self.assertIn('"activity_preference": "散步逛逛"', prompts[0])

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
