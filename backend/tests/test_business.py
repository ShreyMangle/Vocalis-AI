"""
tests/test_business.py — Unit Tests for Business Profile & Working Hours

Testing strategy:
  - Auth token parsing and RBAC permissions (STAFF forbidden, ADMIN/OWNER allowed)
  - Business profile GET, PUT (upsert), PATCH (partial update)
  - Timezone validation using IANA database
  - Working hours validation (open < close, closed handling, duplicate days)
  - Schedule batch update and retrieval
"""

import uuid
from datetime import datetime, time, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.models.business import Business, DayOfWeek, WorkingHours


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def tokens(tenant_id):
    return {
        "owner": create_access_token(uuid.uuid4(), tenant_id, "OWNER"),
        "admin": create_access_token(uuid.uuid4(), tenant_id, "ADMIN"),
        "staff": create_access_token(uuid.uuid4(), tenant_id, "STAFF"),
    }


@pytest.fixture
def mock_business(tenant_id):
    b = MagicMock(spec=Business)
    b.id = uuid.uuid4()
    b.tenant_id = tenant_id
    b.name = "Sunrise Clinic"
    b.description = "Primary care clinic"
    b.industry = "healthcare"
    b.timezone = "Asia/Kolkata"
    b.phone_number = "+919876543210"
    b.email = "info@sunrise.com"
    b.website = "https://sunrise.com"
    b.address = "123 Medical Enclave"
    b.is_deleted = False
    b.created_at = datetime.now(timezone.utc)
    b.updated_at = datetime.now(timezone.utc)
    return b


# =============================================================================
# TEST: Business Profile
# =============================================================================

class TestBusinessProfile:
    def test_get_business_unauthorized(self, client):
        response = client.get("/api/v1/business")
        assert response.status_code == 401

    def test_get_business_not_found(self, client, tokens):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_res

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.get(
                "/api/v1/business",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "BUSINESS_NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_get_business_success(self, client, tokens, mock_business):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_business
        mock_session.execute.return_value = mock_res

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.get(
                "/api/v1/business",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Sunrise Clinic"
            assert data["timezone"] == "Asia/Kolkata"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_upsert_business_forbidden_for_staff(self, client, tokens):
        payload = {
            "name": "Sunrise Healthcare",
            "timezone": "Asia/Kolkata",
        }
        response = client.put(
            "/api/v1/business",
            json=payload,
            headers={"Authorization": f"Bearer {tokens['staff']}"},
        )
        assert response.status_code == 403

    def test_upsert_business_creates_new(self, client, tokens, tenant_id):
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_res

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            payload = {
                "name": "New Sunrise Clinic",
                "description": "General practice",
                "industry": "healthcare",
                "timezone": "Asia/Kolkata",
                "phone_number": "+919999999999",
                "email": "contact@sunrise.com",
            }
            response = client.put(
                "/api/v1/business",
                json=payload,
                headers={"Authorization": f"Bearer {tokens['admin']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "New Sunrise Clinic"
            assert data["timezone"] == "Asia/Kolkata"
            assert mock_session.add.called
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_invalid_timezone_fails_validation(self, client, tokens):
        payload = {
            "name": "Sunrise Clinic",
            "timezone": "Mars/Olympus_Mons",  # Invalid IANA timezone
        }
        response = client.put(
            "/api/v1/business",
            json=payload,
            headers={"Authorization": f"Bearer {tokens['owner']}"},
        )
        assert response.status_code == 422


# =============================================================================
# TEST: Working Hours
# =============================================================================

class TestWorkingHours:
    def test_get_working_hours_unauthorized(self, client):
        response = client.get("/api/v1/business/working-hours")
        assert response.status_code == 401

    def test_get_working_hours_success(self, client, tokens, tenant_id):
        wh = MagicMock(spec=WorkingHours)
        wh.id = uuid.uuid4()
        wh.tenant_id = tenant_id
        wh.business_id = uuid.uuid4()
        wh.day_of_week = DayOfWeek.MONDAY
        wh.open_time = time(9, 0)
        wh.close_time = time(18, 0)
        wh.is_closed = False
        wh.created_at = datetime.now(timezone.utc)
        wh.updated_at = datetime.now(timezone.utc)

        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [wh]
        mock_res.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_res

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.get(
                "/api/v1/business/working-hours",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["day_of_week"] == "MONDAY"
            assert data[0]["open_time"] == "09:00:00"
            assert data[0]["close_time"] == "18:00:00"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_working_hours_validation_open_after_close(self, client, tokens):
        """open_time >= close_time must raise 422."""
        payload = {
            "schedule": [
                {
                    "day_of_week": "MONDAY",
                    "open_time": "18:00:00",
                    "close_time": "09:00:00",  # Invalid: closes before it opens!
                    "is_closed": False,
                }
            ]
        }
        response = client.put(
            "/api/v1/business/working-hours",
            json=payload,
            headers={"Authorization": f"Bearer {tokens['admin']}"},
        )
        assert response.status_code == 422

    def test_working_hours_validation_missing_times_when_not_closed(self, client, tokens):
        """When is_closed=False, open_time and close_time cannot be null."""
        payload = {
            "schedule": [
                {
                    "day_of_week": "MONDAY",
                    "open_time": None,
                    "close_time": None,
                    "is_closed": False,
                }
            ]
        }
        response = client.put(
            "/api/v1/business/working-hours",
            json=payload,
            headers={"Authorization": f"Bearer {tokens['admin']}"},
        )
        assert response.status_code == 422

    def test_working_hours_closed_day_passes(self, client, tokens, mock_business):
        """Closed day with null times is valid."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        # 1st execute: business check
        res1 = MagicMock()
        res1.scalar_one_or_none.return_value = mock_business
        # 2nd execute: existing wh check
        res2 = MagicMock()
        res2.scalar_one_or_none.return_value = None
        # 3rd execute: return updated list
        wh = MagicMock(spec=WorkingHours)
        wh.id = uuid.uuid4()
        wh.tenant_id = mock_business.tenant_id
        wh.business_id = mock_business.id
        wh.day_of_week = DayOfWeek.SUNDAY
        wh.open_time = None
        wh.close_time = None
        wh.is_closed = True
        wh.created_at = datetime.now(timezone.utc)
        wh.updated_at = datetime.now(timezone.utc)

        res3 = MagicMock()
        sc3 = MagicMock()
        sc3.all.return_value = [wh]
        res3.scalars.return_value = sc3

        mock_session.execute.side_effect = [res1, res2, res3]

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            payload = {
                "schedule": [
                    {
                        "day_of_week": "SUNDAY",
                        "open_time": None,
                        "close_time": None,
                        "is_closed": True,
                    }
                ]
            }
            response = client.put(
                "/api/v1/business/working-hours",
                json=payload,
                headers={"Authorization": f"Bearer {tokens['owner']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["day_of_week"] == "SUNDAY"
            assert data[0]["is_closed"] is True
        finally:
            app.dependency_overrides.pop(get_session, None)
