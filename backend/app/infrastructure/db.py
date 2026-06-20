"""Async SQLAlchemy engine and session factory construction."""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def build_engine(database_url: str) -> AsyncEngine:
    """Build the application's async engine without opening a connection."""
    return create_async_engine(database_url, pool_pre_ping=True)


def build_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Build sessions whose ORM state remains usable after commits."""
    return async_sessionmaker(build_engine(database_url), expire_on_commit=False)

