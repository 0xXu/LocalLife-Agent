import asyncio
import unittest
from tempfile import TemporaryDirectory

from backend.domain.events import RUN_STATUS_RUNNING
from backend.infrastructure.event_store import EventStore


class EventStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.store = EventStore(f"{self.tmp.name}/events.sqlite")

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_persists_ordered_events(self):
        first = self.store.append("run_1", "plan_1", "run.started", {"status": RUN_STATUS_RUNNING})
        second = self.store.append("run_1", "plan_1", "agent.started", {"agent": "planner"})

        self.assertEqual(first.seq, 1)
        self.assertEqual(second.seq, 2)
        replayed = self.store.replay("run_1")
        self.assertEqual([event.type for event in replayed], ["run.started", "agent.started"])

    def test_active_queue_receives_formatted_sse(self):
        self.store.open_queue("run_1")
        event = self.store.append("run_1", None, "run.started", {})

        async def read_once():
            return await self.store.next_sse("run_1")

        raw = asyncio.run(read_once())
        self.assertIn(f"id: {event.event_id}", raw)
        self.assertIn("event: run.event", raw)
