import time
import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.api.app import create_app
from backend.application.run_service import RunService


class RunApprovalApiTest(unittest.TestCase):
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
            response = self.client.get(f"/api/runs/{run_id}")
            response.raise_for_status()
            data = response.json()
            if data["status"] == expected:
                return data
            time.sleep(0.05)
        self.fail(f"run {run_id} did not reach {expected}")

    def create_approval_run(self):
        response = self.client.post("/api/runs", json={"goal": "family afternoon"})
        response.raise_for_status()
        created = response.json()
        self.wait_for_status(created["run_id"], "needs_clarification")
        response = self.client.post(
            f"/api/runs/{created['run_id']}/clarifications",
            json={"question_id": "time_window", "answer": "today afternoon 2pm"},
        )
        response.raise_for_status()
        self.wait_for_status(created["run_id"], "approval_required")
        return created

    def test_approve_actions_executes_runtime_and_persists_receipts(self):
        created = self.create_approval_run()
        plan = self.client.get(f"/api/plans/{created['plan_id']}").json()
        action_id = plan["actions"][0]["action_id"]

        response = self.client.post(
            f"/api/runs/{created['run_id']}/actions/approve",
            json={"action_ids": [action_id]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], {"executing", "completed"})
        status = self.client.get(f"/api/runs/{created['run_id']}").json()
        self.assertEqual(status["status"], "completed")
        updated_plan = self.client.get(f"/api/plans/{created['plan_id']}").json()
        self.assertEqual(updated_plan["status"], "completed")
        self.assertEqual(updated_plan["receipts"][0]["action_id"], action_id)
        self.assertEqual(updated_plan["plan"]["receipts"][0]["action_id"], action_id)
        approved_action = next(action for action in updated_plan["actions"] if action["action_id"] == action_id)
        self.assertIn(approved_action.get("status"), {"completed", "confirmed"})

    def test_reject_approval_run_marks_run_rejected(self):
        created = self.create_approval_run()

        response = self.client.post(
            f"/api/runs/{created['run_id']}/actions/reject",
            json={"reason": "not today"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "rejected")
        status = self.client.get(f"/api/runs/{created['run_id']}").json()
        self.assertEqual(status["status"], "rejected")
