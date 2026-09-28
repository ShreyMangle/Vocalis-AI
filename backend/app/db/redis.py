"""
app/db/redis.py — Redis Async Client

CONCEPT: What is Redis?
========================
Redis (Remote Dictionary Server) is a super-fast in-memory database.
"In-memory" means data lives in RAM, not on disk → access is ~100x faster than PostgreSQL.

BUT: RAM is volatile — if the server restarts, data is gone.
     (Redis does have optional persistence — we enabled appendonly in Docker Compose.)

USE CASES in VoxAI:
  1. Call Session State:
     While a call is happening (could be minutes), we need to track its state:
     - What has been said so far (conversation history)
     - Which turn we're on
     - Whether the AI is speaking
     We store this in Redis keyed by call_id.
     Fast reads/writes = no latency added to voice pipeline.

  2. Caching:
     "What services does Clinic ABC offer?" → query PostgreSQL once, cache in Redis.
     Next 100 calls: answer from Redis (microseconds) not PostgreSQL (milliseconds).

  3. Rate Limiting:
     "How many API requests has user X made in the last minute?"
     Redis INCR + EXPIRE = perfect for this.

  4. Background Job Queue (ARQ uses Redis internally):
     After a call ends → push a "process this call" job to Redis queue.
     Worker picks it up and processes asynchronously.

CONCEPT: Connection Pooling in Redis
======================================
Same idea as PostgreSQL — we keep connections open and reuse them.
The `redis.asyncio.ConnectionPool` does this automatically.

redis.asyncio = the async version of the redis-py library.
Regular redis-py blocks the thread. redis.asyncio uses async/await.
"""

from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import logger


class RedisClient:
    """
    Wrapper around the Redis connection pool.

    We use a class (not just module-level functions) so we can:
    1. Initialize the pool once on startup.
    2. Close it cleanly on shutdown.
    3. Easily swap the implementation in tests.
    """

    def __init__(self) -> None:
        # _pool is None until initialize() is called.
        # This is the "lazy initialization" pattern.
        self._pool: aioredis.ConnectionPool | None = None
        self._client: aioredis.Redis | None = None

    async def initialize(self) -> None:
        """
        Create the Redis connection pool.
        Called once during application startup.
        """
        self._pool = aioredis.ConnectionPool.from_url(
            str(settings.REDIS_URL),
            max_connections=20,      # Max simultaneous Redis connections
            decode_responses=True,   # Return strings instead of bytes
            # e.g., GET "key" returns "value" not b"value"
            socket_timeout=5.0,      # Timeout for individual Redis commands (seconds)
            socket_connect_timeout=5.0,  # Timeout for establishing connection
        )
        self._client = aioredis.Redis(connection_pool=self._pool)

        # Test the connection immediately
        await self.ping()
        logger.info("Redis client initialized", url=str(settings.REDIS_URL))

    async def close(self) -> None:
        """
        Close all Redis connections.
        Called on application shutdown — ensures no connections leak.
        """
        if self._pool:
            await self._pool.aclose()
            logger.info("Redis connection pool closed")

    async def ping(self) -> bool:
        """
        Send a PING command to Redis.
        Redis responds with PONG if alive.
        Used by /ready endpoint and startup check.
        """
        if not self._client:
            return False
        try:
            result = await self._client.ping()
            return result is True
        except Exception as e:
            logger.warning("Redis ping failed", error=str(e))
            return False

    # =========================================================================
    # KEY-VALUE OPERATIONS
    # These are thin wrappers that add type safety and logging.
    # =========================================================================

    async def get(self, key: str) -> str | None:
        """Get a value by key. Returns None if key doesn't exist."""
        if not self._client:
            raise RuntimeError("Redis not initialized")
        return await self._client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        expire_seconds: int | None = None,
    ) -> None:
        """
        Set a key-value pair.

        expire_seconds: if set, the key automatically deletes after N seconds.
        GREAT for session data — call sessions expire after the call ends.
        """
        if not self._client:
            raise RuntimeError("Redis not initialized")
        if expire_seconds:
            await self._client.setex(key, expire_seconds, value)
        else:
            await self._client.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete a key."""
        if not self._client:
            raise RuntimeError("Redis not initialized")
        await self._client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if not self._client:
            raise RuntimeError("Redis not initialized")
        return bool(await self._client.exists(key))

    async def increment(self, key: str, expire_seconds: int | None = None) -> int:
        """
        Atomically increment a counter by 1.
        Used for rate limiting: increment "requests:user_id" every request.
        ATOMIC = thread-safe, works across multiple server instances.
        """
        if not self._client:
            raise RuntimeError("Redis not initialized")
        value = await self._client.incr(key)
        if expire_seconds and value == 1:
            # Set expiry on first increment (so the counter resets after window)
            await self._client.expire(key, expire_seconds)
        return value

    async def get_json(self, key: str) -> Any | None:
        """
        Get a JSON value. Deserializes the stored JSON string automatically.
        Useful for storing call session state (a dict).
        """
        import json
        raw = await self.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(
        self,
        key: str,
        value: Any,
        expire_seconds: int | None = None,
    ) -> None:
        """
        Store a Python dict/list as JSON.
        Serializes automatically — you pass a dict, it stores as JSON string.
        """
        import json
        await self.set(key, json.dumps(value), expire_seconds)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================
# One global instance, initialized in main.py lifespan on startup.
redis_client = RedisClient()
