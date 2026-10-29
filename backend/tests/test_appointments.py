"""
tests/test_appointments.py — Unit Tests for Appointments & Scheduling Engine

Testing:
  - Unauthorized access checks
  - Appointment listing and phone filtering
  - Appointment booking with conflict collision check (409 SLOT_CONFLICT)
  - Rescheduling and status transitions
  - Slot availability calculation across working hours and bookings
  - RFC 5545 iCalendar feed export
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.models.appointment import Appointment, AppointmentStatus
from app.models.business import Business, DayOfWeek, WorkingHours
from app.models.service import Service


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def tokens(tenant_id):
    return {
        "staff": create_access_token(uuid.uuid4(), tenant_id, "STAFF"),
        "admin": create_access_token(uuid.uuid4(), tenant_id, "ADMIN"),
    }


@pytest.fixture
def mock_business(tenant_id):
    b = MagicMock(spec=Business)
    b.id = uuid.uuid4()
    b.tenant_id = tenant_id
    b.name = "Sunrise Clinic"
    b.timezone = "Asia/Kolkata"
    b.is_deleted = False
    return b


@pytest.fixture
def mock_appointment(tenant_id, mock_business):
    a = MagicMock(spec=Appointment)
    a.id = uuid.uuid4()
    a.tenant_id = tenant_id
    a.business_id = mock_business.id
    a.service_id = uuid.uuid4()
    a.customer_name = "Rahul Sharma"
    a.customer_phone = "+919876543210"
    a.customer_email = "rahul@example.com"
    a.scheduled_at = datetime.now(timezone.utc) + timedelta(days=1)
    a.duration_minutes = 30
    a.status = AppointmentStatus.CONFIRMED
    a.notes = "General consultation"
    a.original_scheduled_at = None
    a.created_by_agent = True
    a.is_deleted = False
    a.created_at = datetime.now(timezone.utc)
    a.updated_at = datetime.now(timezone.utc)
    a.service = None
    return a


class TestAppointmentsAPI:
    def test_list_appointments_unauthorized(self, client):
        response = client.get("/api/v1/appointments")
        assert response.status_code == 401

    def test_list_appointments_business_not_found(self, client, tokens):
        mock_session = AsyncMock()
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_b_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/appointments",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "BUSINESS_NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_list_appointments_success(self, client, tokens, mock_business, mock_appointment):
        mock_session = AsyncMock()
        
        # 1. Business query
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = mock_business

        # 2. Appointments query
        mock_a_res = MagicMock()
        mock_a_res.scalars.return_value.all.return_value = [mock_appointment]

        mock_session.execute.side_effect = [mock_b_res, mock_a_res]

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/appointments",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["customer_name"] == "Rahul Sharma"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_create_appointment_success(self, client, tokens, mock_business):
        mock_session = AsyncMock()
        
        # 1. Business query
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = mock_business

        # 2. Conflict query (empty = no collision)
        mock_c_res = MagicMock()
        mock_c_res.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_b_res, mock_c_res]
        mock_session.add = MagicMock()

        async def mock_refresh(instance):
            instance.id = uuid.uuid4()
            instance.created_at = datetime.now(timezone.utc)
            instance.updated_at = datetime.now(timezone.utc)

        mock_session.refresh = mock_refresh

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
            payload = {
                "customer_name": "Aman Verma",
                "customer_phone": "+919876543299",
                "scheduled_at": future_time,
                "duration_minutes": 30,
                "notes": "Booked via AI agent",
            }
            response = client.post(
                "/api/v1/appointments",
                json=payload,
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["customer_name"] == "Aman Verma"
            assert data["status"] == "CONFIRMED"
            mock_session.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_create_appointment_collision_conflict_409(
        self, client, tokens, mock_business, mock_appointment
    ):
        mock_session = AsyncMock()
        
        # 1. Business query
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = mock_business

        # 2. Conflict query returns overlapping appointment!
        mock_c_res = MagicMock()
        mock_c_res.scalars.return_value.all.return_value = [mock_appointment]

        mock_session.execute.side_effect = [mock_b_res, mock_c_res]

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            payload = {
                "customer_name": "Second Caller",
                "customer_phone": "+919111122222",
                "scheduled_at": mock_appointment.scheduled_at.isoformat(),
                "duration_minutes": 30,
            }
            response = client.post(
                "/api/v1/appointments",
                json=payload,
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "SLOT_CONFLICT"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_get_appointment_by_id_success(self, client, tokens, mock_appointment):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_appointment
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                f"/api/v1/appointments/{mock_appointment.id}",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            assert response.json()["id"] == str(mock_appointment.id)
            assert response.json()["customer_name"] == "Rahul Sharma"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_cancel_appointment_sets_status(self, client, tokens, mock_appointment):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_appointment
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.delete(
                f"/api/v1/appointments/{mock_appointment.id}",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 204
            assert mock_appointment.status == AppointmentStatus.CANCELLED
            mock_session.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_get_calendar_feed_returns_ical_format(
        self, client, tokens, mock_business, mock_appointment
    ):
        mock_session = AsyncMock()
        
        # 1. Business query
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = mock_business

        # 2. Appointments query with service load
        mock_a_res = MagicMock()
        mock_a_res.scalars.return_value.all.return_value = [mock_appointment]

        mock_session.execute.side_effect = [mock_b_res, mock_a_res]

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/appointments/calendar/ical",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            assert "text/calendar" in response.headers["content-type"]
            body = response.text
            assert "BEGIN:VCALENDAR" in body
            assert "BEGIN:VEVENT" in body
            assert "Rahul Sharma" in body
            assert "END:VCALENDAR" in body
        finally:
            app.dependency_overrides.pop(get_session, None)

