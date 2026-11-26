"""
app/schemas/agent.py — AI Voice Agent Schemas

Pydantic schemas for:
  - Agent configuration create, update, and read
  - Validation of speech speeds, temperatures, providers, and models
  - Prompt preview compilation responses
  - Voice engine catalog listings
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentConfigCreateRequest(BaseModel):
    """Payload to configure or upsert the AI voice agent."""
    name: str = Field(
        default="Sarah",
        min_length=1,
        max_length=100,
        description="Name of the AI voice receptionist",
        examples=["Sarah"],
    )
    role_description: str = Field(
        default="Front desk receptionist and appointment scheduling coordinator",
        max_length=500,
        description="Short description of role and personality",
        examples=["Courteous clinic coordinator and appointment scheduler"],
    )
    system_prompt: str | None = Field(
        default=None,
        max_length=5000,
        description="Custom business instructions and policy guardrails",
        examples=["Always ask if caller is a new or returning patient before booking."],
    )
    greeting_message: str = Field(
        default="Hello! Thank you for calling. How can I assist you today?",
        max_length=1000,
        description="Opening line spoken immediately upon call connection",
        examples=["Hello! Thank you for calling Sunrise Clinic. How can I assist you today?"],
    )
    fallback_message: str = Field(
        default="I apologize, I didn't quite catch that. Could you please repeat that?",
        max_length=500,
        description="Phrase spoken when utterance is not understood",
    )
    voice_provider: str = Field(
        default="edge",
        pattern="^(edge|cartesia|deepgram|sarvam|elevenlabs|azure)$",
        description="TTS provider platform (edge = free neural TTS)",
    )
    voice_id: str = Field(
        default="en-IN-NeerjaNeural",
        max_length=150,
        description="Provider-specific voice ID",
    )
    speech_speed: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Speech playback speed multiplier",
    )
    llm_provider: str = Field(
        default="groq",
        pattern="^(openai|groq|anthropic|gemini)$",
        description="LLM provider platform",
    )
    llm_model: str = Field(
        default="llama-3.3-70b-versatile",
        max_length=100,
        description="Target model identifier",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Sampling temperature (lower = more deterministic)",
    )
    vad_sensitivity: str = Field(
        default="normal",
        pattern="^(low|normal|high)$",
        description="Voice activity detection sensitivity",
    )
    primary_language: str = Field(
        default="en",
        max_length=20,
        description="Primary spoken language code",
    )
    supported_languages: list[str] = Field(
        default_factory=lambda: ["en", "hi"],
        description="Languages the agent can comprehend and speak",
    )
    transfer_phone_number: str | None = Field(
        default=None,
        max_length=30,
        description="E.164 phone number to route call if human escalation requested",
    )
    webhook_url: str | None = Field(
        default=None,
        max_length=500,
        description="Webhook endpoint for post-call data dispatch",
    )
    sms_enabled: bool = Field(
        default=True,
        description="Dispatch automated SMS confirmation after booking",
    )
    is_active: bool = Field(
        default=True,
        description="Agent active status",
    )


class AgentConfigUpdateRequest(BaseModel):
    """Payload to partially update an agent's configuration."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role_description: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, max_length=5000)
    greeting_message: str | None = Field(default=None, max_length=1000)
    fallback_message: str | None = Field(default=None, max_length=500)
    voice_provider: str | None = Field(default=None, pattern="^(edge|cartesia|deepgram|sarvam|elevenlabs|azure)$")
    voice_id: str | None = Field(default=None, max_length=150)
    speech_speed: float | None = Field(default=None, ge=0.5, le=2.0)
    llm_provider: str | None = Field(default=None, pattern="^(openai|groq|anthropic|gemini)$")
    llm_model: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    vad_sensitivity: str | None = Field(default=None, pattern="^(low|normal|high)$")
    primary_language: str | None = Field(default=None, max_length=20)
    supported_languages: list[str] | None = None
    transfer_phone_number: str | None = Field(default=None, max_length=30)
    webhook_url: str | None = Field(default=None, max_length=500)
    sms_enabled: bool | None = None
    is_active: bool | None = None


class AgentConfigResponse(BaseModel):
    """Public representation of an agent configuration."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    business_id: uuid.UUID | None
    name: str
    role_description: str
    system_prompt: str | None
    greeting_message: str
    fallback_message: str
    voice_provider: str
    voice_id: str
    speech_speed: float
    llm_provider: str
    llm_model: str
    temperature: float
    vad_sensitivity: str
    primary_language: str
    supported_languages: list[str]
    transfer_phone_number: str | None
    webhook_url: str | None
    sms_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptPreviewResponse(BaseModel):
    """Details and rendered system prompt for runtime LLM execution."""
    compiled_prompt: str
    agent_name: str
    business_name: str | None
    timezone: str
    services_count: int
    working_hours_count: int


class VoiceCatalogItem(BaseModel):
    """Catalog entry for selectable TTS voices."""
    provider: str
    voice_id: str
    name: str
    gender: str
    accent: str
    description: str
    sample_preview_text: str
    recommended: bool = False

