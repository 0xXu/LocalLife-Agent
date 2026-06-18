import json
import unittest

from backend.domain.events import (
    RUN_STATUS_RUNNING,
    RUN_STATUS_COMPLETED,
    RunEvent,
    format_sse_event,
)


class RunEventDomainTest(unittest.TestCase):
    def test_run_event_serializes_with_stable_envelope(self):
        event = RunEvent(
            event_id="evt_000001",
            run_id="run_1",
            plan_id="plan_1",
            seq=1,
            type="run.started",
            timestamp="2026-06-19T00:00:00Z",
            payload={"status": RUN_STATUS_RUNNING},
        )

        data = event.to_dict()

        self.assertEqual(data["type"], "run.started")
        self.assertEqual(data["run_id"], "run_1")
        self.assertEqual(data["plan_id"], "plan_1")
        self.assertEqual(data["seq"], 1)
        self.assertEqual(data["payload"], {"status": RUN_STATUS_RUNNING})

    def test_format_sse_event_uses_run_event_name(self):
        event = RunEvent(
            event_id="evt_000002",
            run_id="run_1",
            plan_id=None,
            seq=2,
            type="run.completed",
            timestamp="2026-06-19T00:00:01Z",
            payload={"status": RUN_STATUS_COMPLETED},
        )

        raw = format_sse_event(event)

        self.assertTrue(raw.startswith("id: evt_000002\nevent: run.event\n"))
        self.assertTrue(raw.endswith("\n\n"))
        data_line = [line for line in raw.splitlines() if line.startswith("data: ")][0]
        decoded = json.loads(data_line.removeprefix("data: "))
        self.assertEqual(decoded["type"], "run.completed")
        self.assertEqual(decoded["payload"]["status"], RUN_STATUS_COMPLETED)
