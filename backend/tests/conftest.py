"""
tests/conftest.py — Shared Test Fixtures

CONCEPT: What is conftest.py?
==============================
pytest automatically loads this file before running any tests.
It's where you define "fixtures" — reusable setup code.

A fixture is like a helper function that:
  1. Sets something up before the test (e.g., creates a fake DB session).
  2. Runs the test.
  3. Tears it down after (e.g., closes the session).

CONCEPT: Overriding Settings for Tests
========================================
In tests we never want to touch a real database or Redis.
FastAPI's dependency injection makes this easy:
  app.dependency_overrides[get_session] = lambda: mock_session

This replaces the real `get_session` dependency with a mock.
All tests using it get the mock — zero real DB calls.

For Day 2, we keep it simple. As we add more services (Week 2+),
we'll add more fixtures here.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    """
    A TestClient that wraps our FastAPI app.

    scope="session" means this fixture is created ONCE per test session,
    not once per test function. The app (and its lifespan) starts once.

    Using `with TestClient(app)` triggers the app's lifespan events:
    - startup: tries to connect DB/Redis (will warn, not crash)
    - all tests run
    - shutdown: cleans up connections
    """
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
