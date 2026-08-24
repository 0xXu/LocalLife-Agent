from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator
from weakref import WeakValueDictionary

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from google.adk.sessions import DatabaseSessionService, InMemorySessionService

from backend.agent import DecisionEngine, GoogleAdkDecisionEngine
from backend.api.schemas import (
    CompensationRequest,
    DecisionSelectionRequest,
    MessageRequest,
    OutcomeCheckInRequest,
    PlanEditRequest,
    RealityEventRequest,
    StartTaskRequest,
    SupplyActionRequest,
)
from backend.config import Settings, get_settings
from backend.domain.models import (
    ActionKind,
    CompletionEvidence,
    DecisionBranch,
    FulfillmentCommand,
    FulfillmentEvent,
    GoalContractEdit,
    PlanEditIntent,
    PlanEditOperation,
    PreferenceFact,
    PreferenceFactEdit,
    RealityEvent,
    TaskSnapshot,
)
from backend.fulfillment import ExecutionModule, TemporalExecutionModule
from backend.live import LiveCompanionModule
from backend.memory import PostgresMemoryService
from backend.mcp import (
    CapabilityQueryOrchestrator,
    InProcessSupplyToolPort,
    StreamableHttpSupplyToolPort,
    discover_capability_catalog,
    load_capability_catalog,
)
from backend.planning import PlanningModule
from backend.preferences import PreferenceModule
from backend.storage import (
    DocumentConflictError,
    DocumentStore,
    InMemoryDocumentStore,
    PostgresDocumentStore,
)
from backend.supply import AiOutboundCallAdapter, SupplyLifecycleModule, SupplyTwin, TwinCallTransport
from backend.tasks import TaskModule

logger = logging.getLogger(__name__)


@dataclass
class AppContainer:
    settings: Settings
    store: DocumentStore
    supply: SupplyTwin
    lifecycle: SupplyLifecycleModule
    live: LiveCompanionModule
    planning: PlanningModule
    preferences: PreferenceModule
    tasks: TaskModule
    decision: DecisionEngine
    execution: ExecutionModule | None
    background: set[asyncio.Task] = field(default_factory=set)
    decision_tasks: dict[str, asyncio.Task] = field(default_factory=dict)
    live_monitors: dict[str, asyncio.Task] = field(default_factory=dict)
    task_locks: WeakValueDictionary[str, asyncio.Lock] = field(
        default_factory=WeakValueDictionary
    )

    def spawn(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self.background.add(task)
        task.add_done_callback(self.background.discard)

    def schedule_decision(self, task_id: str, message: str) -> None:
        previous = self.decision_tasks.get(task_id)
        if previous is not None and not previous.done():
            previous.cancel()
        task = asyncio.create_task(_advance_task(self, task_id, message))
        self.decision_tasks[task_id] = task
        self.background.add(task)

        def finished(done: asyncio.Task) -> None:
            self.background.discard(done)
            if self.decision_tasks.get(task_id) is done:
                self.decision_tasks.pop(task_id, None)

        task.add_done_callback(finished)

    def schedule_branch_decision(
        self,
        task_id: str,
        branch: DecisionBranch,
        selection_label: str,
    ) -> None:
        previous = self.decision_tasks.get(task_id)
        if previous is not None and not previous.done():
            previous.cancel()
        task = asyncio.create_task(
            _advance_branch(self, task_id, branch, selection_label)
        )
        self.decision_tasks[task_id] = task
        self.background.add(task)

        def finished(done: asyncio.Task) -> None:
            self.background.discard(done)
            if self.decision_tasks.get(task_id) is done:
                self.decision_tasks.pop(task_id, None)

        task.add_done_callback(finished)

    async def cancel_decision(self, task_id: str) -> None:
        current = self.decision_tasks.get(task_id)
        if current is not None and not current.done():
            current.cancel()
            await asyncio.gather(current, return_exceptions=True)

    def schedule_live_monitor(self, task_id: str) -> None:
        current = self.live_monitors.get(task_id)
        if current is not None and not current.done():
            return
        task = asyncio.create_task(_monitor_live_task(self, task_id))
        self.live_monitors[task_id] = task
        self.background.add(task)

        def finished(done: asyncio.Task) -> None:
            self.background.discard(done)
            if self.live_monitors.get(task_id) is done:
                self.live_monitors.pop(task_id, None)

        task.add_done_callback(finished)

    def task_lock(self, task_id: str) -> asyncio.Lock:
        lock = self.task_locks.get(task_id)
        if lock is None:
            lock = asyncio.Lock()
            self.task_locks[task_id] = lock
        return lock


async def _build_container(settings: Settings) -> AppContainer:
    store: DocumentStore
    if settings.use_in_memory_store:
        store = InMemoryDocumentStore()
    else:
        store = PostgresDocumentStore(settings.database_url)
    await store.initialize()

    supply = SupplyTwin(store, settings.supply_catalog_path or None)
    await supply.initialize()
    capability_catalog = (
        load_capability_catalog()
        if settings.use_in_memory_store
        else await discover_capability_catalog(settings.supply_mcp_url)
    )
    planning = PlanningModule(supply)
    preferences = PreferenceModule(store)
    outbound = (
        AiOutboundCallAdapter(settings, TwinCallTransport(supply))
        if settings.deepseek_api_key
        else None
    )
    if settings.use_in_memory_store:
        from backend.mcp import server as mcp_server

        mcp_server.twin = supply
        mcp_server.outbound = outbound
        mcp_server._initialized = True
        supply_tools = InProcessSupplyToolPort(mcp_server.mcp._tool_manager._tools)
    else:
        supply_tools = StreamableHttpSupplyToolPort(
            settings.supply_mcp_url,
            timeout_seconds=settings.supply_query_timeout_seconds,
        )
    query_orchestrator = CapabilityQueryOrchestrator(
        capability_catalog,
        supply_tools,
        timeout_seconds=settings.supply_query_timeout_seconds,
    )
    await query_orchestrator.start()
    lifecycle = SupplyLifecycleModule(store, supply, capability_catalog, outbound)
    live = LiveCompanionModule(capability_catalog)
    tasks = TaskModule(store, planning, preferences, lifecycle, live)
    memory = PostgresMemoryService(store)
    sessions = (
        InMemorySessionService()
        if settings.use_in_memory_store
        else DatabaseSessionService(db_url=settings.database_url)
    )
    decision = GoogleAdkDecisionEngine(
        settings=settings,
        planning=planning,
        tasks=tasks,
        session_service=sessions,
        memory_service=memory,
        capability_catalog=capability_catalog,
        query_orchestrator=query_orchestrator,
    )
    execution: ExecutionModule | None = None
    if settings.enable_temporal:
        execution = TemporalExecutionModule(settings, lifecycle, tasks)
        await execution.initialize()
    return AppContainer(
        settings=settings,
        store=store,
        supply=supply,
        lifecycle=lifecycle,
        live=live,
        planning=planning,
        preferences=preferences,
        tasks=tasks,
        decision=decision,
        execution=execution,
    )


async def _advance_task(
    container: AppContainer,
    task_id: str,
    message: str,
) -> None:
    task: TaskSnapshot | None = None
    try:
        task = await container.tasks.get(task_id)
        if task is None:
            return
        turn = await container.decision.decide(task, message)
        await container.tasks.apply_turn(task, turn)
    except asyncio.CancelledError:
        raise
    except DocumentConflictError:
        # A newer user message or decision turn already owns the task revision.
        return
    except Exception as exc:
        logger.exception("Agent decision failed for task %s", task_id)
        latest = await container.tasks.get(task_id)
        if latest is None or task is None or latest.revision != task.revision:
            return
        try:
            await container.tasks.fail_decision(
                latest,
                "这次代办没有顺利生成方案。你可以补充一句要求，我会重新开始。",
            )
        except DocumentConflictError:
            return


async def _advance_branch(
    container: AppContainer,
    task_id: str,
    branch: DecisionBranch,
    selection_label: str,
) -> None:
    task: TaskSnapshot | None = None
    try:
        task = await container.tasks.get(task_id)
        if task is None:
            return
        turn = await container.decision.decide_branch(task, branch, selection_label)
        await container.tasks.apply_turn(task, turn)
    except asyncio.CancelledError:
        raise
    except DocumentConflictError:
        return
    except Exception:
        logger.exception("Structured decision failed for task %s", task_id)
        latest = await container.tasks.get(task_id)
        if latest is None or task is None or latest.revision != task.revision:
            return
        try:
            await container.tasks.fail_decision(
                latest,
                "这个选择暂时没有形成可执行方案。你可以直接补充新的边界。",
            )
        except DocumentConflictError:
            return


async def _run_commands(
    container: AppContainer,
    task_id: str,
    commands: list[FulfillmentCommand],
) -> None:
    if not commands or container.execution is None:
        return
    async with container.task_lock(task_id):
        task = await container.tasks.get(task_id)
        if task is None:
            return
        for command in commands:
            task = await container.tasks.record_event(
                task,
                FulfillmentEvent(
                    task_id=task_id,
                    node_id=command.node_id,
                    action=command.action,
                    status="started",
                    detail="Temporal 已接收履约命令",
                ),
            )
    handle = await container.execution.start(commands)
    async with container.task_lock(task_id):
        task = await container.tasks.get(task_id)
        if task is None:
            return
        task = await container.tasks.set_workflow(task, handle.workflow_id)
    events = await handle.result()
    failed: FulfillmentEvent | None = None
    retry_commands: list[FulfillmentCommand] = []
    async with container.task_lock(task_id):
        task = await container.tasks.get(task_id)
        if task is None:
            return
        for event in events:
            task = await container.tasks.record_event(task, event)
            if event.status == "failed":
                failed = event
                break
        if failed:
            try:
                task, fallback_applied = await container.tasks.apply_policy_fallback(
                    task,
                    failed.node_id,
                )
                if fallback_applied and task.phase.value == "executing":
                    assert task.policy is not None
                    retry_commands = [
                        command
                        for command in container.planning.commands(
                            task.id,
                            task.policy.primary_plan,
                            transaction=task.transaction_confirmation,
                        )
                        if command.node_id == failed.node_id
                    ]
                elif not fallback_applied:
                    turn = await container.decision.decide(
                        task,
                        (
                            f"外部履约事件：{failed.detail}。保留已经完成的承诺，"
                            "重新读取供给并提出最小 PlanPatch。"
                        ),
                    )
                    await container.tasks.apply_turn(task, turn)
            except Exception as exc:
                await container.tasks.record_system_message(
                    task,
                    f"自动重规划未完成：{exc}",
                )
    if retry_commands:
        await _run_commands(container, task_id, retry_commands)


async def _monitor_live_task(container: AppContainer, task_id: str) -> None:
    """Wait on a durable Temporal observer and resume semantic recovery if needed."""
    if container.execution is None:
        return
    handle = await container.execution.start_observation(
        task_id,
        container.settings.live_observation_interval_seconds,
    )
    async with container.task_lock(task_id):
        task = await container.tasks.get(task_id)
        if task is None:
            return
        await container.tasks.set_observation_workflow(task, handle.workflow_id)
    result = await handle.result()
    unresolved = result.get("unresolved_node_ids", [])
    if unresolved:
        container.schedule_decision(
            task_id,
            (
                "Temporal 主动刷新发现现实变化，受影响节点为 "
                f"{', '.join(unresolved)}。保留其他承诺并生成最小 PlanPatch。"
            ),
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = await _build_container(active_settings)
        app.state.container = container
        yield
        for monitor in list(container.live_monitors.values()):
            monitor.cancel()
        if container.background:
            await asyncio.gather(*container.background, return_exceptions=True)
        if container.execution:
            await container.execution.close()
        await container.decision.close()

    app = FastAPI(
        title="Local Life Agent",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DocumentConflictError)
    async def document_conflict(_: Request, exc: DocumentConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "任务刚刚发生了变化，请基于最新状态重试。",
                "task_id": exc.key,
                "expected_revision": exc.expected_revision,
            },
        )

    def container(request: Request) -> AppContainer:
        return request.app.state.container

    @app.get("/api/health")
    async def health(request: Request) -> dict:
        scope = container(request)
        return {
            "status": "ok",
            "agent": "google-adk",
            "model": scope.settings.deepseek_model,
            "mcp": scope.settings.supply_mcp_url,
            "temporal": scope.execution is not None,
            "world_version": await scope.supply.world_version(),
        }

    @app.post("/api/tasks", response_model=TaskSnapshot, status_code=202)
    async def start_task(payload: StartTaskRequest, request: Request) -> TaskSnapshot:
        scope = container(request)
        task = await scope.tasks.start(payload.user_id, payload.goal)
        scope.schedule_decision(task.id, payload.goal)
        return task

    @app.get("/api/tasks", response_model=list[TaskSnapshot])
    async def list_tasks(request: Request, user_id: str = "demo-user") -> list[TaskSnapshot]:
        return await container(request).tasks.list_for_user(user_id)

    @app.get("/api/preferences", response_model=list[PreferenceFact])
    async def list_preferences(
        request: Request,
        user_id: str = "demo-user",
    ) -> list[PreferenceFact]:
        return await container(request).preferences.list(user_id)

    @app.patch("/api/preferences/{fact_id}", response_model=PreferenceFact)
    async def revise_preference(
        fact_id: str,
        payload: PreferenceFactEdit,
        request: Request,
        user_id: str = "demo-user",
    ) -> PreferenceFact:
        try:
            return await container(request).preferences.revise(user_id, fact_id, payload)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/tasks/{task_id}", response_model=TaskSnapshot)
    async def get_task(task_id: str, request: Request) -> TaskSnapshot:
        task = await container(request).tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task

    @app.post(
        "/api/tasks/{task_id}/messages",
        response_model=TaskSnapshot,
        status_code=202,
    )
    async def send_message(
        task_id: str,
        payload: MessageRequest,
        request: Request,
    ) -> TaskSnapshot:
        scope = container(request)
        await scope.cancel_decision(task_id)
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            task = await scope.tasks.add_user_message(task, payload.content)
        scope.schedule_decision(task.id, payload.content)
        return task

    @app.post(
        "/api/tasks/{task_id}/decisions",
        response_model=TaskSnapshot,
        status_code=202,
    )
    async def select_decision(
        task_id: str,
        payload: DecisionSelectionRequest,
        request: Request,
    ) -> TaskSnapshot:
        scope = container(request)
        await scope.cancel_decision(task_id)
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            try:
                task, branch, selection_label = await scope.tasks.select_decision_option(
                    task,
                    payload.option_id,
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if branch.action == "continue":
            scope.schedule_branch_decision(task.id, branch, selection_label)
        return task

    @app.patch(
        "/api/tasks/{task_id}/goal",
        response_model=TaskSnapshot,
        status_code=202,
    )
    async def edit_goal(
        task_id: str,
        payload: GoalContractEdit,
        request: Request,
    ) -> TaskSnapshot:
        scope = container(request)
        await scope.cancel_decision(task_id)
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            try:
                task, instruction = await scope.tasks.edit_goal(task, payload)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        scope.schedule_decision(task.id, instruction)
        return task

    @app.post(
        "/api/tasks/{task_id}/plan-edits",
        response_model=TaskSnapshot,
        status_code=202,
    )
    async def edit_plan(
        task_id: str,
        payload: PlanEditRequest,
        request: Request,
    ) -> TaskSnapshot:
        scope = container(request)
        await scope.cancel_decision(task_id)
        intent = PlanEditIntent(
            source="direct",
            instruction=payload.instruction,
            operation=payload.operation,
            node_id=payload.node_id,
            keep_other_nodes=payload.keep_other_nodes,
            starts_at=payload.starts_at,
            budget_yuan=payload.budget_yuan,
            option_id=payload.option_id,
            candidate_id=payload.candidate_id,
        )
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            try:
                task = await scope.tasks.apply_plan_edit(task, intent)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if task.pending_plan_edit is not None:
            scope.schedule_decision(task.id, intent.instruction)
        return task

    @app.post("/api/tasks/{task_id}/stop", response_model=TaskSnapshot)
    async def stop_task(task_id: str, request: Request) -> TaskSnapshot:
        scope = container(request)
        await scope.cancel_decision(task_id)
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            return await scope.tasks.stop_decision(task)

    @app.post("/api/tasks/{task_id}/mandate", response_model=TaskSnapshot)
    async def approve_mandate(task_id: str, request: Request) -> TaskSnapshot:
        scope = container(request)
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            task = await scope.tasks.approve_mandate(task)
            scope.schedule_live_monitor(task.id)
            commands = scope.planning.free_commands(
                task.id,
                task.policy.primary_plan,
            )
            if commands:
                if scope.execution is None:
                    raise HTTPException(status_code=503, detail="Temporal 未连接")
                scope.spawn(_run_commands(scope, task.id, commands))
            return task

    @app.post("/api/tasks/{task_id}/transaction", response_model=TaskSnapshot)
    async def confirm_transaction(task_id: str, request: Request) -> TaskSnapshot:
        scope = container(request)
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            task = await scope.tasks.confirm_transaction(task)
            scope.schedule_live_monitor(task.id)
            commands = scope.planning.paid_commands(
                task.id,
                task.policy.primary_plan,
                task.transaction_confirmation,
            )
            if commands:
                if scope.execution is None:
                    raise HTTPException(status_code=503, detail="Temporal 未连接")
                scope.spawn(_run_commands(scope, task.id, commands))
            return task

    @app.post("/api/tasks/{task_id}/compensations", response_model=TaskSnapshot)
    async def compensate(
        task_id: str,
        payload: CompensationRequest,
        request: Request,
    ) -> TaskSnapshot:
        scope = container(request)
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None or task.policy is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            source = next(
                (
                    event
                    for event in task.fulfillment_events
                    if event.id == payload.fulfillment_event_id
                    and event.status == "succeeded"
                ),
                None,
            )
            if source is None or source.compensation_action != payload.action:
                raise HTTPException(status_code=409, detail="补偿动作与原履约事件不匹配")
            node = next(
                item
                for item in task.policy.primary_plan.nodes
                if item.id == source.node_id
            )
            command = FulfillmentCommand(
                task_id=task.id,
                node_id=node.id,
                action=payload.action,
                option_id=node.option_id,
                amount_yuan=0,
                related_receipt_id=source.receipt_id,
            )
            if scope.execution is None:
                raise HTTPException(status_code=503, detail="Temporal 未连接")
            scope.spawn(_run_commands(scope, task.id, [command]))
            return task

    @app.post("/api/tasks/{task_id}/supply-actions", response_model=TaskSnapshot)
    async def supply_action(
        task_id: str,
        payload: SupplyActionRequest,
        request: Request,
    ) -> TaskSnapshot:
        scope = container(request)
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None or task.policy is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            node = next(
                (item for item in task.policy.primary_plan.nodes if item.id == payload.node_id),
                None,
            )
            if node is None or node.supply_reference is None:
                raise HTTPException(status_code=409, detail="节点没有可操作的供给承诺")
            capability = next(
                item
                for item in scope.lifecycle.catalog.capabilities
                if item.id == node.capability_id
            )
            allowed = {
                *capability.lifecycle.change_actions,
                *capability.lifecycle.compensation_actions.values(),
            }
            if payload.action not in allowed:
                raise HTTPException(status_code=409, detail="供给未发布此变更或售后动作")
            receipt_id = node.supply_reference.commitment_id
            if receipt_id is None:
                raise HTTPException(status_code=409, detail="节点还没有可变更的承诺")
            command = FulfillmentCommand(
                task_id=task.id,
                node_id=node.id,
                action=payload.action,
                option_id=node.option_id,
                amount_yuan=0,
                related_receipt_id=receipt_id,
            )
            if scope.execution is None:
                raise HTTPException(status_code=503, detail="Temporal 未连接")
            scope.spawn(_run_commands(scope, task.id, [command]))
            return task

    @app.get("/api/tasks/{task_id}/events")
    async def task_events(task_id: str, request: Request) -> StreamingResponse:
        scope = container(request)

        async def stream() -> AsyncIterator[str]:
            revision = -1
            progress_ids: set[str] = set()
            while not await request.is_disconnected():
                task = await scope.tasks.get(task_id)
                if task is None:
                    yield "event: error\ndata: {\"detail\":\"任务不存在\"}\n\n"
                    return
                if task.revision != revision:
                    for progress in task.progress_events:
                        if progress.id in progress_ids:
                            continue
                        progress_ids.add(progress.id)
                        progress_data = json.dumps(
                            progress.model_dump(mode="json"),
                            ensure_ascii=False,
                        )
                        yield f"id: {progress.revision}\nevent: progress\ndata: {progress_data}\n\n"
                    revision = task.revision
                    data = json.dumps(task.model_dump(mode="json"), ensure_ascii=False)
                    yield f"id: {task.revision}\nevent: task\ndata: {data}\n\n"
                await asyncio.sleep(0.75)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post(
        "/api/tasks/{task_id}/reality-events",
        response_model=TaskSnapshot,
        status_code=202,
    )
    async def report_reality_event(
        task_id: str,
        payload: RealityEventRequest,
        request: Request,
    ) -> TaskSnapshot:
        scope = container(request)
        await scope.cancel_decision(task_id)
        unresolved: list[str] = []
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            try:
                task, affected = await scope.tasks.record_reality_event(
                    task,
                    RealityEvent(
                        task_id=task_id,
                        kind=payload.kind,
                        detail=payload.detail,
                        magnitude=payload.magnitude,
                        node_id=payload.node_id,
                        supply_id=payload.supply_id,
                        location=payload.location,
                        completion_evidence=(
                            CompletionEvidence(
                                source=payload.completion_source or "user_confirmation",
                                detail=payload.detail,
                                provider_status=payload.provider_status,
                            )
                            if payload.kind == "node_completed"
                            else None
                        ),
                    ),
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            if payload.kind == "node_completed":
                return task
            if payload.kind == "user_late":
                task, applied = await scope.tasks.apply_user_delay(
                    task,
                    task.reality_events[-1],
                )
                if not applied:
                    unresolved.extend(affected)
            else:
                for node_id in affected:
                    task, applied = await scope.tasks.apply_policy_fallback(task, node_id)
                    if not applied:
                        unresolved.append(node_id)
        if unresolved:
            scope.schedule_decision(
                task.id,
                (
                    f"现实事件：{payload.detail}。受影响节点为 {', '.join(unresolved)}。"
                    "保留已完成和未受影响承诺，只生成必要的 PlanPatch。"
                ),
            )
        return task

    @app.post(
        "/api/tasks/{task_id}/outcome-check-in",
        response_model=TaskSnapshot,
    )
    async def outcome_check_in(
        task_id: str,
        payload: OutcomeCheckInRequest,
        request: Request,
    ) -> TaskSnapshot:
        scope = container(request)
        async with scope.task_lock(task_id):
            task = await scope.tasks.get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            try:
                return await scope.tasks.record_outcome_check_in(
                    task,
                    payload.response,
                    payload.note,
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/world")
    async def world(request: Request) -> dict:
        scope = container(request)
        return {
            "version": await scope.supply.world_version(),
            "options": [
                item.model_dump(mode="json")
                for item in await scope.supply.list_options()
            ],
        }

    @app.post("/api/world/scenarios/{scenario}")
    async def inject_world(scenario: str, request: Request) -> dict:
        scope = container(request)
        changed = await scope.supply.inject(scenario)
        affected_tasks: list[str] = []
        if changed is not None:
            for task in await scope.tasks.affected_by_supply(changed.id):
                assert task.policy is not None
                signals = await scope.lifecycle.observe_plan(task.policy.primary_plan)
                for signal in signals:
                    if signal.supply_id != changed.id:
                        continue
                    async with scope.task_lock(task.id):
                        latest = await scope.tasks.get(task.id)
                        if latest is None:
                            continue
                        latest = await scope.tasks.record_signal(latest, signal)
                        node = next(
                            item for item in latest.policy.primary_plan.nodes
                            if item.option_id == signal.supply_id
                        )
                        latest, fallback_applied = await scope.tasks.apply_policy_fallback(
                            latest,
                            node.id,
                        )
                    if not fallback_applied:
                        scope.schedule_decision(
                            task.id,
                            f"实时供给信号：{signal.detail}。保留未受影响的承诺，只重规划受影响节点。",
                        )
                    affected_tasks.append(task.id)
                    break
        return {
            "scenario": scenario,
            "world_version": await scope.supply.world_version(),
            "changed": changed.model_dump(mode="json") if changed else None,
            "affected_tasks": affected_tasks,
        }

    return app


app = create_app()
