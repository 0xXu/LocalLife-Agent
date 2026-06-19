import time
import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.api.app import create_app
from backend.application.run_service import RunService


class RunsRuntimeIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.service = RunService(
            database_path=f"{self.tmp.name}/workflow.sqlite",
            runtime=OpenAIAgentsRuntime(dry_run=True),
        )
        self.client = TestClient(create_app(run_service=self.service))

    def tearDown(self):
        self.tmp.cleanup()

    def wait_for_status(self, run_id, expected):
        for _ in range(20):
            data = self.client.get(f"/api/runs/{run_id}").json()
            if data["status"] == expected:
                return data
            time.sleep(0.05)
        self.fail(f"run {run_id} did not reach {expected}")

    def wait_for_event(self, run_id, event_type):
        for _ in range(20):
            events = self.service.events.replay(run_id)
            for event in events:
                if event.type == event_type:
                    return event
            time.sleep(0.05)
        self.fail(f"run {run_id} did not emit {event_type}")

    def test_run_completes_to_approval_required_and_plan_is_fetchable(self):
        created = self.client.post("/api/runs", json={"goal": "family afternoon"}).json()
        self.wait_for_status(created["run_id"], "needs_clarification")
        self.service.submit_clarification(created["run_id"], "time_window", "today afternoon 2pm")
        status = self.wait_for_status(created["run_id"], "approval_required")

        self.assertEqual(status["plan_id"], created["plan_id"])
        plan = self.client.get(f"/api/plans/{created['plan_id']}").json()
        self.assertEqual(plan["plan_id"], created["plan_id"])
        self.assertEqual(plan["plan"]["status"], "approval_required")
        self.assertGreater(len(plan["actions"]), 0)

    def test_run_resumes_same_run_after_single_clarification_answer(self):
        created = self.client.post("/api/runs", json={"goal": "下午帮我安排个地方玩一下"}).json()
        self.wait_for_status(created["run_id"], "needs_clarification")

        record = self.service.submit_clarification(
            created["run_id"],
            "time_window",
            "今天下午 2 点开始，玩 3 小时",
        )

        self.assertEqual(record.run_id, created["run_id"])
        status = self.wait_for_status(created["run_id"], "approval_required")
        self.assertEqual(status["plan_id"], created["plan_id"])

    def test_clarification_can_be_submitted_immediately_after_event_is_visible(self):
        created = self.client.post("/api/runs", json={"goal": "下午帮我安排个地方玩一下"}).json()
        event = self.wait_for_event(created["run_id"], "clarification.required")

        response = self.client.post(
            f"/api/runs/{created['run_id']}/clarifications",
            json={"question_id": event.payload["question"]["id"], "answer": "今天下午 2 点"},
        )

        self.assertEqual(response.status_code, 200)
        self.wait_for_status(created["run_id"], "approval_required")

    def test_duplicate_clarification_answer_does_not_start_second_resume(self):
        created = self.client.post("/api/runs", json={"goal": "下午帮我安排个地方玩一下"}).json()
        self.wait_for_status(created["run_id"], "needs_clarification")

        first = self.client.post(
            f"/api/runs/{created['run_id']}/clarifications",
            json={"question_id": "time_window", "answer": "今天下午 2 点"},
        )
        second = self.client.post(
            f"/api/runs/{created['run_id']}/clarifications",
            json={"question_id": "time_window", "answer": "今天下午 4 点"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()["error"]["code"], "clarification_not_required")
