"""
app/models/user.py — User Model

CONCEPT: Users vs Tenants
==========================
User  = A PERSON who has an account (email + password).
Tenant = An ORGANIZATION using VoxAI.

One user CAN belong to multiple tenants:
  - Dr. Sharma logs in as a user.
  - They are OWNER of "Sunrise Clinic" (Tenant A).
  - They are ADMIN of "City Hospital" (Tenant B).

The link between User and Tenant is the `TenantUser` join table.

CONCEPT: Password Hashing
==========================
We NEVER store plain-text passwords. Never.
If our database is stolen, attackers should NOT be able to recover passwords.

bcrypt hashing:
  "mypassword123" → "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj2NkJUn5Iu."

The hash is one-way — you can't reverse it.
To verify: re-hash the attempt and compare hashes.

Salt: bcrypt adds a random "salt" before hashing.
      Same password → different hash each time → rainbow table attacks fail.

WHY NOT MD5/SHA256?
MD5/SHA256 are fast → attackers can try billions/second.
bcrypt is intentionally SLOW (~100ms) → attacking is impractical.

CONCEPT: is_verified
====================
When a user registers, they get is_verified=False.
We should send a verification email.
Unverified users might have limited access.
(Email verification implemented in a later sprint.)
"""

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class User(Base, TimestampMixin, SoftDeleteMixin):
    """
    Represents a person who can log into VoxAI.

    Users are GLOBAL — they exist independently of any tenant.
    Their association with tenants (and their role) is in TenantUser.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Authentication Fields ─────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Login identifier — unique across all tenants",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt hash — NEVER store plain text",
    )

    # ── Profile Fields ────────────────────────────────────────────────────────
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ── Status Fields ─────────────────────────────────────────────────────────
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True after email verification",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="False = user suspended/banned",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant_memberships: Mapped[list["TenantUser"]] = relationship(  # noqa: F821
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
