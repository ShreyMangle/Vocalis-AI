"""
app/models/agent.py — AI Voice Agent Configuration Model

CONCEPT: The AI Voice Agent Persona
=====================================
In VoxAI, an "Agent" is the AI receptionist that handles phone calls.
Each business customizes:
  - Identity: Name (e.g. "Sarah"), role, tone of voice
  - Voice Engine: TTS voice ID (Cartesia, Deepgram, Azure), speaking speed
  - LLM Intelligence: Model (GPT-4o-mini, Groq Llama-3.3-70b), temperature
  - Telephony & Audio: VAD sensitivity, transfer phone number for escalation
  - Actions & Integrations: Post-call webhooks, SMS confirmation dispatch
"""

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Index, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class AgentConfig(Base, TimestampMixin, SoftDeleteMixin):
    """
    Configuration profile for an AI Voice Receptionist.
    
    Each tenant has one primary agent configuration (1-to-1 relationship).
    """

    __tablename__ = "agent_configs"

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
        comment="Tenant that owns this voice agent",
    )

    business_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Associated business profile",
    )

    # ── Identity & Persona ───────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Sarah",
        server_default="Sarah",
        comment="Name caller hears (e.g. 'I'm Sarah from Sunrise Clinic')",
    )

    role_description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="Front desk receptionist and appointment scheduling coordinator",
        server_default="Front desk receptionist and appointment scheduling coordinator",
        comment="Role summary injected into LLM system prompt",
    )

    system_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Custom instructions, company policies, and conversational guardrails",
    )

    greeting_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Hello! Thank you for calling. How can I assist you today?",
        server_default="Hello! Thank you for calling. How can I assist you today?",
        comment="Initial opening sentence spoken immediately on call connect",
    )

    fallback_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="I apologize, I didn't quite catch that. Could you please repeat that?",
        server_default="I apologize, I didn't quite catch that. Could you repeat that?",
        comment="Spoken when STT fails or LLM produces an unparseable response",
    )

    # ── Voice Engine (TTS) ───────────────────────────────────────────────────
    voice_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="cartesia",
        server_default="cartesia",
        comment="TTS provider: cartesia | deepgram | elevenlabs | azure",
    )

    voice_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        default="a0e99841-438c-4a64-b679-ae501e7d6091",
        server_default="a0e99841-438c-4a64-b679-ae501e7d6091",
        comment="Specific voice identifier within the provider",
    )

    speech_speed: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default="1.0",
        comment="Speech playback rate (0.7 = slower, 1.0 = normal, 1.3 = fast)",
    )

    # ── LLM Engine ───────────────────────────────────────────────────────────
    llm_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="openai",
        server_default="openai",
        comment="LLM provider: openai | groq | anthropic | gemini",
    )

    llm_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="gpt-4o-mini",
        server_default="gpt-4o-mini",
        comment="LLM model name (e.g. gpt-4o-mini, llama-3.3-70b-versatile)",
    )

    temperature: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.3,
        server_default="0.3",
        comment="LLM temperature (0.0 to 1.0; low value ensures factual accuracy)",
    )

    # ── Telephony & Conversational Flow ──────────────────────────────────────
    vad_sensitivity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        server_default="normal",
        comment="Voice activity detection sensitivity: low | normal | high",
    )

    primary_language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="en",
        server_default="en",
        comment="Primary spoken language code (e.g. en, hi)",
    )

    supported_languages: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default="[]",
        comment="List of languages the agent can converse in (e.g. ['en', 'hi'])",
    )

    transfer_phone_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="E.164 phone number to escalate to human staff if requested",
    )

    webhook_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Webhook URL called after call completion with transcript & analytics",
    )

    sms_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Whether to send automated SMS confirmation after booking",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Whether agent handles incoming calls or rejects them",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship(  # noqa: F821
        back_populates="agent_config",
    )

    business: Mapped["Business | None"] = relationship(  # noqa: F821
        back_populates="agent_config",
    )

    __table_args__ = (
        Index("ix_agent_configs_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<AgentConfig id={self.id} name={self.name} provider={self.llm_provider} model={self.llm_model}>"

