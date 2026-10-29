"""
app/models/business.py — Business Profile & Working Hours Models

CONCEPT: Business Profile vs Tenant
===================================
A Tenant represents the billing/SaaS account (slug, plan, active status).
A Business represents the operational entity (Sunrise Clinic, Dr. Sharma's Office).
It holds:
  - Industry vertical (healthcare, hospitality, retail, etc.)
  - Contact details (phone, email, address, website)
  - Operating timezone (crucial for appointment scheduling & call window checks)
  - Operating hours (Monday–Sunday open/close times, closed days)

CONCEPT: Working Hours & AI Call Routing
========================================
When a patient calls outside working hours:
  - The AI agent knows the clinic is closed.
  - It can inform the caller: "Our clinic is currently closed. We open at 9 AM tomorrow. Would you like to leave a message or book an appointment for tomorrow?"
"""

import enum
import uuid
from datetime import time

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class DayOfWeek(str, enum.Enum):
    """Days of the week for scheduling and working hours."""
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class Business(Base, TimestampMixin, SoftDeleteMixin):
    """
    Business Profile for a tenant.
    
    Each tenant has one primary business profile (1-to-1 relationship).
    """

    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="Tenant that owns this business profile",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Business display name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Short summary of what this business does (used in AI agent prompt)",
    )

    industry: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="healthcare",
        server_default="healthcare",
        comment="Industry vertical (healthcare, dental, hospitality, etc.)",
    )

    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Asia/Kolkata",
        server_default="Asia/Kolkata",
        comment="IANA Timezone (e.g. Asia/Kolkata, America/New_York)",
    )

    phone_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Official contact phone number",
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Contact email address",
    )

    website: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Public website URL",
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Physical clinic/office address",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship(  # noqa: F821
        back_populates="business",
    )

    working_hours: Mapped[list["WorkingHours"]] = relationship(
        back_populates="business",
        cascade="all, delete-orphan",
        order_by="WorkingHours.day_of_week",
    )

    services: Mapped[list["Service"]] = relationship(  # noqa: F821
        "Service",
        back_populates="business",
        cascade="all, delete-orphan",
        order_by="Service.name",
    )

    agent_config: Mapped["AgentConfig | None"] = relationship(  # noqa: F821
        "AgentConfig",
        back_populates="business",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<Business id={self.id} name={self.name} tenant_id={self.tenant_id}>"


class WorkingHours(Base, TimestampMixin):
    """
    Weekly operating hours for a business.
    
    Stores the schedule for each day of the week (Monday through Sunday).
    """

    __tablename__ = "working_hours"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Multi-tenancy isolation key",
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated business profile",
    )

    day_of_week: Mapped[DayOfWeek] = mapped_column(
        Enum(DayOfWeek, name="dayofweek"),
        nullable=False,
        comment="Day of the week",
    )

    open_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
        comment="Opening time (e.g. 09:00:00). Null if is_closed is True.",
    )

    close_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
        comment="Closing time (e.g. 18:00:00). Null if is_closed is True.",
    )

    is_closed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True if business is closed on this day",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    business: Mapped["Business"] = relationship(
        back_populates="working_hours",
    )

    __table_args__ = (
        UniqueConstraint("business_id", "day_of_week", name="uq_business_working_hours_day"),
        Index("ix_working_hours_tenant_day", "tenant_id", "day_of_week"),
    )

    def __repr__(self) -> str:
        return (
            f"<WorkingHours day={self.day_of_week.value} "
            f"open={self.open_time} close={self.close_time} closed={self.is_closed}>"
        )
