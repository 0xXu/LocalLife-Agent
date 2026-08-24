import threading
import time

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import Settings
from backend.domain.models import AgentTurn, GoalContract, TurnKind


def test_health_and_world_control_use_the_same_supply_twin() -> None:
    app = create_app(Settings(use_in_memory_store=True, enable_temporal=False))
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["agent"] == "google-adk"
        assert health.json()["temporal"] is False

        before = client.get("/api/world").json()
        injected = client.post("/api/world/scenarios/price_jump")
        after = client.get("/api/world").json()
        assert injected.status_code == 200
        assert after["version"] == before["version"] + 1
        cinema = next(item for item in after["options"] if item["id"] == "activity_cinema")
        assert cinema["price_yuan"] == 176


def test_task_creation_returns_before_the_agent_decision_finishes() -> None:
    release = threading.Event()

    class DelayedDecisionEngine:
        async def decide(self, task, user_message):
            import asyncio

            await asyncio.to_thread(release.wait)
            return AgentTurn(
                kind=TurnKind.INFORM,
                message="暂不支持这个目标。",
                goal=GoalContract(
                    outcome=user_message,
                    city="上海",
                    origin="当前位置",
                    party_size=1,
                    budget_yuan=100,
                    deadline="23:00",
                ),
                )

        async def close(self):
            return None

    app = create_app(Settings(use_in_memory_store=True, enable_temporal=False))
    with TestClient(app) as client:
        app.state.container.decision = DelayedDecisionEngine()
        response = client.post(
            "/api/tasks",
            json={"user_id": "async-test", "goal": "今晚帮我安排一下"},
        )
        assert response.status_code == 202
        initial = response.json()
        assert initial["phase"] == "understanding"

        release.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            current = client.get(f"/api/tasks/{initial['id']}").json()
            if current["phase"] == "unsupported":
                break
            time.sleep(0.02)
        assert current["phase"] == "unsupported"


def test_running_decision_can_be_stopped_explicitly() -> None:
    class NeverFinishesDecisionEngine:
        async def decide(self, task, user_message):
            import asyncio

            await asyncio.Future()

        async def close(self):
            return None

    app = create_app(Settings(use_in_memory_store=True, enable_temporal=False))
    with TestClient(app) as client:
        app.state.container.decision = NeverFinishesDecisionEngine()
        started = client.post(
            "/api/tasks",
            json={"user_id": "stop-test", "goal": "慢慢安排今晚"},
        ).json()

        stopped = client.post(f"/api/tasks/{started['id']}/stop")

        assert stopped.status_code == 200
        assert stopped.json()["phase"] == "cancelled"
        assert client.get(f"/api/tasks/{started['id']}").json()["phase"] == "cancelled"


def test_new_message_cancels_the_obsolete_decision_turn() -> None:
    first_started = threading.Event()

    class CancelAwareDecisionEngine:
        calls = 0

        async def decide(self, task, user_message):
            import asyncio

            self.calls += 1
            if self.calls == 1:
                first_started.set()
                await asyncio.Future()
            return AgentTurn(
                kind=TurnKind.INFORM,
                message=f"采用最新要求：{user_message}",
                goal=GoalContract(
                    outcome=user_message,
                    city="上海",
                    origin="当前位置",
                    party_size=1,
                    budget_yuan=100,
                    deadline="23:00",
                ),
                )

        async def close(self):
            return None

    app = create_app(Settings(use_in_memory_store=True, enable_temporal=False))
    with TestClient(app) as client:
        engine = CancelAwareDecisionEngine()
        app.state.container.decision = engine
        started = client.post(
            "/api/tasks",
            json={"user_id": "revision-test", "goal": "先安排晚餐"},
        ).json()
        assert first_started.wait(timeout=1)

        revised = client.post(
            f"/api/tasks/{started['id']}/messages",
            json={"content": "改成只看电影"},
        )
        assert revised.status_code == 202

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            current = client.get(f"/api/tasks/{started['id']}").json()
            if current["phase"] == "unsupported":
                break
            time.sleep(0.02)
        assert current["messages"][-1]["content"] == "采用最新要求：改成只看电影"
        assert engine.calls == 2
