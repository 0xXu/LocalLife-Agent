from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.domain.events import RunEvent, format_sse_event


class EventStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        self._queues: dict[str, asyncio.Queue[str | None]] = {}
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists run_events (
                    event_id text primary key,
                    run_id text not null,
                    plan_id text,
                    seq integer not null,
                    event_type text not null,
                    payload_json text not null,
                    created_at text not null,
                    unique(run_id, seq)
                )
                """
            )

    def open_queue(self, run_id: str) -> None:
        self._queues.setdefault(run_id, asyncio.Queue())

    def close_queue(self, run_id: str) -> None:
        queue = self._queues.get(run_id)
        if queue is not None:
            queue.put_nowait(None)

    def append(self, run_id: str, plan_id: str | None, event_type: str, payload: dict[str, Any]) -> RunEvent:
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            row = conn.execute(
                "select coalesce(max(seq), 0) + 1 as next_seq from run_events where run_id = ?",
                (run_id,),
            ).fetchone()
            seq = int(row["next_seq"])
            event_id = f"evt_{seq:06d}"
            conn.execute(
                """
                insert into run_events(event_id, run_id, plan_id, seq, event_type, payload_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, run_id, plan_id, seq, event_type, json.dumps(payload, ensure_ascii=False), created_at),
            )
        event = RunEvent(event_id, run_id, plan_id, seq, event_type, created_at, payload)
        queue = self._queues.get(run_id)
        if queue is not None:
            queue.put_nowait(format_sse_event(event))
        return event

    def replay(self, run_id: str, after_seq: int = 0) -> list[RunEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select event_id, run_id, plan_id, seq, event_type, payload_json, created_at
                from run_events
                where run_id = ? and seq > ?
                order by seq asc
                """,
                (run_id, after_seq),
            ).fetchall()
        return [
            RunEvent(
                row["event_id"],
                row["run_id"],
                row["plan_id"],
                int(row["seq"]),
                row["event_type"],
                row["created_at"],
                json.loads(row["payload_json"]),
            )
            for row in rows
        ]

    async def next_sse(self, run_id: str) -> str | None:
        queue = self._queues.get(run_id)
        if queue is None:
            return None
        return await queue.get()
