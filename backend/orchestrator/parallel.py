from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class ParallelExecutor:
    """Deterministic stand-in for future parallel tool execution."""

    def run(self, jobs: list[Callable[[], T]]) -> list[T]:
        return [job() for job in jobs]

