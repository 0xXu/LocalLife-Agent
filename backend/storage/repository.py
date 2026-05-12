from __future__ import annotations

import pickle
import sqlite3
from pathlib import Path
from typing import Any


class PlanRepository:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute("create table if not exists plans (plan_id text primary key, state_blob blob not null)")

    def save_state(self, plan_id: str, state: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                "insert or replace into plans(plan_id, state_blob) values (?, ?)",
                (plan_id, sqlite3.Binary(pickle.dumps(state))),
            )

    def get_state(self, plan_id: str) -> Any | None:
        with self._connect() as conn:
            row = conn.execute("select state_blob from plans where plan_id = ?", (plan_id,)).fetchone()
        return pickle.loads(row[0]) if row else None

    def list_states(self) -> list[Any]:
        with self._connect() as conn:
            rows = conn.execute("select state_blob from plans order by rowid").fetchall()
        return [pickle.loads(row[0]) for row in rows]
