from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol


EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class PlanRunRequest:
    goal: str
    user_id: str = "local_demo_user"


@dataclass(frozen=True)
class ExecuteActionsRequest:
    action_ids: list[str]


@dataclass(frozen=True)
class RuntimeContext:
    run_id: str
    plan_id: str
    user_id: str


@dataclass(frozen=True)
class PlanRunResult:
    status: str
    plan: dict[str, Any]
    validation: dict[str, Any] = field(default_factory=dict)
    pending_actions: list[dict[str, Any]] = field(default_factory=list)
    raw_output: Any | None = None


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    receipts: list[dict[str, Any]] = field(default_factory=list)


class AgentRuntime(Protocol):
    async def start_plan(
        self,
        request: PlanRunRequest,
        context: RuntimeContext,
        sink: EventSink,
    ) -> PlanRunResult:
        ...

    async def execute_actions(
        self,
        request: ExecuteActionsRequest,
        context: RuntimeContext,
        sink: EventSink,
    ) -> ExecutionResult:
        ...
