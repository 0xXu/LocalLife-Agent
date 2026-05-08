import http.client
import json
import threading
import unittest

from backend.api.app import create_server


class BackendApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read().decode("utf-8")
        conn.close()
        return response.status, json.loads(data)

    def test_health_endpoint(self):
        status, data = self.request("GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertGreaterEqual(data["agents"], 7)

    def test_build_execute_and_recover_endpoints(self):
        status, built = self.request(
            "POST",
            "/api/plans/build",
            {"goal": "今天下午带 5 岁孩子出门，老婆减脂，别太远"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(built["plan"]["status"], "ready_for_confirmation")
        plan_id = built["plan"]["id"]

        status, executed = self.request(
            "POST",
            f"/api/plans/{plan_id}/execute",
            {"confirmed": True},
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(executed["receipts"]), 3)

        status, recovered = self.request(
            "POST",
            f"/api/plans/{plan_id}/recover",
            {"reason": "restaurant_unavailable"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(recovered["diff"]["changed"], "restaurant")


if __name__ == "__main__":
    unittest.main()
