from app.infrastructure.db import build_engine, build_session_factory
from app.infrastructure.entities import (
    FavoriteEntity,
    RouteEntity,
    SessionEntity,
    SnapshotEntity,
    UserProfileEntity,
)
from sqlalchemy import BigInteger


def test_user_profile_mapping_retains_legacy_auth_columns() -> None:
    assert UserProfileEntity.__tablename__ == "user_profiles"
    assert "password_hash" in UserProfileEntity.__table__.columns
    assert "user_id" in UserProfileEntity.__table__.columns


def test_all_entity_mappings_use_existing_flyway_table_names() -> None:
    assert {
        UserProfileEntity.__tablename__,
        SessionEntity.__tablename__,
        RouteEntity.__tablename__,
        SnapshotEntity.__tablename__,
        FavoriteEntity.__tablename__,
    } == {"user_profiles", "sessions", "routes", "session_snapshots", "favorites"}


def test_bigserial_primary_keys_match_flyway_schema() -> None:
    for entity in (UserProfileEntity, SnapshotEntity, FavoriteEntity):
        assert isinstance(entity.__table__.c.id.type, BigInteger)


def test_session_factory_configures_async_engine_without_connecting() -> None:
    database_url = "postgresql+asyncpg://user:password@localhost:5432/liquidroute"

    engine = build_engine(database_url)
    session_factory = build_session_factory(database_url)

    assert engine.url.drivername == "postgresql+asyncpg"
    assert session_factory.kw["expire_on_commit"] is False
