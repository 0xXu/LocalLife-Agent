from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserPreference:
    key: str
    value: Any
    source: str
    confidence: float
    scope: str
    evidence: str
    expires_at: str = ""
    user_editable: bool = True
    sensitive: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "scope": self.scope,
            "evidence": self.evidence,
            "expires_at": self.expires_at,
            "user_editable": self.user_editable,
            "sensitive": self.sensitive,
        }


@dataclass
class UserProfile:
    user_id: str
    explicit_preferences: list[UserPreference] = field(default_factory=list)
    learned_preferences: list[UserPreference] = field(default_factory=list)
    session_preferences: list[UserPreference] = field(default_factory=list)

    def all_preferences(self) -> list[UserPreference]:
        return [*self.learned_preferences, *self.explicit_preferences, *self.session_preferences]

    def preferences_by_key(self, key: str) -> list[UserPreference]:
        return [preference for preference in self.all_preferences() if preference.key == key]

    def preference_value(self, key: str, default=None):
        values = self.preferences_by_key(key)
        if not values:
            return default
        values.sort(key=lambda preference: (source_priority(preference.source), preference.confidence), reverse=True)
        return values[0].value

    def as_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "explicit_preferences": [item.as_dict() for item in self.explicit_preferences],
            "learned_preferences": [item.as_dict() for item in self.learned_preferences],
            "session_preferences": [item.as_dict() for item in self.session_preferences],
        }


def source_priority(source: str) -> int:
    return {"feedback": 1, "learned": 2, "explicit": 3, "session": 4}.get(source, 0)
