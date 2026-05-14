import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.llm.config import LLMConfig
from backend.services.planning_service import PlanningService
from backend.services.workflow_service import WorkflowService
from tests.backend.helpers import RuleBasedLLMClient, planning_service_with_fake_llm


class FailingLLMClient:
    def chat_stream(self, _messages):
        raise RuntimeError("LLM request timed out after 30 seconds.")


class BackendApiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        service = planning_service_with_fake_llm()
        workflow = self.workflow_service()
        self.client = TestClient(create_app(service, workflow_service=workflow))

    def tearDown(self):
        self._tmp.cleanup()

    def workflow_service(self):
        workflow = WorkflowService(
            repository_path=f"{self._tmp.name}/workflow.sqlite",
            llm_config=LLMConfig(
                base_url="https://example.test/v1",
                api_key="secret",
                model="test-model",
                remote_enabled=True,
            ),
        )
        workflow.pipeline.llm = RuleBasedLLMClient()
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

    def test_openapi_documents_required_paths(self):
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        for path in [
            "/api/health",
            "/api/plans/build",
            "/api/plans/{plan_id}",
            "/api/plans/{plan_id}/confirm",
            "/api/plans/{plan_id}/execute",
            "/api/plans/{plan_id}/recover",
            "/api/plans/{plan_id}/constraints",
            "/api/plans/{plan_id}/alternatives",
            "/api/tool-schemas",
            "/api/traces/{plan_id}",
        ]:
            self.assertIn(path, paths)

    def test_cors_preflight_allows_frontend_origin(self):
        response = self.client.options(
            "/api/plans/build",
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

    def test_build_and_disabled_execute_endpoints(self):
        status, built = self.request(
            "POST",
            "/api/plans/build",
            {"goal": "今天下午带 5 岁孩子出门，老婆减脂，别太远"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(built["plan"]["status"], "pending_approval")
        plan_id = built["plan"]["id"]

        status, executed = self.request(
            "POST",
            f"/api/plans/{plan_id}/execute",
            {"confirmed": True},
        )
        self.assertEqual(status, 410)
        self.assertEqual(executed["error"]["code"], "legacy_endpoint_disabled")

        status, fetched = self.request("GET", f"/api/plans/{plan_id}")
        self.assertEqual(status, 200)
        self.assertEqual(fetched["plan_id"], plan_id)
        self.assertEqual(fetched["plan"]["id"], plan_id)

    def test_plan_list_endpoint_uses_workflow_backend_plans(self):
        status, built = self.request(
            "POST",
            "/api/plans/build",
            {"goal": "今天下午朋友4个人出去玩，先活动再吃饭"},
        )
        self.assertEqual(status, 200)
        plan_id = built["plan"]["id"]

        status, listed = self.request("GET", "/api/plans")

        self.assertEqual(status, 200)
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["plans"][0]["id"], plan_id)
        self.assertEqual(listed["plans"][0]["status"], listed["plans"][0]["phase"])
        self.assertIn("created_at", listed["plans"][0])
        self.assertIn("updated_at", listed["plans"][0])
        self.assertIn("tags", listed["plans"][0])
        self.assertIn(listed["plans"][0]["phase"], {"pending_approval", "partially_completed"})

    def test_execute_legacy_endpoint_is_disabled_with_selected_action_ids(self):
        status, built = self.request("POST", "/api/plans/build", {"goal": "我想找个地方写代码一小时"})
        self.assertEqual(status, 200)
        plan_id = built["plan"]["id"]
        action_id = built["pending_actions"][0]["action_id"]

        status, executed = self.request(
            "POST",
            f"/api/plans/{plan_id}/execute",
            {"confirmed": True, "selected_action_ids": [action_id], "idempotency_key": "test-idem-1"},
        )

        self.assertEqual(status, 410)
        self.assertEqual(executed["error"]["code"], "legacy_endpoint_disabled")

    def test_invalid_json_returns_400_response(self):
        status, data = self.raw_request("POST", "/api/plans/build", "{bad json")

        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "invalid_json")
        self.assertEqual(data["error"]["message"], "invalid_json")

    def test_remote_llm_failure_returns_500_without_template_plan(self):
        service = PlanningService(
            llm_config=LLMConfig(
                base_url="https://token-plan-sgp.xiaomimimo.com/v1",
                api_key="secret-key-value",
                model="MiMo-V2.5-Pro",
                remote_enabled=True,
            )
        )
        service.pipeline.llm = FailingLLMClient()
        workflow = self.workflow_service()
        workflow.pipeline.llm = FailingLLMClient()
        client = TestClient(create_app(service, workflow_service=workflow), raise_server_exceptions=False)

        response = client.post("/api/plans/build", json={"goal": "friends dinner this afternoon"})

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["error"]["code"], "tool_failed")
        self.assertIn("LLM intent parsing failed", data["error"]["message"])


if __name__ == "__main__":
    unittest.main()
