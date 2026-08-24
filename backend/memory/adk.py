from __future__ import annotations

from collections.abc import Sequence

from google.adk.memory import BaseMemoryService
from google.adk.memory.base_memory_service import SearchMemoryResponse
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.sessions import Session
from google.genai import types

from backend.domain.models import PreferenceFact
from backend.storage import DocumentStore


class PostgresMemoryService(BaseMemoryService):
    """ADK memory interface over the application's evidence-backed memory records."""

    namespace = "preference_facts"

    def __init__(self, store: DocumentStore) -> None:
        self.store = store

    async def add_session_to_memory(self, _session: Session) -> None:
        # Durable preferences are admitted only through typed task evidence.
        return None

    async def add_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        memories: Sequence[MemoryEntry],
        custom_metadata=None,
    ) -> None:
        # ADK sessions are intentionally not a second preference write path.
        return None

    async def search_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        query: str,
    ) -> SearchMemoryResponse:
        facts = [
            PreferenceFact.model_validate(item)
            for item in await self.store.scan(self.namespace)
            if item.get("user_id") == user_id and item.get("active", True)
        ]
        tokens = {item.lower() for item in query.replace("，", " ").split() if len(item) > 1}
        ranked: list[tuple[int, PreferenceFact]] = []
        for item in facts:
            haystack = f"{item.dimension} {item.preference} {item.context_scope}".lower()
            score = sum(token in haystack for token in tokens)
            ranked.append((score, item))
        ranked.sort(key=lambda pair: (pair[0], pair[1].confidence), reverse=True)
        entries = [
            MemoryEntry(
                id=f"memory-{index}",
                author="user-memory",
                content=types.Content(
                    role="user",
                    parts=[types.Part(text=item.preference)],
                ),
                custom_metadata={
                    "source": item.source,
                    "scope": item.context_scope,
                    "confidence": item.confidence,
                },
            )
            for index, (_, item) in enumerate(ranked[:8])
        ]
        return SearchMemoryResponse(memories=entries)
