"""
tests/test_calls.py — Unit Tests for Call Logs, Analytics & CSV Export

Testing:
  - Unauthorized access checks
  - Paginated call list queries
  - Single call record details with transcript
  - KPI aggregate analytics calculation
  - CSV report export
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.models.business import Business
from app.models.call import Call, CallDirection, CallSentiment, CallStatus


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def tokens(tenant_id):
    return {
        "staff": create_access_token(uuid.uuid4(), tenant_id, "STAFF"),
    }


@pytest.fixture
def mock_business(tenant_id):
    b = MagicMock(spec=Business)
    b.id = uuid.uuid4()
    b.tenant_id = tenant_id
    b.name = "Sunrise Clinic"
    b.is_deleted = False
    return b


@pytest.fixture
def mock_call(tenant_id, mock_business):
    c = MagicMock(spec=Call)
    c.id = uuid.uuid4()
    c.tenant_id = tenant_id
    c.business_id = mock_business.id
    c.appointment_id = None
    c.caller_phone = "+919876543210"
    c.direction = CallDirection.INBOUND
    c.status = CallStatus.COMPLETED
    c.started_at = datetime.now(timezone.utc)
    c.ended_at = datetime.now(timezone.utc)
    c.duration_seconds = 145
    c.recording_url = "https://s3.amazonaws.com/voxai/call-1.wav"
    c.transcript = [
        {"role": "assistant", "content": "Hello! How can I help you today?"},
        {"role": "user", "content": "I would like to book a dental checkup."},
    ]
    c.sentiment = CallSentiment.POSITIVE
    c.intent = "Appointment Booking"
    c.notes = "Patient booked routine checkup for next Tuesday."
    c.stt_latency_ms = 195
    c.llm_latency_ms = 220
    c.tts_latency_ms = 48
    c.cost_cents = 8
    c.is_deleted = False
    c.created_at = datetime.now(timezone.utc)
    c.updated_at = datetime.now(timezone.utc)
    return c


class TestCallsAPI:
    def test_list_calls_unauthorized(self, client):
        response = client.get("/api/v1/calls")
        assert response.status_code == 401

    def test_list_calls_business_not_found(self, client, tokens):
        mock_session = AsyncMock()
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_b_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/calls",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "BUSINESS_NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_list_calls_success(self, client, tokens, mock_business, mock_call):
        mock_session = AsyncMock()
        
        # 1. Business query
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = mock_business

        # 2. Calls query
        mock_c_res = MagicMock()
        mock_c_res.scalars.return_value.all.return_value = [mock_call]

        mock_session.execute.side_effect = [mock_b_res, mock_c_res]

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/calls",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["caller_phone"] == "+919876543210"
            assert data["items"][0]["duration_seconds"] == 145
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_get_call_by_id_success(self, client, tokens, mock_call):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_call
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                f"/api/v1/calls/{mock_call.id}",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(mock_call.id)
            assert len(data["transcript"]) == 2
            assert data["sentiment"] == "POSITIVE"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_get_call_stats_aggregates_kpis(self, client, tokens, mock_business, mock_call):
        mock_session = AsyncMock()
        
        # 1. Business query
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = mock_business

        # 2. Calls query
        mock_c_res = MagicMock()
        mock_c_res.scalars.return_value.all.return_value = [mock_call]

        mock_session.execute.side_effect = [mock_b_res, mock_c_res]

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/calls/analytics/stats",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total_calls"] == 1
            assert data["avg_duration_seconds"] == 145.0
            assert data["total_cost_usd"] == 0.08
            assert data["avg_stt_latency_ms"] == 195
            assert data["avg_llm_latency_ms"] == 220
            assert data["avg_tts_latency_ms"] == 48
            assert data["avg_e2e_latency_ms"] == 195 + 220 + 48
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_export_calls_csv_returns_csv(self, client, tokens, mock_business, mock_call):
        mock_session = AsyncMock()
        
        # 1. Business query
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = mock_business

        # 2. Calls query
        mock_c_res = MagicMock()
        mock_c_res.scalars.return_value.all.return_value = [mock_call]

        mock_session.execute.side_effect = [mock_b_res, mock_c_res]

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/calls/export/csv",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            assert "text/csv" in response.headers["content-type"]
            body = response.text
            assert "Call ID" in body
            assert "+919876543210" in body
            assert "POSITIVE" in body
        finally:
            app.dependency_overrides.pop(get_session, None)

