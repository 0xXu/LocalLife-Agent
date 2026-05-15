from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any

# ---------------------------------------------------------------------------
# SSE formatting helpers
# ---------------------------------------------------------------------------

def sse_event(event_id: str, event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"id: {event_id}\nevent: {event}\ndata: {payload}\n\n"


def progress_sse_event(event_id: str, step_label: str, step_detail: str, phase: str) -> str:
    """Return an SSE-formatted string for an intermediate progress update."""
    return sse_event(
        event_id,
        "graph_update",
        {
            "phase": phase,
            "step_label": step_label,
            "step_detail": step_detail,
            "is_final": False,
        },
    )

# ---------------------------------------------------------------------------
# Per-run event queue infrastructure
# ---------------------------------------------------------------------------

_QUEUE_TTL_SECONDS = 5 * 60  # 5 minutes


class _RunEventQueue:
    """Thread-safe event queue for a single pipeline run.

    Uses ``queue.Queue`` (stdlib) so that a synchronous worker thread can
    ``put()`` without worrying about event-loop affinity.  The async SSE
    endpoint can consume via ``get()`` called inside ``run_in_executor``.
    """

    def __init__(self) -> None:
        self._q: queue.Queue[str | None] = queue.Queue()
        self._created_at: float = time.monotonic()

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self._created_at

    @property
    def is_expired(self) -> bool:
        return self.age_seconds > _QUEUE_TTL_SECONDS

    def put(self, event: str) -> None:
        """Enqueue an SSE-formatted event string."""
        self._q.put(event)

    def get(self, timeout: float | None = None) -> str | None:
        """Dequeue an event.  Returns *None* if the sentinel is received
        (signalling the run is finished) or if *timeout* is exceeded.

        This is a blocking call – wrap it with
        ``loop.run_in_executor(None, q.get)`` from async code.
        """
        return self._q.get(timeout=timeout)

    def empty(self) -> bool:
        return self._q.empty()

    def close(self) -> None:
        """Push a ``None`` sentinel so any waiter unblocks."""
        self._q.put(None)


# Module-level registry of active run queues, keyed by run_id.
_run_queues: dict[str, _RunEventQueue] = {}
_run_queues_lock = threading.Lock()


def get_or_create_run_queue(run_id: str) -> _RunEventQueue:
    """Return the queue for *run_id*, creating one if it doesn't exist."""
    with _run_queues_lock:
        q = _run_queues.get(run_id)
        if q is None:
            q = _RunEventQueue()
            _run_queues[run_id] = q
        return q


def remove_run_queue(run_id: str) -> _RunEventQueue | None:
    """Remove and return the queue for *run_id*, if present."""
    with _run_queues_lock:
        return _run_queues.pop(run_id, None)


def has_run_queue(run_id: str) -> bool:
    """Return True if a queue for *run_id* currently exists."""
    with _run_queues_lock:
        return run_id in _run_queues


def cleanup_stale_queues() -> int:
    """Remove all expired queues.  Returns the number removed."""
    removed = 0
    with _run_queues_lock:
        stale = [rid for rid, q in _run_queues.items() if q.is_expired]
        for rid in stale:
            del _run_queues[rid]
            removed += 1
    return removed
