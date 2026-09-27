"""
tests/test_health.py — Day 1 Tests

CONCEPT: What is a test?
==========================
A test is a small program that calls your code and checks whether the output
is what you expected. If not, it "fails" — telling you something is broken.

pytest finds all files named test_*.py and runs every function named test_*.

WHY test the health endpoint?
Because if health breaks, NOTHING works — Docker won't know the container
is alive, load balancers won't route traffic here, and monitoring alerts fire.

TestClient from FastAPI/Starlette:
- Creates a fake HTTP client that calls your FastAPI app directly.
- No real network needed — tests run instantly.
- You can make GET/POST requests just like a real browser would.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

# TestClient wraps our FastAPI app. It simulates real HTTP requests.
# "with" statement ensures the app's lifespan (startup/shutdown) runs.
client = TestClient(app)


def test_health_returns_200():
    """
    GIVEN: The application is running
    WHEN:  GET /health is called
    THEN:  Response status should be 200 OK
    """
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_status():
    """
    GIVEN: The application is running
    WHEN:  GET /health is called
    THEN:  Body should contain status=ok and app name
    """
    response = client.get("/health")
    data = response.json()

    assert data["status"] == "ok"
    assert data["app"] == "VoxAI"
    assert "version" in data
    assert "environment" in data


def test_readiness_returns_200():
    """
    GIVEN: The application is running (Day 1: DB not yet connected)
    WHEN:  GET /ready is called
    THEN:  Response should be 200 (placeholder checks pass)
    """
    response = client.get("/ready")
    assert response.status_code == 200


def test_readiness_has_checks():
    """
    GIVEN: The application is running
    WHEN:  GET /ready is called
    THEN:  Body should contain checks dict
    """
    response = client.get("/ready")
    data = response.json()

    assert "status" in data
    assert "checks" in data
    assert "database" in data["checks"]
    assert "redis" in data["checks"]


def test_request_id_header_is_set():
    """
    GIVEN: The application is running
    WHEN:  Any request is made
    THEN:  Response should include X-Request-ID header
           (proves our request ID middleware is working)
    """
    response = client.get("/health")
    assert "x-request-id" in response.headers


def test_request_id_echoed_from_client():
    """
    GIVEN: Client sends a custom X-Request-ID
    WHEN:  GET /health is called with that header
    THEN:  Same ID should be echoed back in response headers
    """
    my_request_id = "test-request-id-12345"
    response = client.get("/health", headers={"X-Request-ID": my_request_id})
    assert response.headers["x-request-id"] == my_request_id


def test_unknown_route_returns_404():
    """
    GIVEN: The application is running
    WHEN:  A non-existent route is accessed
    THEN:  FastAPI returns 404 Not Found
    """
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404


def test_cors_headers_present():
    """
    GIVEN: A request with an Origin header (simulating a browser request)
    WHEN:  GET /health is called
    THEN:  CORS headers should be present in the response
    """
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    # The CORS middleware should add this header
    assert "access-control-allow-origin" in response.headers
