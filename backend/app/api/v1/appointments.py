"""
app/api/v1/appointments.py — Appointment Operations & Availability Endpoints

Routes:
  GET    /api/v1/appointments                    → List appointments (filters: status, customer_phone, date range)
  POST   /api/v1/appointments                    → Create appointment (with conflict collision check)
  GET    /api/v1/appointments/{appointment_id}  → Get appointment details
  PATCH  /api/v1/appointments/{appointment_id}  → Update / reschedule appointment
  DELETE /api/v1/appointments/{appointment_id}  → Cancel appointment
  GET    /api/v1/appointments/availability/slots → Fetch open booking slots for a date
  GET    /api/v1/appointments/calendar/ical      → Export live iCalendar (.ics) feed
"""

import uuid
from datetime import date, datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import (
    CurrentUser,
    require_authenticated,
    require_role,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_session
from app.models.appointment import Appointment, AppointmentStatus
from app.models.business import Business
from app.models.tenant_user import UserRole
from app.schemas.appointment import (
    AppointmentCreateRequest,
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentUpdateRequest,
    AvailableSlotItem,
    AvailableSlotsResponse,
)
from app.services.ical_generator import generate_ical_feed
from app.services.scheduler import check_slot_conflict, get_available_slots_for_date

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/appointments", tags=["Appointment Operations"])


async def _get_tenant_business(session: AsyncSession, tenant_id: uuid.UUID) -> Business:
    result = await session.execute(
        select(Business).where(
            Business.tenant_id == tenant_id,
            Business.is_deleted == False,  # noqa: E712
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise NotFoundError("Business profile not configured.", code="BUSINESS_NOT_FOUND")
    return business


@router.get(
    "",
    response_model=AppointmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List appointments",
)
async def list_appointments(
    appt_status: AppointmentStatus | None = Query(default=None, description="Filter by status"),
    customer_phone: str | None = Query(default=None, description="Filter by customer phone"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> AppointmentListResponse:
    """List appointments for the tenant's business."""
    business = await _get_tenant_business(session, current_user.tenant_id)

    query = select(Appointment).where(
        Appointment.tenant_id == current_user.tenant_id,
        Appointment.business_id == business.id,
        Appointment.is_deleted == False,  # noqa: E712
    )

    if appt_status:
        query = query.where(Appointment.status == appt_status)

    if customer_phone:
        query = query.where(Appointment.customer_phone.ilike(f"%{customer_phone}%"))

    query = query.order_by(Appointment.scheduled_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    appointments = result.scalars().all()

    return AppointmentListResponse(
        items=[AppointmentResponse.model_validate(a) for a in appointments],
        total=len(appointments),
    )


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule an appointment",
    description="Schedules an appointment. Verifies that the slot has no conflict.",
)
async def create_appointment(
    payload: AppointmentCreateRequest,
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> AppointmentResponse:
    """Book a new appointment with slot collision checking."""
    business = await _get_tenant_business(session, current_user.tenant_id)

    # Check for slot collision
    has_conflict = await check_slot_conflict(
        session=session,
        tenant_id=current_user.tenant_id,
        business_id=business.id,
        start_time=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
    )

    if has_conflict:
        raise ConflictError(
            "The requested appointment time conflicts with an existing booking.",
            code="SLOT_CONFLICT",
        )

    appointment = Appointment(
        tenant_id=current_user.tenant_id,
        business_id=business.id,
        service_id=payload.service_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        status=AppointmentStatus.CONFIRMED,
        notes=payload.notes,
        created_by_agent=payload.created_by_agent,
    )

    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)

    logger.info(
        "Appointment scheduled",
        appointment_id=str(appointment.id),
        customer_name=appointment.customer_name,
        scheduled_at=appointment.scheduled_at.isoformat(),
        tenant_id=str(current_user.tenant_id),
    )

    return AppointmentResponse.model_validate(appointment)


@router.get(
    "/availability/slots",
    response_model=AvailableSlotsResponse,
    status_code=status.HTTP_200_OK,
    summary="Query available booking slots for a date",
)
async def get_availability_slots(
    target_date: date = Query(..., description="Date to check slots for (YYYY-MM-DD)"),
    duration_minutes: int = Query(default=30, ge=5, le=480, description="Duration in minutes"),
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> AvailableSlotsResponse:
    """Fetch open booking slots based on operating hours and existing bookings."""
    business = await _get_tenant_business(session, current_user.tenant_id)

    raw_slots = await get_available_slots_for_date(
        session=session,
        business=business,
        target_date=target_date,
        duration_minutes=duration_minutes,
    )

    items = [
        AvailableSlotItem(
            start_time=s["start_time"],
            end_time=s["end_time"],
            formatted_time=s["formatted_time"],
        )
        for s in raw_slots
    ]

    return AvailableSlotsResponse(
        date=target_date.isoformat(),
        business_timezone=business.timezone,
        slots=items,
    )


@router.get(
    "/calendar/ical",
    status_code=status.HTTP_200_OK,
    summary="Get iCalendar feed",
)
async def get_calendar_feed(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Export calendar in standard RFC 5545 iCalendar format."""
    business = await _get_tenant_business(session, current_user.tenant_id)

    result = await session.execute(
        select(Appointment)
        .options(selectinload(Appointment.service))
        .where(
            Appointment.tenant_id == current_user.tenant_id,
            Appointment.business_id == business.id,
            Appointment.is_deleted == False,  # noqa: E712
        )
        .order_by(Appointment.scheduled_at.asc())
    )
    appointments = list(result.scalars().all())

    ical_content = generate_ical_feed(
        appointments=appointments,
        calendar_name=f"{business.name} Appointments",
    )

    return Response(
        content=ical_content,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="appointments.ics"'},
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get appointment by ID",
)
async def get_appointment(
    appointment_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> AppointmentResponse:
    """Fetch details of a single appointment."""
    result = await session.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.tenant_id == current_user.tenant_id,
            Appointment.is_deleted == False,  # noqa: E712
        )
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise NotFoundError("Appointment not found.", code="APPOINTMENT_NOT_FOUND")

    return AppointmentResponse.model_validate(appointment)


@router.patch(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Reschedule or update appointment",
)
async def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdateRequest,
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> AppointmentResponse:
    """Update or reschedule appointment."""
    result = await session.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.tenant_id == current_user.tenant_id,
            Appointment.is_deleted == False,  # noqa: E712
        )
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise NotFoundError("Appointment not found.", code="APPOINTMENT_NOT_FOUND")

    update_data = payload.model_dump(exclude_unset=True)

    # If rescheduling time, check for collision
    if "scheduled_at" in update_data and update_data["scheduled_at"] != appointment.scheduled_at:
        new_time = update_data["scheduled_at"]
        new_duration = update_data.get("duration_minutes", appointment.duration_minutes)

        has_conflict = await check_slot_conflict(
            session=session,
            tenant_id=current_user.tenant_id,
            business_id=appointment.business_id,
            start_time=new_time,
            duration_minutes=new_duration,
            exclude_appointment_id=appointment.id,
        )
        if has_conflict:
            raise ConflictError(
                "Rescheduled appointment time conflicts with an existing booking.",
                code="SLOT_CONFLICT",
            )
        appointment.original_scheduled_at = appointment.scheduled_at
        appointment.status = AppointmentStatus.RESCHEDULED

    for field, value in update_data.items():
        setattr(appointment, field, value)

    appointment.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(appointment)

    logger.info(
        "Appointment updated",
        appointment_id=str(appointment.id),
        status=appointment.status.value,
        tenant_id=str(current_user.tenant_id),
    )

    return AppointmentResponse.model_validate(appointment)


@router.delete(
    "/{appointment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel appointment",
)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Mark appointment as CANCELLED."""
    result = await session.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.tenant_id == current_user.tenant_id,
            Appointment.is_deleted == False,  # noqa: E712
        )
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise NotFoundError("Appointment not found.", code="APPOINTMENT_NOT_FOUND")

    appointment.status = AppointmentStatus.CANCELLED
    appointment.updated_at = datetime.now(timezone.utc)

    await session.commit()

    logger.info(
        "Appointment cancelled",
        appointment_id=str(appointment.id),
        tenant_id=str(current_user.tenant_id),
    )

