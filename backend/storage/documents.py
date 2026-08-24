from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class DocumentConflictError(RuntimeError):
    """The document changed after the caller read it."""

    def __init__(self, namespace: str, key: str, expected_revision: int) -> None:
        super().__init__(
            f"{namespace}/{key} changed after revision {expected_revision}"
        )
        self.namespace = namespace
        self.key = key
        self.expected_revision = expected_revision


class DocumentStore(Protocol):
    async def initialize(self) -> None: ...
    async def load(self, namespace: str, key: str) -> dict[str, Any] | None: ...
    async def save(
        self,
        namespace: str,
        key: str,
        payload: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> int: ...
    async def scan(self, namespace: str) -> list[dict[str, Any]]: ...


class InMemoryDocumentStore:
    def __init__(self) -> None:
        self._documents: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self._revisions: dict[tuple[str, str], int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        return None

    async def load(self, namespace: str, key: str) -> dict[str, Any] | None:
        async with self._lock:
            value = self._documents[namespace].get(key)
            return json.loads(json.dumps(value, default=str)) if value is not None else None

    async def save(
        self,
        namespace: str,
        key: str,
        payload: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> int:
        async with self._lock:
            current = self._documents[namespace].get(key)
            if expected_revision is not None and (
                current is None or current.get("revision") != expected_revision
            ):
                raise DocumentConflictError(namespace, key, expected_revision)
            self._documents[namespace][key] = json.loads(json.dumps(payload, default=str))
            self._revisions[(namespace, key)] += 1
            return self._revisions[(namespace, key)]

    async def scan(self, namespace: str) -> list[dict[str, Any]]:
        async with self._lock:
            return [
                json.loads(json.dumps(item, default=str))
                for item in self._documents[namespace].values()
            ]


class PostgresDocumentStore:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(text("""
                CREATE TABLE IF NOT EXISTS documents (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (namespace, key)
                )
            """))

    async def load(self, namespace: str, key: str) -> dict[str, Any] | None:
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text("SELECT payload FROM documents WHERE namespace=:namespace AND key=:key"),
                    {"namespace": namespace, "key": key},
                )
            ).mappings().first()
            return dict(row["payload"]) if row else None

    async def save(
        self,
        namespace: str,
        key: str,
        payload: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> int:
        serializable = json.loads(json.dumps(payload, default=str))
        async with self.engine.begin() as connection:
            if expected_revision is not None:
                row = (
                    await connection.execute(
                        text("""
                            UPDATE documents
                            SET payload=CAST(:payload AS JSONB),
                                revision=revision + 1,
                                updated_at=NOW()
                            WHERE namespace=:namespace
                              AND key=:key
                              AND CAST(payload->>'revision' AS INTEGER)=:expected_revision
                            RETURNING revision
                        """),
                        {
                            "namespace": namespace,
                            "key": key,
                            "payload": json.dumps(serializable),
                            "expected_revision": expected_revision,
                        },
                    )
                ).first()
                if row is None:
                    raise DocumentConflictError(namespace, key, expected_revision)
                return int(row[0])
            row = (
                await connection.execute(
                    text("""
                        INSERT INTO documents(namespace, key, payload)
                        VALUES (:namespace, :key, CAST(:payload AS JSONB))
                        ON CONFLICT(namespace, key) DO UPDATE SET
                            payload=EXCLUDED.payload,
                            revision=documents.revision + 1,
                            updated_at=NOW()
                        RETURNING revision
                    """),
                    {
                        "namespace": namespace,
                        "key": key,
                        "payload": json.dumps(serializable),
                    },
                )
            ).first()
            return int(row[0])

    async def scan(self, namespace: str) -> list[dict[str, Any]]:
        async with self.engine.connect() as connection:
            rows = (
                await connection.execute(
                    text("SELECT payload FROM documents WHERE namespace=:namespace ORDER BY updated_at"),
                    {"namespace": namespace},
                )
            ).mappings().all()
            return [dict(row["payload"]) for row in rows]
