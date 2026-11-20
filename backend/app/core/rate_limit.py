"""
app/core/rate_limit.py — Distributed & In-Memory Rate Limiter

Protects API endpoints from brute force and abusive traffic.
Primary: Redis atomic counter (multi-instance production safe).
Fallback: In-memory sliding window counter (for local/testing or Redis offline).
"""

import time
from collections import defaultdict
from typing import Callable

import structlog
from fastapi import Request, Response

from app.core.exceptions import RateLimitError
from app.db.redis import redis_client

logger = structlog.get_logger(__name__)

# Fallback in-memory tracking: { "identifier:window": (count, expires_at) }
_in_memory_buckets: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))


def rate_limit(
    max_requests: int = 60,
    window_seconds: int = 60,
    key_prefix: str = "rl",
) -> Callable:
    """
    FastAPI dependency for rate limiting.

    Usage:
        @router.post("/login", dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60))])
    """

    async def _rate_limiter(request: Request, response: Response) -> None:
        # Determine client identifier:
        # 1. Authenticated user ID (if present in request state)
        # 2. X-Forwarded-For header (if behind reverse proxy)
        # 3. Client IP
        identifier = getattr(request.state, "user_id", None)
        if not identifier:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                identifier = forwarded.split(",")[0].strip()
            elif request.client:
                identifier = request.client.host
            else:
                identifier = "unknown"

        key = f"{key_prefix}:{identifier}:{window_seconds}"
        current_count = 0

        # 1. Try Redis if active
        if getattr(redis_client, "is_connected", False):
            try:
                current_count = await redis_client.increment(key, expire_seconds=window_seconds)
            except Exception:
                current_count = 0

        # 2. In-memory sliding window fallback
        if current_count == 0:
            now = time.time()
            count, expires_at = _in_memory_buckets[key]
            if now > expires_at:
                count = 1
                expires_at = now + window_seconds
            else:
                count += 1
            _in_memory_buckets[key] = (count, expires_at)
            current_count = count

        remaining = max(0, max_requests - current_count)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = f"{window_seconds}s"

        if current_count > max_requests:
            logger.warning(
                "Rate limit exceeded",
                identifier=identifier,
                path=request.url.path,
                count=current_count,
                limit=max_requests,
            )
            raise RateLimitError(
                f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds.",
                code="RATE_LIMIT_EXCEEDED",
                details={
                    "limit": max_requests,
                    "window_seconds": window_seconds,
                    "retry_after": window_seconds,
                },
            )

    return _rate_limiter
