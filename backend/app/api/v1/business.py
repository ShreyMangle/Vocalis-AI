"""
app/api/v1/business.py — Business Profile & Working Hours Management

Routes:
  GET   /api/v1/business               → Get organization business profile
  PUT   /api/v1/business               → Create or overwrite business profile (ADMIN+)
  PATCH /api/v1/business               → Partially update business profile (ADMIN+)
  GET   /api/v1/business/working-hours → Get operating schedule (Mon-Sun)
  PUT   /api/v1/business/working-hours → Batch update operating schedule (ADMIN+)
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
from app.models.business import Business, WorkingHours
from app.models.tenant_user import UserRole
from app.schemas.business import (
    BusinessCreateRequest,
    BusinessResponse,
    BusinessUpdateRequest,
    WorkingHoursResponse,
    WorkingHoursUpdateBatchRequest,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/business", tags=["Business Onboarding & Profile"])


# =============================================================================
# BUSINESS PROFILE ENDPOINTS
# =============================================================================

@router.get(
    "",
    response_model=BusinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get business profile",
    description="Returns the operational business profile for the authenticated tenant.",
)
async def get_business_profile(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> BusinessResponse:
    """Fetch the business profile for the current tenant."""
    result = await session.execute(
        select(Business).where(
            Business.tenant_id == current_user.tenant_id,
            Business.is_deleted == False,  # noqa: E712
        )
    )
    business = result.scalar_one_or_none()

    if business is None:
        raise NotFoundError(
            "Business profile not yet configured for this organization.",
            code="BUSINESS_NOT_FOUND",
        )

    return BusinessResponse.model_validate(business)


@router.put(
    "",
    response_model=BusinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or update business profile",
    description="Upserts the business profile for the current tenant. Requires ADMIN or OWNER role.",
)
async def upsert_business_profile(
    body: BusinessCreateRequest,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> BusinessResponse:
    """Upserts the operational profile for the tenant."""
    result = await session.execute(
        select(Business).where(Business.tenant_id == current_user.tenant_id)
    )
    business = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if business is not None:
        # Update existing profile
        business.name = body.name.strip()
        business.description = body.description.strip() if body.description else None
        business.industry = body.industry.strip()
        business.timezone = body.timezone
        business.phone_number = body.phone_number.strip() if body.phone_number else None
        business.email = body.email.lower().strip() if body.email else None
        business.website = body.website.strip() if body.website else None
        business.address = body.address.strip() if body.address else None
        business.is_deleted = False
        business.deleted_at = None
        business.updated_at = now
    else:
        # Create brand-new profile
        business = Business(
            id=uuid.uuid4(),
            tenant_id=current_user.tenant_id,
            name=body.name.strip(),
            description=body.description.strip() if body.description else None,
            industry=body.industry.strip(),
            timezone=body.timezone,
            phone_number=body.phone_number.strip() if body.phone_number else None,
            email=body.email.lower().strip() if body.email else None,
            website=body.website.strip() if body.website else None,
            address=body.address.strip() if body.address else None,
            created_at=now,
            updated_at=now,
        )
        session.add(business)

    await session.flush()

    logger.info(
        "Business profile configured",
        tenant_id=str(current_user.tenant_id),
        business_id=str(business.id),
        name=business.name,
        timezone=business.timezone,
    )

    return BusinessResponse.model_validate(business)


@router.patch(
    "",
    response_model=BusinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update business profile",
    description="Updates specified fields of the business profile. Requires ADMIN or OWNER role.",
)
async def update_business_profile(
    body: BusinessUpdateRequest,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> BusinessResponse:
    """Partially update fields of the business profile."""
    result = await session.execute(
        select(Business).where(
            Business.tenant_id == current_user.tenant_id,
            Business.is_deleted == False,  # noqa: E712
        )
    )
    business = result.scalar_one_or_none()

    if business is None:
        raise NotFoundError(
            "Business profile not found. Please create one first.",
            code="BUSINESS_NOT_FOUND",
        )

    data = body.model_dump(exclude_unset=True)
    for field_name, value in data.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(business, field_name, value)

    session.add(business)
    await session.flush()

    logger.info(
        "Business profile updated partially",
        tenant_id=str(current_user.tenant_id),
        business_id=str(business.id),
        updated_fields=list(data.keys()),
    )

    return BusinessResponse.model_validate(business)


# =============================================================================
# WORKING HOURS ENDPOINTS
# =============================================================================

@router.get(
    "/working-hours",
    response_model=list[WorkingHoursResponse],
    status_code=status.HTTP_200_OK,
    summary="Get working hours schedule",
    description="Returns the weekly operating hours schedule for this organization.",
)
async def get_working_hours(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> list[WorkingHoursResponse]:
    """Retrieve all working hours records for the current tenant."""
    result = await session.execute(
        select(WorkingHours)
        .where(WorkingHours.tenant_id == current_user.tenant_id)
        .order_by(WorkingHours.day_of_week)
    )
    rows = result.scalars().all()
    return [WorkingHoursResponse.model_validate(r) for r in rows]


@router.put(
    "/working-hours",
    response_model=list[WorkingHoursResponse],
    status_code=status.HTTP_200_OK,
    summary="Batch update working hours schedule",
    description="Sets or updates the operating hours for specified days. Requires ADMIN or OWNER role.",
)
async def update_working_hours_batch(
    body: WorkingHoursUpdateBatchRequest,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> list[WorkingHoursResponse]:
    """Batch upserts operating hours for given days."""
    # Ensure business profile exists first
    b_result = await session.execute(
        select(Business).where(
            Business.tenant_id == current_user.tenant_id,
            Business.is_deleted == False,  # noqa: E712
        )
    )
    business = b_result.scalar_one_or_none()
    if business is None:
        raise NotFoundError(
            "Please create a business profile before configuring working hours.",
            code="BUSINESS_NOT_FOUND",
        )

    for item in body.schedule:
        # Check if record for this day already exists
        wh_result = await session.execute(
            select(WorkingHours).where(
                WorkingHours.business_id == business.id,
                WorkingHours.day_of_week == item.day_of_week,
            )
        )
        wh = wh_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if wh is not None:
            wh.open_time = item.open_time
            wh.close_time = item.close_time
            wh.is_closed = item.is_closed
            wh.updated_at = now
        else:
            wh = WorkingHours(
                id=uuid.uuid4(),
                tenant_id=current_user.tenant_id,
                business_id=business.id,
                day_of_week=item.day_of_week,
                open_time=item.open_time,
                close_time=item.close_time,
                is_closed=item.is_closed,
                created_at=now,
                updated_at=now,
            )
            session.add(wh)

    await session.flush()

    # Return refreshed list
    all_wh_result = await session.execute(
        select(WorkingHours)
        .where(WorkingHours.business_id == business.id)
        .order_by(WorkingHours.day_of_week)
    )
    records = all_wh_result.scalars().all()

    logger.info(
        "Working hours batch updated",
        tenant_id=str(current_user.tenant_id),
        business_id=str(business.id),
        days_updated=[i.day_of_week.value for i in body.schedule],
    )

    return [WorkingHoursResponse.model_validate(r) for r in records]
