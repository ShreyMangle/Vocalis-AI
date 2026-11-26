"""Calls table and telemetry

Revision ID: 006
Revises: 005
Create Date: 2026-10-29

Creates:
  - calls → telephony call logs, transcripts, and latency metrics
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Enums ────────────────────────────────────────────────────────────────
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'calldirection') THEN "
        "CREATE TYPE calldirection AS ENUM ('INBOUND', 'OUTBOUND'); "
        "END IF; "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'callstatus') THEN "
        "CREATE TYPE callstatus AS ENUM ('IN_PROGRESS', 'COMPLETED', 'BUSY', 'NO_ANSWER', 'FAILED'); "
        "END IF; "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'callsentiment') THEN "
        "CREATE TYPE callsentiment AS ENUM ('POSITIVE', 'NEUTRAL', 'NEGATIVE'); "
        "END IF; "
        "END $$;"
    )

    # ── calls table ──────────────────────────────────────────────────────────
    op.create_table(
        "calls",
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
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("caller_phone", sa.String(50), nullable=False, index=True),
        sa.Column(
            "direction",
            sa.Enum("INBOUND", "OUTBOUND", name="calldirection", create_type=False),
            nullable=False,
            server_default="INBOUND",
        ),
        sa.Column(
            "status",
            sa.Enum("IN_PROGRESS", "COMPLETED", "BUSY", "NO_ANSWER", "FAILED", name="callstatus", create_type=False),
            nullable=False,
            server_default="COMPLETED",
            index=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recording_url", sa.String(500), nullable=True),
        sa.Column("transcript", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "sentiment",
            sa.Enum("POSITIVE", "NEUTRAL", "NEGATIVE", name="callsentiment", create_type=False),
            nullable=False,
            server_default="NEUTRAL",
            index=True,
        ),
        sa.Column("intent", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("stt_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tts_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_cents", sa.Integer(), nullable=False, server_default="0"),
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

    op.create_index("ix_calls_tenant_started", "calls", ["tenant_id", "started_at"])
    op.create_index("ix_calls_business_sentiment", "calls", ["business_id", "sentiment"])


def downgrade() -> None:
    op.drop_index("ix_calls_business_sentiment", table_name="calls")
    op.drop_index("ix_calls_tenant_started", table_name="calls")
    op.drop_table("calls")
    op.execute("DROP TYPE callsentiment")
    op.execute("DROP TYPE callstatus")
    op.execute("DROP TYPE calldirection")

