from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from backend.services import PlanningService


def create_server(host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    service = PlanningService()

    class Handler(WeekendPilotHandler):
        planning_service = service

    return ThreadingHTTPServer((host, port), Handler)


class WeekendPilotHandler(BaseHTTPRequestHandler):
    planning_service: PlanningService

    def do_OPTIONS(self) -> None:
        self.respond_json({})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self.respond_json({"status": "ok", "service": "weekendpilot-backend", "agents": 8})
            return
        if path.startswith("/api/traces/"):
            plan_id = path.rsplit("/", 1)[-1]
            self.respond_json({"plan_id": plan_id, "trace": self.planning_service.get_trace(plan_id)})
            return
        self.respond_json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self.read_json()
        try:
            if path == "/api/plans/build":
                self.respond_json(self.planning_service.build_plan(str(body.get("goal", ""))))
                return
            if path.startswith("/api/plans/") and path.endswith("/execute"):
                plan_id = path.split("/")[3]
                self.respond_json(self.planning_service.execute_plan(plan_id, bool(body.get("confirmed"))))
                return
            if path.startswith("/api/plans/") and path.endswith("/recover"):
                plan_id = path.split("/")[3]
                reason = str(body.get("reason", "restaurant_unavailable"))
                self.respond_json(self.planning_service.recover_plan(plan_id, reason))
                return
        except PermissionError as exc:
            self.respond_json({"error": str(exc)}, status=403)
            return
        except KeyError as exc:
            self.respond_json({"error": str(exc)}, status=404)
            return
        self.respond_json({"error": "not_found"}, status=404)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def respond_json(self, payload: dict | list, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    server = create_server()
    print("WeekendPilot backend listening on http://127.0.0.1:8787")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
