from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class PlanFeedback:
    feedback_text: str
    selected_issue_codes: list[str] = field(default_factory=list)
    locked_nodes: list[str] = field(default_factory=list)
    removed_nodes: list[str] = field(default_factory=list)
    preference_updates: dict[str, Any] = field(default_factory=dict)
    save_to_profile: bool = False
    user_id: str = "local_demo_user"


@dataclass
class RevisionDelta:
    revision_id: str
    feedback_text: str
    constraint_updates: dict[str, Any]
    locked_nodes: list[str]
    removed_nodes: list[str]
    save_to_profile: bool
    user_id: str


def new_revision_delta(feedback: PlanFeedback) -> RevisionDelta:
    return RevisionDelta(
        revision_id=f"rev_{uuid4().hex[:10]}",
        feedback_text=feedback.feedback_text,
        constraint_updates=dict(feedback.preference_updates),
        locked_nodes=list(feedback.locked_nodes),
        removed_nodes=list(feedback.removed_nodes),
        save_to_profile=feedback.save_to_profile,
        user_id=feedback.user_id,
    )
