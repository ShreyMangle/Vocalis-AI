"""
app/services/scheduler.py — Appointment Scheduling & Slot Availability Engine

Calculates open booking slots by cross-referencing:
  1. The business's weekly operating hours (open_time to close_time)
  2. The target service's duration (e.g. 15, 30, 60 minutes)
  3. Existing non-cancelled appointments (conflict prevention)
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.models.business import Business, DayOfWeek, WorkingHours

# Map python weekday (0=Monday, 6=Sunday) to DayOfWeek enum
_WEEKDAY_MAP = {
    0: DayOfWeek.MONDAY,
    1: DayOfWeek.TUESDAY,
    2: DayOfWeek.WEDNESDAY,
    3: DayOfWeek.THURSDAY,
    4: DayOfWeek.FRIDAY,
    5: DayOfWeek.SATURDAY,
    6: DayOfWeek.SUNDAY,
}


async def check_slot_conflict(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    business_id: uuid.UUID,
    start_time: datetime,
    duration_minutes: int,
    exclude_appointment_id: uuid.UUID | None = None,
) -> bool:
    """
    Check if a proposed appointment time conflicts with an existing booking.
    Returns True if a conflict exists, False if the slot is clear.
    """
    end_time = start_time + timedelta(minutes=duration_minutes)

    query = select(Appointment).where(
        Appointment.tenant_id == tenant_id,
        Appointment.business_id == business_id,
        Appointment.is_deleted == False,  # noqa: E712
        Appointment.status != AppointmentStatus.CANCELLED,
    )

    if exclude_appointment_id:
        query = query.where(Appointment.id != exclude_appointment_id)

    result = await session.execute(query)
    appointments = result.scalars().all()

    for appt in appointments:
        appt_start = appt.scheduled_at
        appt_end = appt.scheduled_at + timedelta(minutes=appt.duration_minutes)

        # Overlap occurs when: Proposed Start < Existing End AND Proposed End > Existing Start
        if start_time < appt_end and end_time > appt_start:
            return True

    return False


async def get_available_slots_for_date(
    session: AsyncSession,
    business: Business,
    target_date: date,
    duration_minutes: int = 30,
) -> list[dict[str, datetime | str]]:
    """
    Generate all open booking slots for a given calendar date.
    Returns list of dicts with:
      {"start_time": dt, "end_time": dt, "formatted_time": "09:30 AM"}
    """
    tz = ZoneInfo(business.timezone)
    day_enum = _WEEKDAY_MAP[target_date.weekday()]

    # 1. Fetch working hours for this day of the week
    wh_res = await session.execute(
        select(WorkingHours).where(
            WorkingHours.business_id == business.id,
            WorkingHours.day_of_week == day_enum,
        )
    )
    wh = wh_res.scalar_one_or_none()

    if wh is None or wh.is_closed or not wh.open_time or not wh.close_time:
        return []

    # 2. Fetch existing appointments on target_date
    day_start = datetime.combine(target_date, time.min, tzinfo=tz)
    day_end = datetime.combine(target_date, time.max, tzinfo=tz)

    appt_res = await session.execute(
        select(Appointment).where(
            Appointment.business_id == business.id,
            Appointment.is_deleted == False,  # noqa: E712
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.scheduled_at >= day_start,
            Appointment.scheduled_at <= day_end,
        )
    )
    existing_appts = appt_res.scalars().all()

    # 3. Generate candidate slots from open_time to close_time
    slots: list[dict[str, datetime | str]] = []
    current_dt = datetime.combine(target_date, wh.open_time, tzinfo=tz)
    close_dt = datetime.combine(target_date, wh.close_time, tzinfo=tz)
    step = timedelta(minutes=duration_minutes)

    while current_dt + step <= close_dt:
        slot_start = current_dt
        slot_end = current_dt + step

        # Check overlap against existing appointments
        has_overlap = False
        for appt in existing_appts:
            appt_start = appt.scheduled_at.astimezone(tz)
            appt_end = appt_start + timedelta(minutes=appt.duration_minutes)

            if slot_start < appt_end and slot_end > appt_start:
                has_overlap = True
                break

        if not has_overlap:
            slots.append(
                {
                    "start_time": slot_start,
                    "end_time": slot_end,
                    "formatted_time": slot_start.strftime("%I:%M %p"),
                }
            )

        current_dt += step

    return slots

