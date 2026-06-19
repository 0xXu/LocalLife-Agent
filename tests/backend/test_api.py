import time
import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.agents.openai_runtime import OpenAIAgentsRuntime
from backend.api.app import create_app
from backend.application.run_service import RunService
from backend.profile.store import UserProfileStore
from backend.tools.registry import LocalToolRegistry


class BackendApiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.run_service = RunService(
            database_path=f"{self._tmp.name}/workflow.sqlite",
            runtime=OpenAIAgentsRuntime(dry_run=True),
        )
        self.client = TestClient(
            create_app(
                run_service=self.run_service,
                profile_store=UserProfileStore(f"{self._tmp.name}/profiles.sqlite"),
                tool_registry=LocalToolRegistry(),
            )
        )

    def tearDown(self):
        self._tmp.cleanup()

    def request(self, method, path, body=None):
        response = self.client.request(method, path, json=body)
        return response.status_code, response.json()

    def wait_for_status(self, run_id, expected):
        for _ in range(20):
            response = self.client.get(f"/api/runs/{run_id}")
            response.raise_for_status()
            data = response.json()
            if data["status"] == expected:
                return data
            time.sleep(0.05)
        self.fail(f"run {run_id} did not reach {expected}")

    def create_plan(self, goal="family afternoon with child age 5"):
        response = self.client.post("/api/runs", json={"goal": goal, "user_id": "user_1"})
        self.assertEqual(response.status_code, 200)
        created = response.json()
        self.wait_for_status(created["run_id"], "approval_required")
        return created

    def test_openapi_documents_new_run_paths_and_removes_legacy_paths(self):
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        for path in [
            "/api/health",
            "/api/llm/status",
            "/api/runs",
            "/api/runs/{run_id}",
            "/api/runs/{run_id}/events",
            "/api/runs/{run_id}/actions/approve",
            "/api/runs/{run_id}/actions/reject",
            "/api/plans/{plan_id}",
            "/api/tool-schemas",
            "/api/users/{user_id}/profile",
        ]:
            self.assertIn(path, paths)
        for path in [
            "/api/plans",
            "/api/plans/runs",
            "/api/plans/runs/{run_id}/stream",
            "/api/plans/{plan_id}/resume",
            "/api/plans/{plan_id}/versions",
            "/api/plans/build",
            "/api/plans/build/stream",
            "/api/plans/{plan_id}/confirm",
            "/api/plans/{plan_id}/execute",
            "/api/plans/{plan_id}/recover",
            "/api/plans/{plan_id}/constraints",
            "/api/plans/{plan_id}/alternatives",
            "/api/plans/{plan_id}/revise",
        ]:
            self.assertNotIn(path, paths)

    def test_legacy_plan_run_routes_return_not_found(self):
        created = self.create_plan()

        for method, path in [
            ("POST", "/api/plans/runs"),
            ("GET", f"/api/plans/runs/{created['run_id']}/stream"),
            ("POST", f"/api/plans/{created['plan_id']}/resume"),
            ("GET", f"/api/plans/{created['plan_id']}/versions"),
            ("GET", "/api/plans"),
        ]:
            status, data = self.request(method, path, {"decision": "approve"})
            self.assertIn(status, {404, 405})
            if status == 404:
                self.assertEqual(data["error"]["code"], "not_found")

    def test_cors_preflight_allows_frontend_origin(self):
        response = self.client.options(
            "/api/runs",
            headers={
                "Origin": "http://127.0.0.1:4173",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")
        self.assertIn("POST", response.headers["access-control-allow-methods"])

    def test_health_endpoint(self):
        status, data = self.request("GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "weekendpilot-planner")
        self.assertEqual(data["mode"], "fastapi-python-service")
        self.assertGreaterEqual(data["agents"], 7)

    def test_plan_detail_uses_new_run_service(self):
        created = self.create_plan("friends afternoon, four adults, activity before dinner")

        status, fetched = self.request("GET", f"/api/plans/{created['plan_id']}")

        self.assertEqual(status, 200)
        self.assertEqual(fetched["plan_id"], created["plan_id"])
        self.assertEqual(fetched["run_id"], created["run_id"])
        self.assertEqual(fetched["plan"]["id"], created["plan_id"])
        self.assertEqual(fetched["status"], "approval_required")

    def test_removed_execute_endpoint(self):
        created = self.create_plan()

        status, executed = self.request(
            "POST",
            f"/api/plans/{created['plan_id']}/execute",
            {"confirmed": True},
        )

        self.assertEqual(status, 404)
        self.assertEqual(executed["error"]["code"], "not_found")

    def test_invalid_json_returns_400_response(self):
        response = self.client.post("/api/runs", content="{bad json", headers={"Content-Type": "application/json"})

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"]["code"], "invalid_json")
        self.assertEqual(data["error"]["message"], "invalid_json")

    def test_tool_schemas_endpoint(self):
        status, data = self.request("GET", "/api/tool-schemas")

        self.assertEqual(status, 200)
        self.assertEqual(len(data["tools"]), 20)

    def test_user_profile_endpoints(self):
        status, data = self.request("GET", "/api/users/test_user/profile")
        self.assertEqual(status, 200)
        self.assertEqual(data["user_id"], "test_user")

        status, data = self.request("POST", "/api/users/test_user/profile", {
            "explicit_preferences": [{
                "key": "diet",
                "value": "low_fat",
                "source": "explicit",
                "confidence": 0.9,
                "scope": "long_term",
                "evidence": "user stated preference",
            }],
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["user_id"], "test_user")
        self.assertEqual(data["explicit_preferences"][0]["key"], "diet")


if __name__ == "__main__":
    unittest.main()
