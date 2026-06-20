"""ORM mappings for the PostgreSQL tables created by Flyway V1--V6."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for existing LiquidRoute persistence mappings."""


class UserProfileEntity(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_name: Mapped[str | None] = mapped_column(String(100))
    preferred_city: Mapped[str | None] = mapped_column(String(50))
    avg_budget: Mapped[float | None] = mapped_column(Float)
    favorite_categories: Mapped[str | None] = mapped_column(Text)
    preference_tags: Mapped[str | None] = mapped_column(Text)
    avoid_tags: Mapped[str | None] = mapped_column(Text)
    history_actions: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    provider_name: Mapped[str | None] = mapped_column(String(50))
    # This legacy column is retained only so pre-existing Flyway databases map.
    deepseek_api_key: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SessionEntity(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(50), index=True)
    intent_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RouteEntity(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    segments_json: Mapped[str] = mapped_column(Text, nullable=False)
    total_cost: Mapped[float | None] = mapped_column(Float)
    total_travel_time: Mapped[float | None] = mapped_column(Float)
    total_rating: Mapped[float | None] = mapped_column(Float)
    optimization_goal: Mapped[str | None] = mapped_column(String(50))
    score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SnapshotEntity(Base):
    __tablename__ = "session_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    route_json: Mapped[str] = mapped_column(Text, nullable=False)
    intent_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FavoriteEntity(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(50), index=True)
    route_json: Mapped[str] = mapped_column(Text, nullable=False)
    route_name: Mapped[str | None] = mapped_column(String(200))
    scene: Mapped[str | None] = mapped_column(String(100))
    poi_count: Mapped[int | None] = mapped_column(Integer)
    total_time: Mapped[str | None] = mapped_column(String(50))
    total_cost: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
