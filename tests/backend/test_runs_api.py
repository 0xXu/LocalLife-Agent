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
        self.run_service.wait_for_workers()
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
        self.assertIn(data["status"], {"queued", "running", "needs_clarification", "approval_required", "completed"})

    def test_invalid_goal_returns_400(self):
        response = self.client.post("/api/runs", json={"goal": ""})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_malformed_json_returns_invalid_json(self):
        response = self.client.post("/api/runs", content=b'{"goal":', headers={"content-type": "application/json"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_json")

    def test_stream_missing_run_returns_not_found(self):
        response = self.client.get("/api/runs/run_missing/events")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "run_not_found")

    def test_stream_skips_duplicate_replayed_event_ids(self):
        created = self.client.post("/api/runs", json={"goal": "family afternoon"}).json()
        self.run_service.events.close_queue(created["run_id"])

        with self.client.stream("GET", f"/api/runs/{created['run_id']}/events") as response:
            body = response.read().decode("utf-8")

        event_ids = [line.removeprefix("id: ") for line in body.splitlines() if line.startswith("id: ")]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(event_ids[0], f"{created['run_id']}_evt_000001")
        self.assertEqual(event_ids, list(dict.fromkeys(event_ids)))

    def test_submit_clarification_rejects_stale_question_after_resume(self):
        created = self.client.post("/api/runs", json={"goal": "family afternoon"}).json()
        self.run_service.wait_for_workers(timeout=2.0)
        self.run_service.submit_clarification(created["run_id"], "time_window", "今天下午 2 点")
        self.run_service.wait_for_workers(timeout=2.0)

        response = self.client.post(
            f"/api/runs/{created['run_id']}/clarifications",
            json={"question_id": "time_window", "answer": "今天下午 2 点"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "clarification_question_mismatch")

    def test_submit_clarification_validates_question_id(self):
        created = self.client.post("/api/runs", json={"goal": "下午帮我安排个地方玩一下"}).json()
        self.run_service.wait_for_workers(timeout=2.0)

        response = self.client.post(
            f"/api/runs/{created['run_id']}/clarifications",
            json={"question_id": "party_size", "answer": 3},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "clarification_question_mismatch")

    def test_submit_clarification_resumes_same_run(self):
        created = self.client.post("/api/runs", json={"goal": "下午帮我安排个地方玩一下"}).json()
        self.run_service.wait_for_workers(timeout=2.0)

        response = self.client.post(
            f"/api/runs/{created['run_id']}/clarifications",
            json={"question_id": "time_window", "answer": "今天下午 2 点"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run_id"], created["run_id"])
        self.assertEqual(response.json()["accepted_question_id"], "time_window")
