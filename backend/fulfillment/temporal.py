from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Protocol
from uuid import uuid4

from temporalio import activity, workflow
from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy
from temporalio.worker import Worker

from backend.config import Settings
from backend.domain.models import FulfillmentCommand, FulfillmentEvent


@workflow.defn
class LiveObservationWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        while True:
            result = await workflow.execute_activity(
                "observe_live_task",
                payload["task_id"],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    backoff_coefficient=2,
                    maximum_attempts=3,
                ),
            )
            if not result["active"] or result["unresolved_node_ids"]:
                return result
            await workflow.sleep(timedelta(seconds=payload["interval_seconds"]))


@workflow.defn
class FulfillmentWorkflow:
    @workflow.run
    async def run(self, commands: list[dict]) -> list[dict]:
        events: list[dict] = []
        for command in commands:
            event = await workflow.execute_activity(
                "execute_supply_action",
                command,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    backoff_coefficient=2,
                    maximum_attempts=3,
                ),
            )
            events.append(event)
            if event["status"] == "failed":
                break
        return events


class LifecycleActivities:
    def __init__(self, lifecycle, tasks) -> None:
        self.lifecycle = lifecycle
        self.tasks = tasks

    @activity.defn(name="execute_supply_action")
    async def execute_supply_action(self, payload: dict) -> dict:
        command = FulfillmentCommand.model_validate(payload)
        await asyncio.sleep(0.35)
        event = await self.lifecycle.execute(command)
        return event.model_dump(mode="json")

    @activity.defn(name="observe_live_task")
    async def observe_live_task(self, task_id: str) -> dict:
        task = await self.tasks.get(task_id)
        if task is None or task.policy is None:
            return {"active": False, "unresolved_node_ids": []}
        if task.phase.value not in {"awaiting_transaction", "executing"}:
            return {"active": False, "unresolved_node_ids": []}
        signals = await self.lifecycle.observe_plan(task.policy.primary_plan)
        if not signals:
            task.live = self.tasks.live.evolve(task)
            await self.tasks.save_live_refresh(task)
            return {"active": True, "unresolved_node_ids": []}
        unresolved: list[str] = []
        for signal in signals:
            task = await self.tasks.record_signal(task, signal)
            node = next(
                item
                for item in task.policy.primary_plan.nodes
                if item.option_id == signal.supply_id
            )
            task, applied = await self.tasks.apply_policy_fallback(task, node.id)
            if not applied:
                unresolved.append(node.id)
        return {"active": not unresolved, "unresolved_node_ids": unresolved}


class ExecutionHandle(Protocol):
    workflow_id: str

    async def result(self) -> list[FulfillmentEvent]: ...


class ExecutionModule(Protocol):
    async def initialize(self) -> None: ...
    async def start(self, commands: list[FulfillmentCommand]) -> ExecutionHandle: ...
    async def start_observation(
        self,
        task_id: str,
        interval_seconds: int,
    ) -> "TemporalObservationHandle": ...
    async def close(self) -> None: ...


class TemporalExecutionHandle:
    def __init__(self, workflow_id: str, handle: WorkflowHandle) -> None:
        self.workflow_id = workflow_id
        self.handle = handle

    async def result(self) -> list[FulfillmentEvent]:
        payloads = await self.handle.result()
        return [FulfillmentEvent.model_validate(item) for item in payloads]


class TemporalObservationHandle:
    def __init__(self, workflow_id: str, handle: WorkflowHandle) -> None:
        self.workflow_id = workflow_id
        self.handle = handle

    async def result(self) -> dict:
        return await self.handle.result()


class TemporalExecutionModule:
    """Runs every external commitment inside one durable Temporal workflow."""

    def __init__(self, settings: Settings, lifecycle, tasks) -> None:
        self.settings = settings
        self.lifecycle = lifecycle
        self.tasks = tasks
        self.client: Client | None = None
        self.worker: Worker | None = None
        self.worker_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        self.client = await Client.connect(
            self.settings.temporal_address,
            namespace=self.settings.temporal_namespace,
        )
        activities = LifecycleActivities(self.lifecycle, self.tasks)
        self.worker = Worker(
            self.client,
            task_queue=self.settings.temporal_task_queue,
            workflows=[FulfillmentWorkflow, LiveObservationWorkflow],
            activities=[
                activities.execute_supply_action,
                activities.observe_live_task,
            ],
        )
        self.worker_task = asyncio.create_task(self.worker.run())

    async def start(self, commands: list[FulfillmentCommand]) -> TemporalExecutionHandle:
        if self.client is None:
            raise RuntimeError("Temporal execution module is not initialized")
        workflow_id = f"fulfillment-{commands[0].task_id}-{uuid4().hex[:8]}"
        handle = await self.client.start_workflow(
            FulfillmentWorkflow.run,
            [item.model_dump(mode="json") for item in commands],
            id=workflow_id,
            task_queue=self.settings.temporal_task_queue,
        )
        return TemporalExecutionHandle(workflow_id, handle)

    async def start_observation(
        self,
        task_id: str,
        interval_seconds: int,
    ) -> TemporalObservationHandle:
        if self.client is None:
            raise RuntimeError("Temporal execution module is not initialized")
        workflow_id = f"observe-{task_id}-{uuid4().hex[:8]}"
        handle = await self.client.start_workflow(
            LiveObservationWorkflow.run,
            {"task_id": task_id, "interval_seconds": interval_seconds},
            id=workflow_id,
            task_queue=self.settings.temporal_task_queue,
        )
        return TemporalObservationHandle(workflow_id, handle)

    async def close(self) -> None:
        if self.worker:
            await self.worker.shutdown()
        if self.worker_task:
            await self.worker_task
