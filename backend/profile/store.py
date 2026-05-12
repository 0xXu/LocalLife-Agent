from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.profile.models import UserPreference, UserProfile


class UserProfileStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute("create table if not exists user_profiles (user_id text primary key, profile_json text not null)")

    def save(self, profile: UserProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                "insert or replace into user_profiles(user_id, profile_json) values (?, ?)",
                (profile.user_id, json.dumps(profile.as_dict(), ensure_ascii=False)),
            )

    def get(self, user_id: str) -> UserProfile:
        with self._connect() as conn:
            row = conn.execute("select profile_json from user_profiles where user_id = ?", (user_id,)).fetchone()
        if not row:
            return UserProfile(user_id=user_id)
        return profile_from_dict(json.loads(row[0]))


def profile_from_dict(data: dict) -> UserProfile:
    return UserProfile(
        user_id=data["user_id"],
        explicit_preferences=[preference_from_dict(item) for item in data.get("explicit_preferences", [])],
        learned_preferences=[preference_from_dict(item) for item in data.get("learned_preferences", [])],
        session_preferences=[preference_from_dict(item) for item in data.get("session_preferences", [])],
    )


def preference_from_dict(data: dict) -> UserPreference:
    return UserPreference(
        key=data["key"],
        value=data.get("value"),
        source=data.get("source", "learned"),
        confidence=float(data.get("confidence", 0.5)),
        scope=data.get("scope", "long_term"),
        evidence=data.get("evidence", ""),
        expires_at=data.get("expires_at", ""),
        user_editable=bool(data.get("user_editable", True)),
        sensitive=bool(data.get("sensitive", False)),
    )
