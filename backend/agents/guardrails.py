from __future__ import annotations

from typing import Any


def require_grounded_action(action: dict[str, Any]) -> dict[str, Any]:
    if not action.get("action_id"):
        raise ValueError("Action must include an action_id")
    if not action.get("tool"):
        raise ValueError("Action must include a tool")
    if not action.get("target"):
        raise ValueError("Action must include a target")
    return action
