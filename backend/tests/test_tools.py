"""
tests/test_tools.py — Unit Tests for AI Voice Agent Tool Calling Engine

Tests:
  - check_availability: open slots retrieval
  - book_appointment: slot reservation & conflict detection
  - confirm_appointment: status update
  - reschedule_appointment: slot update & conflict check
  - cancel_appointment: status cancellation
  - escalate_to_human: routing transfer action
  - end_call: graceful termination
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.tools.definitions import VOICE_AGENT_TOOLS
from app.ai.tools.executor import ToolExecutor
from app.models.appointment import Appointment, AppointmentStatus
from app.models.business import Business, DayOfWeek, WorkingHours


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def business_id():
    return uuid.uuid4()


def test_voice_agent_tools_schema_valid():
    tool_names = [t["function"]["name"] for t in VOICE_AGENT_TOOLS]
    assert "check_availability" in tool_names
    assert "book_appointment" in tool_names
    assert "confirm_appointment" in tool_names
    assert "reschedule_appointment" in tool_names
    assert "cancel_appointment" in tool_names
    assert "escalate_to_human" in tool_names
    assert "end_call" in tool_names


@pytest.mark.asyncio
async def test_tool_executor_escalate_and_end(tenant_id, business_id):
    mock_session = AsyncMock()
    executor = ToolExecutor(
        session=mock_session,
        tenant_id=tenant_id,
        business_id=business_id,
    )

    # Escalate to human
    res_esc = await executor.execute("escalate_to_human", {"reason": "Customer needs a doctor urgently"})
    assert res_esc.success is True
    assert res_esc.action == "transfer"
    assert "Please hold" in res_esc.message

    # End call
    res_end = await executor.execute("end_call", {"summary": "Booking finished"})
    assert res_end.success is True
    assert res_end.action == "hangup"
    assert "Have a wonderful day" in res_end.message


@pytest.mark.asyncio
async def test_tool_executor_check_availability(tenant_id, business_id):
    mock_session = AsyncMock()

    # Mock business query
    mock_b = MagicMock(spec=Business)
    mock_b.id = business_id
    mock_b.timezone = "Asia/Kolkata"
    mock_b_res = MagicMock()
    mock_b_res.scalar_one_or_none.return_value = mock_b

    # Mock working hours query (Monday 9 AM to 5 PM)
    mock_wh = MagicMock(spec=WorkingHours)
    mock_wh.day_of_week = DayOfWeek.MONDAY
    mock_wh.is_closed = False
    mock_wh.open_time = datetime.strptime("09:00", "%H:%M").time()
    mock_wh.close_time = datetime.strptime("17:00", "%H:%M").time()
    mock_wh_res = MagicMock()
    mock_wh_res.scalar_one_or_none.return_value = mock_wh

    # Mock appointments query (empty)
    mock_appt_res = MagicMock()
    mock_appt_res.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [mock_b_res, mock_wh_res, mock_appt_res]

    executor = ToolExecutor(
        session=mock_session,
        tenant_id=tenant_id,
        business_id=business_id,
    )

    # 2026-11-23 is a Monday
    res = await executor.execute("check_availability", {"target_date": "2026-11-23", "duration_minutes": 30})
    assert res.success is True
    assert "available slots" in res.message
    assert len(res.data["available_slots"]) > 0


@pytest.mark.asyncio
async def test_tool_executor_book_appointment_success(tenant_id, business_id):
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    # 1. Conflict check query -> empty (no conflict)
    mock_conflict_res = MagicMock()
    mock_conflict_res.scalars.return_value.all.return_value = []

    # 2. Service query -> none
    mock_svc_res = MagicMock()
    mock_svc_res.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [mock_conflict_res, mock_svc_res]

    executor = ToolExecutor(
        session=mock_session,
        tenant_id=tenant_id,
        business_id=business_id,
    )

    res = await executor.execute(
        "book_appointment",
        {
            "customer_name": "Vikram Patel",
            "customer_phone": "+919876543210",
            "scheduled_at": "2026-11-24T11:00:00Z",
            "duration_minutes": 30,
        },
    )

    assert res.success is True
    assert "Vikram Patel" in res.message
    assert "appointment_id" in res.data
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_tool_executor_book_appointment_conflict(tenant_id, business_id):
    mock_session = AsyncMock()

    # 1. Overlapping appointment in DB
    existing_appt = MagicMock(spec=Appointment)
    existing_appt.scheduled_at = datetime.fromisoformat("2026-11-24T11:00:00+00:00")
    existing_appt.duration_minutes = 30

    mock_conflict_res = MagicMock()
    mock_conflict_res.scalars.return_value.all.return_value = [existing_appt]

    mock_session.execute.return_value = mock_conflict_res

    executor = ToolExecutor(
        session=mock_session,
        tenant_id=tenant_id,
        business_id=business_id,
    )

    res = await executor.execute(
        "book_appointment",
        {
            "customer_name": "Second Caller",
            "customer_phone": "+919876543299",
            "scheduled_at": "2026-11-24T11:00:00Z",
            "duration_minutes": 30,
        },
    )

    assert res.success is False
    assert "already booked" in res.message
    assert res.data.get("conflict") is True


@pytest.mark.asyncio
async def test_tool_executor_confirm_appointment(tenant_id, business_id):
    mock_session = AsyncMock()
    appt = MagicMock(spec=Appointment)
    appt.id = uuid.uuid4()
    appt.scheduled_at = datetime.now(timezone.utc)
    appt.status = AppointmentStatus.PENDING

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = appt
    mock_session.execute.return_value = mock_res

    executor = ToolExecutor(
        session=mock_session,
        tenant_id=tenant_id,
        business_id=business_id,
        current_appointment_id=appt.id,
    )

    res = await executor.execute("confirm_appointment", {})
    assert res.success is True
    assert appt.status == AppointmentStatus.CONFIRMED
    assert "confirmed" in res.message
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_tool_executor_cancel_appointment(tenant_id, business_id):
    mock_session = AsyncMock()
    appt = MagicMock(spec=Appointment)
    appt.id = uuid.uuid4()
    appt.scheduled_at = datetime.now(timezone.utc)
    appt.status = AppointmentStatus.CONFIRMED
    appt.notes = ""

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = appt
    mock_session.execute.return_value = mock_res

    executor = ToolExecutor(
        session=mock_session,
        tenant_id=tenant_id,
        business_id=business_id,
        current_appointment_id=appt.id,
    )

    res = await executor.execute("cancel_appointment", {"reason": "Change of plans"})
    assert res.success is True
    assert appt.status == AppointmentStatus.CANCELLED
    assert "[Cancelled: Change of plans]" in appt.notes
    mock_session.commit.assert_awaited_once()
