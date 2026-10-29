"""Appointments and calendar table

Revision ID: 005
Revises: 004
Create Date: 2026-10-29

Creates:
  - appointments → customer scheduled bookings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── appointmentstatus enum ──────────────────────────────────────────────
    op.execute(
        "CREATE TYPE appointmentstatus AS ENUM ("
        "'PENDING', 'CONFIRMED', 'CANCELLED', 'RESCHEDULED', 'COMPLETED', 'NO_SHOW'"
        ")"
    )

    # ── appointments table ──────────────────────────────────────────────────
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_phone", sa.String(50), nullable=False, index=True),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "CONFIRMED",
                "CANCELLED",
                "RESCHEDULED",
                "COMPLETED",
                "NO_SHOW",
                name="appointmentstatus",
            ),
            nullable=False,
            server_default="CONFIRMED",
            index=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("original_scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_agent", sa.Boolean(), nullable=False, server_default="true"),
        # TimestampMixin
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # SoftDeleteMixin
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_appointments_tenant_scheduled",
        "appointments",
        ["tenant_id", "scheduled_at"],
    )
    op.create_index(
        "ix_appointments_business_status",
        "appointments",
        ["business_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_appointments_business_status", table_name="appointments")
    op.drop_index("ix_appointments_tenant_scheduled", table_name="appointments")
    op.drop_table("appointments")
    op.execute("DROP TYPE appointmentstatus")

