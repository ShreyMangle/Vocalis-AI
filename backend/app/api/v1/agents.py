"""
app/api/v1/agents.py — Voice Agent Configuration & Runtime Telemetry

Routes:
  GET   /api/v1/agents                → Get active voice agent configuration
  PUT   /api/v1/agents                → Upsert voice agent configuration (ADMIN+)
  PATCH /api/v1/agents                → Partially update agent configuration (ADMIN+)
  POST  /api/v1/agents/preview-prompt → Render compiled system prompt with live context
  GET   /api/v1/agents/voices         → List curated catalog of selectable TTS voices
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    CurrentUser,
    require_authenticated,
    require_role,
)
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.agent import AgentConfig
from app.models.business import Business, WorkingHours
from app.models.service import Service
from app.models.tenant_user import UserRole
from app.schemas.agent import (
    AgentConfigCreateRequest,
    AgentConfigResponse,
    AgentConfigUpdateRequest,
    PromptPreviewResponse,
    VoiceCatalogItem,
)
from app.services.prompt_compiler import compile_voice_system_prompt

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["Voice Agent Studio"])

# Curated catalog of production TTS voices
VOICE_CATALOG: list[VoiceCatalogItem] = [
    VoiceCatalogItem(
        provider="cartesia",
        voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",
        name="Sarah",
        gender="Female",
        accent="American (Warm)",
        description="Warm, natural, and conversational tone ideal for healthcare and front-desk reception.",
        sample_preview_text="Hello! Thank you for calling Sunrise Clinic. How can I help you today?",
        recommended=True,
    ),
    VoiceCatalogItem(
        provider="cartesia",
        voice_id="694f9389-aac1-45b6-b726-9d9369183238",
        name="David",
        gender="Male",
        accent="American (Professional)",
        description="Clear, calm, and articulate baritone well-suited for legal and executive booking.",
        sample_preview_text="Good afternoon. You've reached our scheduling desk. How may I direct your call?",
        recommended=False,
    ),
    VoiceCatalogItem(
        provider="cartesia",
        voice_id="b7d50908-b17c-442d-ad8d-810c63997ed9",
        name="Priya",
        gender="Female",
        accent="Indian (English)",
        description="Polite, friendly Indian English accent optimized for India domestic business operations.",
        sample_preview_text="Namaste, welcome to Sunrise Clinic. I am Priya, how can I assist you with an appointment?",
        recommended=True,
    ),
    VoiceCatalogItem(
        provider="deepgram",
        voice_id="aura-asteria-en",
        name="Asteria",
        gender="Female",
        accent="American",
        description="Deepgram Aura low-latency streaming voice with expressive pacing.",
        sample_preview_text="Thanks for getting in touch. When would you like to schedule your consultation?",
        recommended=False,
    ),
]


@router.get(
    "",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current voice agent configuration",
)
async def get_agent_config(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> AgentConfigResponse:
    """Fetch the agent config for the authenticated tenant."""
    result = await session.execute(
        select(AgentConfig).where(
            AgentConfig.tenant_id == current_user.tenant_id,
            AgentConfig.is_deleted == False,  # noqa: E712
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise NotFoundError(
            "Agent configuration not found for this organization.",
            code="AGENT_NOT_FOUND",
        )
    return AgentConfigResponse.model_validate(agent)


@router.put(
    "",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or overwrite voice agent configuration",
)
async def upsert_agent_config(
    payload: AgentConfigCreateRequest,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> AgentConfigResponse:
    """Create or overwrite agent config."""
    # Look up business profile
    b_res = await session.execute(
        select(Business).where(
            Business.tenant_id == current_user.tenant_id,
            Business.is_deleted == False,  # noqa: E712
        )
    )
    business = b_res.scalar_one_or_none()
    business_id = business.id if business else None

    # Check if agent already exists
    result = await session.execute(
        select(AgentConfig).where(
            AgentConfig.tenant_id == current_user.tenant_id,
            AgentConfig.is_deleted == False,  # noqa: E712
        )
    )
    agent = result.scalar_one_or_none()

    if agent is None:
        agent = AgentConfig(
            tenant_id=current_user.tenant_id,
            business_id=business_id,
            **payload.model_dump(),
        )
        session.add(agent)
    else:
        for field, value in payload.model_dump().items():
            setattr(agent, field, value)
        if business_id and not agent.business_id:
            agent.business_id = business_id
        agent.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(agent)

    logger.info(
        "Agent config upserted",
        agent_id=str(agent.id),
        agent_name=agent.name,
        tenant_id=str(current_user.tenant_id),
    )

    return AgentConfigResponse.model_validate(agent)


@router.patch(
    "",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update agent configuration",
)
async def patch_agent_config(
    payload: AgentConfigUpdateRequest,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> AgentConfigResponse:
    """Partially update agent config fields."""
    result = await session.execute(
        select(AgentConfig).where(
            AgentConfig.tenant_id == current_user.tenant_id,
            AgentConfig.is_deleted == False,  # noqa: E712
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise NotFoundError("Agent configuration not found.", code="AGENT_NOT_FOUND")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)

    agent.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(agent)

    logger.info(
        "Agent config patched",
        agent_id=str(agent.id),
        updated_fields=list(update_data.keys()),
        tenant_id=str(current_user.tenant_id),
    )

    return AgentConfigResponse.model_validate(agent)


@router.post(
    "/preview-prompt",
    response_model=PromptPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate compiled runtime system prompt",
)
async def preview_system_prompt(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> PromptPreviewResponse:
    """Compile the full system prompt using live business, hours, and services data."""
    # 1. Fetch Agent
    a_res = await session.execute(
        select(AgentConfig).where(
            AgentConfig.tenant_id == current_user.tenant_id,
            AgentConfig.is_deleted == False,  # noqa: E712
        )
    )
    agent = a_res.scalar_one_or_none()
    if agent is None:
        # Provide default virtual agent for prompt inspection if not configured yet
        agent = AgentConfig(
            tenant_id=current_user.tenant_id,
            name="Sarah",
            role_description="Front desk receptionist and appointment scheduling coordinator",
            system_prompt="",
            greeting_message="Hello! Thank you for calling. How can I assist you today?",
            fallback_message="I apologize, I didn't quite catch that. Could you please repeat that?",
        )

    # 2. Fetch Business
    b_res = await session.execute(
        select(Business).where(
            Business.tenant_id == current_user.tenant_id,
            Business.is_deleted == False,  # noqa: E712
        )
    )
    business = b_res.scalar_one_or_none()

    # 3. Fetch Working Hours
    wh_list = []
    if business:
        wh_res = await session.execute(
            select(WorkingHours)
            .where(WorkingHours.business_id == business.id)
            .order_by(WorkingHours.day_of_week)
        )
        wh_list = list(wh_res.scalars().all())

    # 4. Fetch Services
    services_list = []
    if business:
        s_res = await session.execute(
            select(Service).where(
                Service.business_id == business.id,
                Service.is_active == True,  # noqa: E712
                Service.is_deleted == False,  # noqa: E712
            )
        )
        services_list = list(s_res.scalars().all())

    compiled = compile_voice_system_prompt(
        agent=agent,
        business=business,
        working_hours=wh_list,
        services=services_list,
    )

    return PromptPreviewResponse(
        compiled_prompt=compiled,
        agent_name=agent.name,
        business_name=business.name if business else None,
        timezone=business.timezone if business else "UTC",
        services_count=len(services_list),
        working_hours_count=len(wh_list),
    )


@router.get(
    "/voices",
    response_model=list[VoiceCatalogItem],
    status_code=status.HTTP_200_OK,
    summary="List available TTS voices",
)
async def list_voice_catalog(
    current_user: CurrentUser = Depends(require_authenticated),
) -> list[VoiceCatalogItem]:
    """Returns the catalog of selectable voices."""
    return VOICE_CATALOG

