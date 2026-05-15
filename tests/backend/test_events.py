"""Tests for backend.graph.events — SSE formatting and run-queue infrastructure."""

from __future__ import annotations

import json
import queue
import threading
import time

import pytest

from backend.graph.events import (
    _QUEUE_TTL_SECONDS,
    _RunEventQueue,
    _run_queues,
    cleanup_stale_queues,
    get_or_create_run_queue,
    progress_sse_event,
    remove_run_queue,
    sse_event,
)


# ---------------------------------------------------------------------------
# progress_sse_event
# ---------------------------------------------------------------------------


class TestProgressSseEvent:
    """Verify wire-format and payload shape of progress SSE events."""

    def test_wire_format_matches_spec(self) -> None:
        raw = progress_sse_event("e1", "Searching", "Querying hotels", "retrieval")
        assert raw == (
            'id: e1\n'
            'event: graph_update\n'
            'data: {"is_final":false,"phase":"retrieval","step_detail":"Querying hotels","step_label":"Searching"}\n'
            '\n'
        )

    def test_data_has_required_keys(self) -> None:
        raw = progress_sse_event("e2", "L", "D", "plan")
        # Extract the JSON payload line
        for line in raw.splitlines():
            if line.startswith("data: "):
                data = json.loads(line[len("data: "):])
                break
        else:
            pytest.fail("No data line found")

        assert data["phase"] == "plan"
        assert data["step_label"] == "L"
        assert data["step_detail"] == "D"
        assert data["is_final"] is False
        assert len(data) == 4, "Unexpected extra keys in progress payload"

    def test_sorted_keys_json(self) -> None:
        raw = progress_sse_event("e3", "a", "b", "c")
        for line in raw.splitlines():
            if line.startswith("data: "):
                payload = line[len("data: "):]
                break
        # Keys should be alphabetically sorted
        parsed = json.loads(payload)
        assert list(parsed.keys()) == sorted(parsed.keys())

    def test_ensure_ascii_false_preserves_unicode(self) -> None:
        raw = progress_sse_event("e4", "搜索", "查询酒店", "retrieval")
        assert "搜索" in raw
        assert "查询酒店" in raw

    def test_sse_event_compatibility(self) -> None:
        """progress_sse_event uses sse_event internally — verify event type."""
        raw = progress_sse_event("e5", "x", "y", "z")
        assert "event: graph_update\n" in raw


# ---------------------------------------------------------------------------
# _RunEventQueue
# ---------------------------------------------------------------------------


class TestRunEventQueue:
    """Unit tests for the per-run queue wrapper."""

    def test_put_get_roundtrip(self) -> None:
        q = _RunEventQueue()
        q.put("event-a")
        q.put("event-b")
        assert q.get(timeout=0.1) == "event-a"
        assert q.get(timeout=0.1) == "event-b"

    def test_empty_reflects_state(self) -> None:
        q = _RunEventQueue()
        assert q.empty() is True
        q.put("evt")
        assert q.empty() is False

    def test_close_pushes_sentinel(self) -> None:
        q = _RunEventQueue()
        q.close()
        assert q.get(timeout=0.1) is None

    def test_not_expired_initially(self) -> None:
        q = _RunEventQueue()
        assert q.is_expired is False

    def test_age_seconds_positive(self) -> None:
        q = _RunEventQueue()
        assert q.age_seconds >= 0

    def test_is_expired_after_ttl(self) -> None:
        q = _RunEventQueue()
        # Patch _created_at to simulate age
        q._created_at = time.monotonic() - _QUEUE_TTL_SECONDS - 1
        assert q.is_expired is True

    def test_get_blocks_until_put(self) -> None:
        """Verify a blocking get() unblocks when put() is called from another thread."""
        q = _RunEventQueue()
        result: list[str | None] = []

        def _getter() -> None:
            result.append(q.get(timeout=2.0))

        t = threading.Thread(target=_getter)
        t.start()
        time.sleep(0.05)
        q.put("delayed-event")
        t.join(timeout=3.0)
        assert result == ["delayed-event"]


# ---------------------------------------------------------------------------
# Module-level queue management
# ---------------------------------------------------------------------------


class _QueueRegistryIsolation:
    """Mixin that saves/restores the module-level ``_run_queues`` dict so
    tests don't leak state into each other."""

    @pytest.fixture(autouse=True)
    def _isolate_registry(self):
        saved = dict(_run_queues)
        _run_queues.clear()
        yield
        _run_queues.clear()
        _run_queues.update(saved)


class TestGetOrCreateRunQueue(_QueueRegistryIsolation):
    def test_creates_new_queue(self) -> None:
        q = get_or_create_run_queue("run-1")
        assert isinstance(q, _RunEventQueue)
        assert "run-1" in _run_queues

    def test_returns_existing_queue(self) -> None:
        q1 = get_or_create_run_queue("run-2")
        q2 = get_or_create_run_queue("run-2")
        assert q1 is q2

    def test_different_runs_get_different_queues(self) -> None:
        q1 = get_or_create_run_queue("run-a")
        q2 = get_or_create_run_queue("run-b")
        assert q1 is not q2


class TestRemoveRunQueue(_QueueRegistryIsolation):
    def test_removes_existing(self) -> None:
        get_or_create_run_queue("run-x")
        removed = remove_run_queue("run-x")
        assert isinstance(removed, _RunEventQueue)
        assert "run-x" not in _run_queues

    def test_returns_none_for_missing(self) -> None:
        assert remove_run_queue("no-such-run") is None


class TestCleanupStaleQueues(_QueueRegistryIsolation):
    def test_removes_expired_queues(self) -> None:
        q = get_or_create_run_queue("stale")
        q._created_at = time.monotonic() - _QUEUE_TTL_SECONDS - 1
        removed = cleanup_stale_queues()
        assert removed == 1
        assert "stale" not in _run_queues

    def test_keeps_fresh_queues(self) -> None:
        get_or_create_run_queue("fresh")
        removed = cleanup_stale_queues()
        assert removed == 0
        assert "fresh" in _run_queues

    def test_mixed_stale_and_fresh(self) -> None:
        q_stale = get_or_create_run_queue("old")
        q_stale._created_at = time.monotonic() - _QUEUE_TTL_SECONDS - 100
        get_or_create_run_queue("new")
        removed = cleanup_stale_queues()
        assert removed == 1
        assert "old" not in _run_queues
        assert "new" in _run_queues

    def test_returns_zero_when_empty(self) -> None:
        assert cleanup_stale_queues() == 0
