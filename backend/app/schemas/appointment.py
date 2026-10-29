"""
app/schemas/appointment.py — Appointment Schemas

Pydantic schemas for:
  - Appointment booking requests
  - Updating status and rescheduling
  - Listing and filtering appointments
  - Available slot queries and time representation
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.appointment import AppointmentStatus


class AppointmentCreateRequest(BaseModel):
    """Payload to schedule an appointment."""
    customer_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full name of customer",
        examples=["Rahul Sharma"],
    )
    customer_phone: str = Field(
        ...,
        min_length=7,
        max_length=50,
        description="Customer phone number",
        examples=["+919876543210"],
    )
    customer_email: EmailStr | None = Field(
        default=None,
        description="Customer email for notifications",
        examples=["rahul@example.com"],
    )
    service_id: uuid.UUID | None = Field(
        default=None,
        description="ID of specific service booked",
    )
    scheduled_at: datetime = Field(
        ...,
        description="ISO 8601 scheduled start timestamp with timezone",
    )
    duration_minutes: int = Field(
        default=30,
        ge=5,
        le=480,
        description="Duration of appointment in minutes",
        examples=[30],
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Notes recorded during voice conversation",
        examples=["Customer mentioned tooth sensitivity on left molar"],
    )
    created_by_agent: bool = Field(
        default=False,
        description="True if booked by automated voice receptionist",
    )


class AppointmentUpdateRequest(BaseModel):
    """Payload to reschedule or update status of an appointment."""
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    status: AppointmentStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)
    service_id: uuid.UUID | None = None


class AppointmentResponse(BaseModel):
    """Public representation of a scheduled appointment."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    business_id: uuid.UUID
    service_id: uuid.UUID | None
    customer_name: str
    customer_phone: str
    customer_email: str | None
    scheduled_at: datetime
    duration_minutes: int
    status: AppointmentStatus
    notes: str | None
    original_scheduled_at: datetime | None
    created_by_agent: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentListResponse(BaseModel):
    """List response wrapping appointment items."""
    items: list[AppointmentResponse]
    total: int


class AvailableSlotItem(BaseModel):
    """A discrete open calendar time slot."""
    start_time: datetime
    end_time: datetime
    formatted_time: str


class AvailableSlotsResponse(BaseModel):
    """Response containing available booking slots for a requested date."""
    date: str
    business_timezone: str
    slots: list[AvailableSlotItem]

