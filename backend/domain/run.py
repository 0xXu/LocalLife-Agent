from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanRunRequest:
    goal: str
    user_id: str = "local_demo_user"
    mode: str = "plan"


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    plan_id: str
    user_id: str
    goal: str
    status: str
    current_agent: str | None
    created_at: str
    updated_at: str
    error: dict | None = None
