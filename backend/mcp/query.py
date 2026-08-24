from __future__ import annotations

import asyncio
import json
import time
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any, Protocol

from jsonschema import Draft202012Validator
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from backend.domain.models import SupplyOption
from backend.mcp.catalog import CapabilityCatalog
from backend.mcp.schemas import (
    CapabilityEvidence,
    CapabilityQueryPlan,
    CapabilityToolQuery,
    SupplyCallTrace,
    ToolEnvelope,
)


class SupplyToolPort(Protocol):
    """Seam for provider-owned tool discovery and invocation."""

    async def start(self) -> None: ...

    async def list_tools(self) -> dict[str, dict[str, Any]]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolEnvelope: ...

    async def close(self) -> None: ...


class StreamableHttpSupplyToolPort:
    """One application-scoped MCP connection shared by all supply queries."""

    def __init__(self, url: str, *, timeout_seconds: float = 10) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._tool_schemas: dict[str, dict[str, Any]] = {}
        self._start_lock = asyncio.Lock()

    async def start(self) -> None:
        if self._session is not None:
            return
        async with self._start_lock:
            if self._session is not None:
                return
            stack = AsyncExitStack()
            try:
                read, write, _ = await stack.enter_async_context(
                    streamablehttp_client(
                        self.url,
                        timeout=self.timeout_seconds,
                        sse_read_timeout=120,
                    )
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                listed = await session.list_tools()
            except BaseException:
                await stack.aclose()
                raise
            self._stack = stack
            self._session = session
            self._tool_schemas = {
                tool.name: {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                }
                for tool in listed.tools
            }

    async def list_tools(self) -> dict[str, dict[str, Any]]:
        await self.start()
        return dict(self._tool_schemas)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolEnvelope:
        await self.start()
        if self._session is None:
            raise RuntimeError("MCP supply session did not initialize")
        result = await self._session.call_tool(
            name,
            arguments,
            read_timeout_seconds=timedelta(seconds=self.timeout_seconds),
        )
        if result.isError:
            detail = "；".join(
                getattr(item, "text", "") for item in result.content
                if getattr(item, "text", "")
            )
            raise RuntimeError(detail or f"MCP tool failed: {name}")
        payload = getattr(result, "structuredContent", None)
        if payload is None:
            text = next(
                (
                    getattr(item, "text", "")
                    for item in result.content
                    if getattr(item, "text", "")
                ),
                "",
            )
            if not text:
                raise ValueError(f"MCP tool returned no structured content: {name}")
            payload = json.loads(text)
        return ToolEnvelope.model_validate(payload)

    async def close(self) -> None:
        stack, self._stack = self._stack, None
        self._session = None
        self._tool_schemas = {}
        if stack is not None:
            await stack.aclose()


class InProcessSupplyToolPort:
    """Local adapter used by the in-memory app and module tests."""

    def __init__(self, tools: dict[str, Any]) -> None:
        self._tools = tools

    async def start(self) -> None:
        return None

    async def list_tools(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "name": name,
                "description": tool.description or "",
                "input_schema": tool.parameters,
            }
            for name, tool in self._tools.items()
        }

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolEnvelope:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"unknown in-process MCP tool: {name}")
        payload = await tool.run(arguments, convert_result=False)
        return ToolEnvelope.model_validate(payload)

    async def close(self) -> None:
        return None


class CapabilityQueryOrchestrator:
    """Resolve a semantic query plan into immutable provider evidence."""

    def __init__(
        self,
        catalog: CapabilityCatalog,
        tools: SupplyToolPort,
        *,
        timeout_seconds: float = 10,
    ) -> None:
        self.catalog = catalog
        self.tools = tools
        self.timeout_seconds = timeout_seconds
        self._schemas: dict[str, dict[str, Any]] = {}

    async def start(self) -> None:
        await self.tools.start()
        self._schemas = await self.tools.list_tools()
        published = {
            tool
            for capability in self.catalog.capabilities
            for tool in capability.retrieval.entry_tools
        }
        missing = published - set(self._schemas)
        if missing:
            raise ValueError(f"MCP server does not publish retrieval tools: {sorted(missing)}")

    def protocol_description(self) -> list[dict[str, Any]]:
        """Stable model-facing retrieval interface for the system prompt prefix."""
        definitions = []
        for capability in self.catalog.capabilities:
            definitions.append({
                "capability_id": capability.id,
                "entry_tools": [
                    self._schemas.get(tool_name, {"name": tool_name})
                    for tool_name in capability.retrieval.entry_tools
                ],
            })
        return definitions

    def validate_plan(self, plan: CapabilityQueryPlan, capability_ids: list[str]) -> None:
        selected = {
            item.id: item for item in self.catalog.select(capability_ids)
        }
        query_capabilities = {query.capability_id for query in plan.queries}
        if query_capabilities != set(selected):
            raise ValueError(
                "query plan must cover every selected capability exactly by id: "
                f"expected={sorted(selected)}, actual={sorted(query_capabilities)}"
            )
        for query in plan.queries:
            capability = selected[query.capability_id]
            if query.tool_name not in capability.retrieval.entry_tools:
                raise ValueError(
                    f"{query.tool_name!r} is not a retrieval entry tool for "
                    f"{query.capability_id!r}"
                )
            schema = self._schemas.get(query.tool_name, {}).get("input_schema")
            if schema:
                Draft202012Validator(schema).validate(query.arguments)

    async def resolve(
        self,
        plan: CapabilityQueryPlan,
        capability_ids: list[str],
    ) -> dict[str, CapabilityEvidence]:
        self.validate_plan(plan, capability_ids)

        async def execute(query: CapabilityToolQuery) -> tuple[str, ToolEnvelope, SupplyCallTrace]:
            started = time.perf_counter()
            envelope = await self.tools.call_tool(query.tool_name, query.arguments)
            trace = SupplyCallTrace(
                tool_name=query.tool_name,
                arguments=query.arguments,
                status=envelope.status,
                item_count=len(envelope.items),
                world_version=envelope.world_version,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            return query.capability_id, envelope, trace

        async with asyncio.timeout(self.timeout_seconds):
            results = await asyncio.gather(*(execute(query) for query in plan.queries))
        grouped: dict[str, CapabilityEvidence] = {
            capability_id: CapabilityEvidence(capability_id=capability_id)
            for capability_id in capability_ids
        }
        seen: dict[str, set[tuple[str, str, tuple[str, ...]]]] = {
            capability_id: set() for capability_id in capability_ids
        }
        for capability_id, envelope, trace in results:
            evidence = grouped[capability_id]
            evidence.calls.append(trace)
            evidence.warnings.extend(envelope.warnings)
            for raw in envelope.items:
                try:
                    option = SupplyOption.model_validate(raw)
                except ValueError as error:
                    raise ValueError(
                        f"{trace.tool_name} returned an invalid SupplyOption"
                    ) from error
                identity = (option.id, option.venue, tuple(option.time_slots))
                if identity in seen[capability_id]:
                    continue
                seen[capability_id].add(identity)
                evidence.candidates.append(option)
        return grouped

    async def close(self) -> None:
        await self.tools.close()
