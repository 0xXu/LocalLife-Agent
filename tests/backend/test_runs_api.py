import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.application.run_service import RunService


class RunsApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.run_service = RunService(database_path=f"{self.tmp.name}/workflow.sqlite")
        self.client = TestClient(create_app(run_service=self.run_service))

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_run_returns_run_centered_contract(self):
        response = self.client.post("/api/runs", json={"goal": "family afternoon", "user_id": "user_1"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["run_id"].startswith("run_"))
        self.assertTrue(data["plan_id"].startswith("plan_"))
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["events_url"], f"/api/runs/{data['run_id']}/events")

    def test_get_run_returns_product_status(self):
        created = self.client.post("/api/runs", json={"goal": "family afternoon"}).json()

        response = self.client.get(f"/api/runs/{created['run_id']}")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["run_id"], created["run_id"])
        self.assertEqual(data["plan_id"], created["plan_id"])
        self.assertIn(data["status"], {"queued", "running", "completed"})

    def test_invalid_goal_returns_400(self):
        response = self.client.post("/api/runs", json={"goal": ""})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
