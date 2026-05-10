import unittest

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.llm.config import LLMConfig
from backend.services.planning_service import PlanningService
from tests.backend.helpers import planning_service_with_fake_llm


class FailingLLMClient:
    def chat_stream(self, _messages):
        raise RuntimeError("LLM request timed out after 30 seconds.")


class BackendApiTest(unittest.TestCase):
    def setUp(self):
        service = planning_service_with_fake_llm()
        self.client = TestClient(create_app(service))

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

    def test_build_execute_and_recover_endpoints(self):
        status, built = self.request(
            "POST",
            "/api/plans/build",
            {"goal": "今天下午带 5 岁孩子出门，老婆减脂，别太远"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(built["plan"]["status"], "pending_confirmation")
        plan_id = built["plan"]["id"]

        status, executed = self.request(
            "POST",
            f"/api/plans/{plan_id}/execute",
            {"confirmed": True},
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(executed["receipts"]), 6)

        status, recovered = self.request(
            "POST",
            f"/api/plans/{plan_id}/recover",
            {"reason": "restaurant_unavailable"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(recovered["diff"]["changed"], "restaurant")

        status, traces = self.request("GET", f"/api/traces/{plan_id}")
        self.assertEqual(status, 200)
        self.assertEqual(traces["planId"], plan_id)
        self.assertGreaterEqual(len(traces["trace"]), 1)
        self.assertIn("tool_calls", traces)

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
        client = TestClient(create_app(service), raise_server_exceptions=False)

        response = client.post("/api/plans/build", json={"goal": "friends dinner this afternoon"})

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["error"]["code"], "tool_failed")
        self.assertIn("LLM intent parsing failed", data["error"]["message"])


if __name__ == "__main__":
    unittest.main()
