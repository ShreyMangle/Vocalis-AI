"""Business profile and working hours tables

Revision ID: 002
Revises: 001
Create Date: 2026-10-02

Creates:
  - businesses    → operational business profile per tenant (1-to-1)
  - working_hours → weekly operating schedule per business (Mon-Sun)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── dayofweek enum ────────────────────────────────────────────────────────
    op.execute(
        "CREATE TYPE dayofweek AS ENUM ("
        "'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'"
        ")"
    )

    # ── businesses ────────────────────────────────────────────────────────────
    op.create_table(
        "businesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(100), nullable=False, server_default="healthcare"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
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
    op.create_index("ix_businesses_tenant_id", "businesses", ["tenant_id"], unique=True)
    op.create_index("ix_businesses_is_deleted", "businesses", ["is_deleted"])

    # ── working_hours ─────────────────────────────────────────────────────────
    op.create_table(
        "working_hours",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "day_of_week",
            postgresql.ENUM(
                "MONDAY",
                "TUESDAY",
                "WEDNESDAY",
                "THURSDAY",
                "FRIDAY",
                "SATURDAY",
                "SUNDAY",
                name="dayofweek",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("open_time", sa.Time(), nullable=True),
        sa.Column("close_time", sa.Time(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default="false"),
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
    )
    op.create_index("ix_working_hours_tenant_id", "working_hours", ["tenant_id"])
    op.create_index("ix_working_hours_business_id", "working_hours", ["business_id"])
    op.create_index(
        "ix_working_hours_tenant_day",
        "working_hours",
        ["tenant_id", "day_of_week"],
    )
    op.create_unique_constraint(
        "uq_business_working_hours_day",
        "working_hours",
        ["business_id", "day_of_week"],
    )


def downgrade() -> None:
    op.drop_table("working_hours")
    op.drop_table("businesses")
    op.execute("DROP TYPE dayofweek")
