"""
app/models/service.py — Business Service Model

CONCEPT: Services in AI Voice SaaS
====================================
Every business provides specific services:
  - Dental Clinic: "Routine Checkup" (30 min, ₹500), "Root Canal" (60 min, ₹3000)
  - Salon: "Haircut & Styling" (45 min, ₹800), "Beard Grooming" (20 min, ₹300)
  - Consulting: "Initial Consultation" (30 min, Free)

When an AI Voice Agent answers a call:
  1. It can answer: "What services do you provide and what are your prices?"
  2. When a caller asks to book an appointment:
     The agent checks the duration of that specific service (e.g. 45 min)
     and calculates appropriate calendar slot availability!
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Service(Base, TimestampMixin, SoftDeleteMixin):
    """
    Represents an offered service or treatment by a business.
    """

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant that owns this service (multi-tenancy isolation)",
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Business profile offering this service",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Name of the service (e.g. 'General Consultation')",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of what is included in this service (used in AI prompt)",
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        server_default="30",
        comment="Duration in minutes needed for scheduling slots",
    )

    price: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Price in smallest currency unit (e.g. paise or cents)",
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="INR",
        server_default="INR",
        comment="ISO 4217 currency code (e.g. INR, USD, EUR)",
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Optional service category (e.g. 'Dental', 'Cosmetic')",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Whether this service is currently available for booking",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    business: Mapped["Business"] = relationship(  # noqa: F821
        back_populates="services",
    )

    __table_args__ = (
        Index("ix_services_tenant_active", "tenant_id", "is_active"),
        Index("ix_services_business_active", "business_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Service id={self.id} name={self.name} duration={self.duration_minutes}m price={self.price}>"

