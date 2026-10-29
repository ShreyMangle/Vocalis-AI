"""
app/models/appointment.py — Appointment Database Model

CONCEPT: Appointments in AI Voice Operations
==============================================
The primary business outcome of an inbound voice call is often scheduling
an appointment (dental consultation, hotel booking, table reservation, salon slot).

Appointments are:
  - Associated with a Tenant and a Business
  - Linked to a specific Service (which dictates slot duration and price)
  - Bound to a customer phone number and name
  - Tagged with structured lifecycle status (CONFIRMED, CANCELLED, RESCHEDULED, etc.)
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class AppointmentStatus(str, enum.Enum):
    """Lifecycle statuses for appointments."""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class Appointment(Base, TimestampMixin, SoftDeleteMixin):
    """Represents a scheduled booking with a customer."""

    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant isolation key",
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Business where appointment takes place",
    )

    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Service booked (e.g. Dental Checkup)",
    )

    customer_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Full name of customer/patient",
    )

    customer_phone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Customer phone number (E.164 format preferred)",
    )

    customer_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Customer email address for calendar invites / receipts",
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Date and time when appointment starts (UTC timestamp)",
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        server_default="30",
        comment="Duration of appointment slot in minutes",
    )

    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointmentstatus"),
        nullable=False,
        default=AppointmentStatus.CONFIRMED,
        server_default=AppointmentStatus.CONFIRMED.value,
        index=True,
        comment="Current status of the appointment",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notes taken by AI receptionist during the call or entered by staff",
    )

    original_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Previous time before rescheduling",
    )

    created_by_agent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="True if booked automatically by AI voice agent during call",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    service: Mapped["Service | None"] = relationship(  # noqa: F821
        "Service",
    )

    business: Mapped["Business"] = relationship(  # noqa: F821
        "Business",
    )

    __table_args__ = (
        Index("ix_appointments_tenant_scheduled", "tenant_id", "scheduled_at"),
        Index("ix_appointments_business_status", "business_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id} customer='{self.customer_name}' "
            f"time={self.scheduled_at} status={self.status.value}>"
        )

