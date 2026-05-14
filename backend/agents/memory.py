from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class MemoryItem:
    type: Literal["preference", "history", "poi_feedback"]
    content: dict[str, Any]
    source: Literal["user_explicit", "user_behavior", "agent_inferred", "system_observed"]
    confidence: float = 1.0
    created_at: str = ""
    updated_at: str = ""
    expires_at: str | None = None


class MemoryStore:
    """In-memory store for agent memory. First version — production should use persistent backend."""

    def __init__(self) -> None:
        self._preferences: dict[str, dict[str, Any]] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._poi_feedback: dict[str, list[dict[str, Any]]] = {}

    def put_preference(self, user_id: str, preferences: dict[str, Any]) -> None:
        """Store user preferences (hard memory)."""
        if user_id not in self._preferences:
            self._preferences[user_id] = {}
        self._preferences[user_id].update(preferences)

    def get_preference(self, user_id: str) -> dict[str, Any]:
        """Get user preferences."""
        return dict(self._preferences.get(user_id, {}))

    def add_history(self, user_id: str, entry: dict[str, Any]) -> None:
        """Add a recommendation history entry."""
        if user_id not in self._history:
            self._history[user_id] = []
        self._history[user_id].append(entry)

    def get_history(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent recommendation history."""
        return list(self._history.get(user_id, [])[-limit:])

    def add_poi_feedback(self, poi_id: str, feedback: dict[str, Any]) -> None:
        """Add feedback for a POI."""
        if poi_id not in self._poi_feedback:
            self._poi_feedback[poi_id] = []
        self._poi_feedback[poi_id].append(feedback)

    def get_poi_feedback(self, poi_id: str) -> list[dict[str, Any]]:
        """Get feedback for a POI."""
        return list(self._poi_feedback.get(poi_id, []))

    def build_context_message(self, user_id: str) -> str:
        """Build a context string from user memory for injection into agent prompts."""
        parts = []
        prefs = self.get_preference(user_id)
        if prefs:
            parts.append(f"User preferences: {json.dumps(prefs, ensure_ascii=False)}")
        history = self.get_history(user_id, limit=10)
        if history:
            parts.append(f"Recent choices: {json.dumps(history, ensure_ascii=False)}")
        if not parts:
            return "No prior memory available for this user."
        return "\n".join(parts)
