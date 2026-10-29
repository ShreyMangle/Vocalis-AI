"""Agent configuration table

Revision ID: 004
Revises: 003
Create Date: 2026-10-29

Creates:
  - agent_configs → configuration for AI voice receptionist
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
            index=True,
        ),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False, server_default="Sarah"),
        sa.Column(
            "role_description",
            sa.String(500),
            nullable=False,
            server_default="Front desk receptionist and appointment scheduling coordinator",
        ),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column(
            "greeting_message",
            sa.Text(),
            nullable=False,
            server_default="Hello! Thank you for calling. How can I assist you today?",
        ),
        sa.Column(
            "fallback_message",
            sa.Text(),
            nullable=False,
            server_default="I apologize, I didn't quite catch that. Could you please repeat that?",
        ),
        sa.Column("voice_provider", sa.String(50), nullable=False, server_default="cartesia"),
        sa.Column(
            "voice_id",
            sa.String(150),
            nullable=False,
            server_default="a0e99841-438c-4a64-b679-ae501e7d6091",
        ),
        sa.Column("speech_speed", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("llm_provider", sa.String(50), nullable=False, server_default="openai"),
        sa.Column("llm_model", sa.String(100), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("vad_sensitivity", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("primary_language", sa.String(20), nullable=False, server_default="en"),
        sa.Column("supported_languages", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("transfer_phone_number", sa.String(30), nullable=True),
        sa.Column("webhook_url", sa.String(500), nullable=True),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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

    op.create_index("ix_agent_configs_tenant_active", "agent_configs", ["tenant_id", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_agent_configs_tenant_active", table_name="agent_configs")
    op.drop_table("agent_configs")

