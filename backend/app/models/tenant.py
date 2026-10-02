"""
app/models/tenant.py — Tenant (Business Organization) Model

CONCEPT: What is a Tenant?
===========================
In a multi-tenant SaaS, a "tenant" is ONE customer organization.

Example:
  Tenant A = "Sunrise Clinic" (has their own doctors, appointments, AI agent)
  Tenant B = "Hotel Pearl"    (has their own rooms, bookings, AI agent)

Both tenants use the SAME application code and database,
BUT their data is completely isolated from each other.

Think of it like a shared office building:
  - All offices share the same building (our servers)
  - Each office has its own locked door (tenant_id isolation)
  - No one can enter another office

HOW ISOLATION WORKS:
  Every table that contains tenant data has a `tenant_id` column.
  Every query MUST filter by `tenant_id`.
  We enforce this in our repository/service layer — not just trusting routes.

SLUG:
  A slug is a URL-safe, human-readable identifier.
  "Sunrise Clinic" → "sunrise-clinic"
  Used in URLs: /tenants/sunrise-clinic/dashboard
"""

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Tenant(Base, TimestampMixin, SoftDeleteMixin):
    """
    Represents one business organization using VoxAI.

    Lifecycle:
      1. Business owner registers → Tenant created automatically.
      2. Owner configures their business, AI agent, etc.
      3. Tenant can be suspended (is_active=False) without deleting data.
      4. Soft delete preserves all data for compliance/billing.
    """

    __tablename__ = "tenants"

    # ── Primary Key ──────────────────────────────────────────────────────────
    # UUID generated in Python (not by DB) so we know the ID before insertion.
    # server_default generates UUID in DB as fallback.
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Core Fields ──────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name: 'Sunrise Clinic'",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="URL-safe identifier: 'sunrise-clinic'",
    )
    plan: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="free",
        server_default="free",
        comment="Subscription plan: free | starter | business | enterprise",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="False = tenant suspended, login blocked",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    # back_populates wires both sides of the relationship.
    # lazy="selectin" means: when you load a Tenant, also load tenant_memberships
    # in a single additional SELECT (not N+1 queries).
    tenant_memberships: Mapped[list["TenantUser"]] = relationship(  # noqa: F821
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    business: Mapped["Business | None"] = relationship(  # noqa: F821
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug} plan={self.plan}>"
