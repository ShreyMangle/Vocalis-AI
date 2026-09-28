"""
tests/test_db.py — Day 2 Tests: Database & Redis Layer

These are UNIT tests — they test the structure and logic WITHOUT a real database.
Tests that need a real running database are marked @pytest.mark.integration
and only run when Docker is up.

CONCEPT: Unit vs Integration vs End-to-End tests
=================================================
Unit test:       Tests ONE unit (function/class) in isolation.
                 External dependencies (DB, Redis) are mocked.
                 Fast: milliseconds each. Run on every save.

Integration test: Tests multiple components working together.
                  Needs real services running (DB, Redis via Docker).
                  Slower: seconds each. Run before commit.

E2E test:        Tests the full system from UI to database.
                 Slowest. Run before deployment.

We write: mostly unit tests (fast, cheap) + some integration tests.
We avoid: lots of E2E tests (slow, brittle).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Tests: Configuration
# =============================================================================

class TestDatabaseConfig:
    """Tests that the database configuration is correct."""

    def test_database_url_uses_async_driver(self):
        """
        GIVEN: Our settings
        WHEN:  DATABASE_URL is read
        THEN:  It should use the asyncpg driver (postgresql+asyncpg://)
               NOT the sync driver (postgresql://)

        Why? create_async_engine requires +asyncpg.
        Using the sync URL would cause runtime errors.
        """
        from app.core.config import settings
        url = str(settings.DATABASE_URL)
        assert "asyncpg" in url, (
            f"DATABASE_URL must use asyncpg async driver, got: {url}"
        )

    def test_pool_settings_are_sane(self):
        """
        GIVEN: Our settings
        WHEN:  Pool settings are read
        THEN:  They should be positive numbers in reasonable ranges
        """
        from app.core.config import settings
        assert settings.DB_POOL_SIZE > 0
        assert settings.DB_MAX_OVERFLOW >= 0
        assert settings.DB_POOL_TIMEOUT > 0

    def test_redis_url_format(self):
        """
        GIVEN: Our settings
        WHEN:  REDIS_URL is read
        THEN:  It should start with redis://
        """
        from app.core.config import settings
        assert str(settings.REDIS_URL).startswith("redis://")


# =============================================================================
# Tests: SQLAlchemy Engine
# =============================================================================

class TestDatabaseEngine:
    """Tests for the SQLAlchemy engine setup."""

    def test_engine_is_created(self):
        """
        GIVEN: The app module is imported
        WHEN:  The engine is accessed
        THEN:  It should exist (not None)
        """
        from app.db.base import engine
        assert engine is not None

    def test_session_factory_is_created(self):
        """
        GIVEN: The app module is imported
        WHEN:  The SessionFactory is accessed
        THEN:  It should be a callable session factory
        """
        from app.db.base import SessionFactory
        assert SessionFactory is not None
        assert callable(SessionFactory)

    def test_engine_pool_settings_applied(self):
        """
        GIVEN: The engine is created with pool settings
        WHEN:  The pool is inspected
        THEN:  Pool size should match config
        """
        from app.core.config import settings
        from app.db.base import engine

        # SQLAlchemy exposes pool settings on the engine's pool object
        pool = engine.pool
        assert pool.size() == settings.DB_POOL_SIZE


# =============================================================================
# Tests: Models Base
# =============================================================================

class TestModelBase:
    """Tests for SQLAlchemy model base classes."""

    def test_base_is_declarative(self):
        """
        GIVEN: The Base class
        WHEN:  Inspected
        THEN:  Should be a SQLAlchemy DeclarativeBase subclass
        """
        from sqlalchemy.orm import DeclarativeBase
        from app.models.base import Base
        assert issubclass(Base, DeclarativeBase)

    def test_timestamp_mixin_has_correct_fields(self):
        """
        GIVEN: The TimestampMixin
        WHEN:  A model inherits from Base + TimestampMixin
        THEN:  The model should have created_at and updated_at columns
        """
        from app.models.base import Base, TimestampMixin

        # Create a test model inline
        class TestModel(Base, TimestampMixin):
            __tablename__ = "test_timestamp_model"
            import sqlalchemy as sa
            id = sa.Column(sa.Integer, primary_key=True)

        # Check the columns exist in the table
        column_names = [c.name for c in TestModel.__table__.columns]
        assert "created_at" in column_names
        assert "updated_at" in column_names

    def test_soft_delete_mixin_has_correct_fields(self):
        """
        GIVEN: The SoftDeleteMixin
        WHEN:  A model inherits from Base + SoftDeleteMixin
        THEN:  The model should have is_deleted and deleted_at columns
        """
        from app.models.base import Base, SoftDeleteMixin

        class TestSoftModel(Base, SoftDeleteMixin):
            __tablename__ = "test_soft_delete_model"
            import sqlalchemy as sa
            id = sa.Column(sa.Integer, primary_key=True)

        column_names = [c.name for c in TestSoftModel.__table__.columns]
        assert "is_deleted" in column_names
        assert "deleted_at" in column_names

    def test_uuid_type_annotation_map(self):
        """
        GIVEN: The Base class has a type_annotation_map
        WHEN:  uuid.UUID is used as Mapped[uuid.UUID]
        THEN:  It should map to PostgreSQL UUID type
        """
        import uuid as uuid_module
        from sqlalchemy.dialects.postgresql import UUID
        from app.models.base import Base

        assert uuid_module.UUID in Base.type_annotation_map
        mapped_type = Base.type_annotation_map[uuid_module.UUID]
        assert isinstance(mapped_type, UUID)


# =============================================================================
# Tests: Redis Client
# =============================================================================

class TestRedisClient:
    """Tests for the Redis client wrapper (mocked — no real Redis needed)."""

    def test_redis_client_is_singleton(self):
        """
        GIVEN: The redis module is imported twice
        WHEN:  redis_client is accessed both times
        THEN:  Both references point to the same object
        """
        from app.db.redis import redis_client as rc1
        from app.db import redis as redis_module
        rc2 = redis_module.redis_client
        assert rc1 is rc2

    def test_redis_client_starts_uninitialized(self):
        """
        GIVEN: A fresh RedisClient instance
        WHEN:  Created without calling initialize()
        THEN:  _pool should be None (lazy initialization)
        """
        from app.db.redis import RedisClient
        client = RedisClient()
        assert client._pool is None
        assert client._client is None

    @pytest.mark.asyncio
    async def test_ping_returns_false_when_not_initialized(self):
        """
        GIVEN: A RedisClient that hasn't been initialized
        WHEN:  ping() is called
        THEN:  It should return False (not raise an exception)
        """
        from app.db.redis import RedisClient
        client = RedisClient()
        result = await client.ping()
        assert result is False

    @pytest.mark.asyncio
    async def test_set_raises_when_not_initialized(self):
        """
        GIVEN: A RedisClient that hasn't been initialized
        WHEN:  set() is called
        THEN:  It should raise RuntimeError with helpful message
        """
        from app.db.redis import RedisClient
        client = RedisClient()
        with pytest.raises(RuntimeError, match="Redis not initialized"):
            await client.set("key", "value")

    @pytest.mark.asyncio
    async def test_set_and_get_with_mock(self):
        """
        GIVEN: A RedisClient with a mocked internal _client
        WHEN:  set() and get() are called
        THEN:  They should call the underlying Redis commands correctly

        This tests OUR wrapper logic, not Redis itself.
        """
        from app.db.redis import RedisClient

        client = RedisClient()

        # Create a mock Redis client
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "hello"
        mock_redis.set.return_value = True

        # Inject the mock — bypass initialization
        client._client = mock_redis

        # Test get
        result = await client.get("some_key")
        assert result == "hello"
        mock_redis.get.assert_called_once_with("some_key")

        # Test set (no expiry)
        await client.set("some_key", "some_value")
        mock_redis.set.assert_called_once_with("some_key", "some_value")

    @pytest.mark.asyncio
    async def test_set_with_expiry_uses_setex(self):
        """
        GIVEN: A RedisClient with a mocked internal _client
        WHEN:  set() is called WITH expire_seconds
        THEN:  It should call Redis SETEX (not SET), which auto-expires the key

        SETEX = SET with EXpiry. This is how Redis TTL works.
        """
        from app.db.redis import RedisClient

        client = RedisClient()
        mock_redis = AsyncMock()
        client._client = mock_redis

        await client.set("session:call123", "data", expire_seconds=3600)
        # Should call setex, not set
        mock_redis.setex.assert_called_once_with("session:call123", 3600, "data")

    @pytest.mark.asyncio
    async def test_increment_sets_expiry_on_first_call(self):
        """
        GIVEN: A RedisClient with a mocked internal _client
        WHEN:  increment() is called with expire_seconds
        THEN:  EXPIRE is only set when the counter is first created (value==1)
               NOT on subsequent increments (would reset the window)

        This is the correct rate limiting pattern:
          - First request: INCR → 1, set EXPIRE 60
          - 2nd-99th request: INCR → 2..99, no EXPIRE change
          - After 60s: key expires, counter resets
        """
        from app.db.redis import RedisClient

        client = RedisClient()
        mock_redis = AsyncMock()
        client._client = mock_redis

        # First call → value is 1 → should set expiry
        mock_redis.incr.return_value = 1
        await client.increment("rate:user123", expire_seconds=60)
        mock_redis.expire.assert_called_once_with("rate:user123", 60)

        mock_redis.reset_mock()

        # Second call → value is 2 → should NOT set expiry again
        mock_redis.incr.return_value = 2
        await client.increment("rate:user123", expire_seconds=60)
        mock_redis.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_json_deserializes_correctly(self):
        """
        GIVEN: A Redis key containing a JSON string
        WHEN:  get_json() is called
        THEN:  It should return a Python dict (deserialized)
        """
        import json
        from app.db.redis import RedisClient

        client = RedisClient()
        mock_redis = AsyncMock()
        # Simulate Redis returning a JSON string
        mock_redis.get.return_value = json.dumps({"call_id": "abc", "turn": 3})
        client._client = mock_redis

        result = await client.get_json("session:abc")

        assert isinstance(result, dict)
        assert result["call_id"] == "abc"
        assert result["turn"] == 3

    @pytest.mark.asyncio
    async def test_get_json_returns_none_for_missing_key(self):
        """
        GIVEN: A Redis key that doesn't exist
        WHEN:  get_json() is called
        THEN:  It should return None (not raise an exception)
        """
        from app.db.redis import RedisClient

        client = RedisClient()
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # Simulate missing key
        client._client = mock_redis

        result = await client.get_json("nonexistent:key")
        assert result is None


# =============================================================================
# Tests: Readiness Endpoint (with mocked DB and Redis)
# =============================================================================

class TestReadinessEndpoint:
    """Tests that /ready correctly reports dependency health."""

    def test_ready_returns_correct_structure(self, client):
        """
        GIVEN: The app is running
        WHEN:  GET /ready is called
        THEN:  Response body has the expected keys regardless of check results
        """
        response = client.get("/ready")
        data = response.json()

        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]

    def test_ready_status_matches_http_code(self, client):
        """
        GIVEN: The /ready endpoint
        WHEN:  Called and the checks either all pass or some fail
        THEN:  HTTP 200 → status="ready", HTTP 503 → status="not_ready"
        """
        response = client.get("/ready")
        data = response.json()

        if response.status_code == 200:
            assert data["status"] == "ready"
        else:
            assert response.status_code == 503
            assert data["status"] == "not_ready"

    def test_ready_check_values_are_strings(self, client):
        """
        GIVEN: The /ready endpoint
        WHEN:  Called
        THEN:  Each check value is a string (either "ok" or "error: ...")
        """
        response = client.get("/ready")
        data = response.json()

        for service, check_value in data["checks"].items():
            assert isinstance(check_value, str), (
                f"Check '{service}' value should be a string, got {type(check_value)}"
            )
