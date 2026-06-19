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

    def test_run_completes_to_approval_required_and_plan_is_fetchable(self):
        created = self.client.post("/api/runs", json={"goal": "family afternoon"}).json()
        status = self.wait_for_status(created["run_id"], "approval_required")

        self.assertEqual(status["plan_id"], created["plan_id"])
        plan = self.client.get(f"/api/plans/{created['plan_id']}").json()
        self.assertEqual(plan["plan_id"], created["plan_id"])
        self.assertEqual(plan["plan"]["status"], "approval_required")
        self.assertGreater(len(plan["actions"]), 0)
