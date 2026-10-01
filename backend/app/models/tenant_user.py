"""
app/models/tenant_user.py — TenantUser Join Model (Many-to-Many with Role)

CONCEPT: Many-to-Many Relationships
=====================================
A User can belong to many Tenants.
A Tenant can have many Users.
This is called a "many-to-many" relationship.

In SQL, this needs a JOIN TABLE:
  users ──< tenant_users >── tenants
                │
                └── + role (OWNER / ADMIN / STAFF)
                └── + is_active
                └── + timestamps

A plain join table just has two foreign keys.
Our join table (TenantUser) is "enhanced" — it carries extra data (role).
This is why we give it its own model instead of a simple association table.

CONCEPT: RBAC (Role-Based Access Control)
==========================================
RBAC = different users have different permissions based on their role.

In VoxAI:
  OWNER:  Full control — can delete tenant, manage billing, all settings
  ADMIN:  Can manage agents, knowledge, calls — but NOT billing/deletion
  STAFF:  Read-only access — can view calls, transcripts

Permissions are checked in the API layer using the role from this table.
We NEVER rely on frontend-only restrictions — always check on the backend.

CONCEPT: UniqueConstraint
===========================
`UniqueConstraint("tenant_id", "user_id")` means:
  The COMBINATION of tenant_id + user_id must be unique.
  A user can only be in the same tenant ONCE.
  But the same user can appear in different tenants (different rows).

  OK:   (tenant_A, user_1, OWNER)
  OK:   (tenant_B, user_1, ADMIN)  ← same user, different tenant
  FAIL: (tenant_A, user_1, ADMIN)  ← same user+tenant already exists
"""

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    """
    User roles within a tenant.

    str + enum.Enum means the value is also a string.
    UserRole.OWNER == "OWNER"  ← True
    This makes JSON serialization automatic.
    """

    OWNER = "OWNER"    # Full control
    ADMIN = "ADMIN"    # Operational control
    STAFF = "STAFF"    # Read + limited write


class TenantUser(Base, TimestampMixin):
    """
    Links a User to a Tenant with a specific Role.

    This is the bridge between global users and tenant organizations.
    Every protected API endpoint checks this table to verify:
      1. Does this user belong to this tenant?
      2. What is their role?
    """

    __tablename__ = "tenant_users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Foreign Keys ──────────────────────────────────────────────────────────
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        # ondelete="CASCADE" = if the Tenant is deleted, all TenantUser rows
        # pointing to it are automatically deleted too.
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Role & Status ─────────────────────────────────────────────────────────
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole"),
        nullable=False,
        default=UserRole.OWNER,
        comment="Permission level within this specific tenant",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="False = user removed from tenant (without deleting their account)",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship(  # noqa: F821
        back_populates="tenant_memberships",
    )
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="tenant_memberships",
    )

    # ── Table-Level Constraints ───────────────────────────────────────────────
    __table_args__ = (
        # A user can only appear once per tenant
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_users_tenant_user"),
        # Composite index for fast "get all users for this tenant" queries
        Index("ix_tenant_users_tenant_id_user_id", "tenant_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<TenantUser tenant={self.tenant_id} user={self.user_id} role={self.role}>"
