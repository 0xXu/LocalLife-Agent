import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.llm.config import LLMConfig
from backend.services.workflow_service import WorkflowService
from tests.backend.helpers import RuleBasedChatModel, FailingChatModel


class BackendApiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.workflow = self._make_workflow()
        self.client = TestClient(create_app(self.workflow))

    def tearDown(self):
        self._tmp.cleanup()

    def _make_workflow(self):
        workflow = WorkflowService(
            repository_path=f"{self._tmp.name}/workflow.sqlite",
            llm_config=LLMConfig(
                base_url="https://example.test/v1",
                api_key="secret",
                model="test-model",
                remote_enabled=True,
            ),
        )
        workflow.pipeline.chat_model = RuleBasedChatModel()
        return workflow

    def request(self, method, path, body=None):
        response = self.client.request(method, path, json=body)
        return response.status_code, response.json()

    def raw_request(self, method, path, payload):
        response = self.client.request(
            method,
            path,
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        return response.status_code, response.json()

    def start_run(self, goal="family afternoon with child age 5"):
        status, started = self.request("POST", "/api/plans/runs", {"goal": goal, "user_id": "user_1"})
        self.assertEqual(status, 200)
        return started

    def test_openapi_documents_graph_run_paths_and_removes_legacy_paths(self):
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        for path in [
            "/api/health",
            "/api/plans/runs",
            "/api/plans/runs/{run_id}/stream",
            "/api/plans/{plan_id}",
            "/api/plans/{plan_id}/resume",
            "/api/plans/{plan_id}/versions",
            "/api/tool-schemas",
        ]:
            self.assertIn(path, paths)
        for path in [
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

    def test_cors_preflight_allows_frontend_origin(self):
        response = self.client.options(
            "/api/plans/runs",
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

    def test_run_api_and_removed_execute_endpoint(self):
        started = self.start_run()
        plan_id = started["plan_id"]

        status, executed = self.request(
            "POST",
            f"/api/plans/{plan_id}/execute",
            {"confirmed": True},
        )
        self.assertEqual(status, 404)
        self.assertEqual(executed["error"]["code"], "not_found")

        status, fetched = self.request("GET", f"/api/plans/{plan_id}")
        self.assertEqual(status, 200)
        self.assertEqual(fetched["plan_id"], plan_id)
        self.assertEqual(fetched["plan"]["id"], plan_id)

    def test_plan_list_endpoint_uses_workflow_backend_plans(self):
        started = self.start_run("friends afternoon, four adults, activity before dinner")
        plan_id = started["plan_id"]

        status, listed = self.request("GET", "/api/plans")

        self.assertEqual(status, 200)
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["plans"][0]["id"], plan_id)
        self.assertEqual(listed["plans"][0]["status"], listed["plans"][0]["phase"])
        self.assertIn("created_at", listed["plans"][0])
        self.assertIn("updated_at", listed["plans"][0])
        self.assertIn("tags", listed["plans"][0])
        self.assertIn(listed["plans"][0]["phase"], {"pending_approval", "partially_completed"})

    def test_execute_legacy_endpoint_is_removed_with_selected_action_ids(self):
        started = self.start_run("write code for one hour")
        plan_id = started["plan_id"]
        status, plan = self.request("GET", f"/api/plans/{plan_id}")
        self.assertEqual(status, 200)
        action_id = plan["actions"][0]["action_id"]

        status, executed = self.request(
            "POST",
            f"/api/plans/{plan_id}/execute",
            {"confirmed": True, "selected_action_ids": [action_id], "idempotency_key": "test-idem-1"},
        )

        self.assertEqual(status, 404)
        self.assertEqual(executed["error"]["code"], "not_found")

    def test_invalid_json_returns_400_response(self):
        status, data = self.raw_request("POST", "/api/plans/runs", "{bad json")

        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "invalid_json")
        self.assertEqual(data["error"]["message"], "invalid_json")

    def test_remote_llm_failure_returns_500_without_template_plan(self):
        workflow = WorkflowService(
            repository_path=f"{self._tmp.name}/failing.sqlite",
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            ),
        )
        workflow.pipeline.chat_model = FailingChatModel()
        client = TestClient(create_app(workflow), raise_server_exceptions=False)

        response = client.post("/api/plans/runs", json={"goal": "friends dinner this afternoon"})

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["error"]["code"], "tool_failed")
        self.assertIn("LLM intent parsing failed", data["error"]["message"])

    def test_tool_schemas_endpoint(self):
        status, data = self.request("GET", "/api/tool-schemas")

        self.assertEqual(status, 200)
        self.assertEqual(len(data["tools"]), 20)

    def test_user_profile_endpoints(self):
        status, data = self.request("GET", "/api/users/test_user/profile")
        self.assertEqual(status, 200)

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


if __name__ == "__main__":
    unittest.main()
