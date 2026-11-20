"""
tests/test_security_hardening.py — Production Security & Rate Limiting Tests

Verifies:
  - Security headers (X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy)
  - Distributed / in-memory rate limiting enforcement (HTTP 429)
  - Rate limit telemetry headers (X-RateLimit-Limit, Remaining, Window)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.rate_limit import rate_limit
from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app


def test_security_headers_present(client):
    """Verify security headers are injected on responses."""
    response = client.get("/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "X-Request-ID" in headers
    assert "X-Response-Time" in headers


def test_rate_limiter_headers_and_limit(client):
    """Verify rate limiter tracks requests and returns 429 when threshold exceeded."""
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res
    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        exceeded = False
        for i in range(25):
            res = client.post(
                "/api/v1/auth/login",
                json={"email": f"abuse_test_{i}@example.com", "password": "wrongpassword123"},
                headers={"X-Forwarded-For": "198.51.100.42"},
            )
            if res.status_code == 429:
                exceeded = True
                data = res.json()
                assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
                assert "X-RateLimit-Limit" in res.headers
                assert res.headers["X-RateLimit-Remaining"] == "0"
                break

        assert exceeded is True
    finally:
        app.dependency_overrides.pop(get_session, None)
