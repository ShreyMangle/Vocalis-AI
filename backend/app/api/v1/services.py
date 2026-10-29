"""
app/api/v1/services.py — Business Services Catalog Endpoints

Routes:
  GET    /api/v1/business/services               → List services for the business
  POST   /api/v1/business/services               → Create a new service (ADMIN+)
  GET    /api/v1/business/services/{service_id}  → Get service details
  PATCH  /api/v1/business/services/{service_id}  → Update a service (ADMIN+)
  DELETE /api/v1/business/services/{service_id}  → Soft-delete a service (ADMIN+)
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    CurrentUser,
    require_authenticated,
    require_role,
)
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.business import Business
from app.models.service import Service
from app.models.tenant_user import UserRole
from app.schemas.service import (
    ServiceCreateRequest,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdateRequest,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/business/services", tags=["Business Services"])


async def _get_tenant_business(session: AsyncSession, tenant_id: uuid.UUID) -> Business:
    """Helper to verify that tenant has an existing business profile."""
    result = await session.execute(
        select(Business).where(
            Business.tenant_id == tenant_id,
            Business.is_deleted == False,  # noqa: E712
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise NotFoundError(
            "Business profile not configured. Create a business profile first before adding services.",
            code="BUSINESS_NOT_FOUND",
        )
    return business


@router.get(
    "",
    response_model=ServiceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List business services",
    description="Returns all active or configured services offered by the business.",
)
async def list_services(
    active_only: bool = Query(default=True, description="Filter for active services only"),
    category: str | None = Query(default=None, description="Optional category filter"),
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> ServiceListResponse:
    """List services for the authenticated tenant's business."""
    business = await _get_tenant_business(session, current_user.tenant_id)

    query = select(Service).where(
        Service.tenant_id == current_user.tenant_id,
        Service.business_id == business.id,
        Service.is_deleted == False,  # noqa: E712
    )

    if active_only:
        query = query.where(Service.is_active == True)  # noqa: E712

    if category:
        query = query.where(Service.category == category)

    query = query.order_by(Service.name.asc())
    result = await session.execute(query)
    services = result.scalars().all()

    return ServiceListResponse(
        items=[ServiceResponse.model_validate(s) for s in services],
        total=len(services),
    )


@router.post(
    "",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service",
    description="Creates a new service in the business catalog. Requires ADMIN or OWNER role.",
)
async def create_service(
    payload: ServiceCreateRequest,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> ServiceResponse:
    """Create a new service for the business."""
    business = await _get_tenant_business(session, current_user.tenant_id)

    service = Service(
        tenant_id=current_user.tenant_id,
        business_id=business.id,
        name=payload.name,
        description=payload.description,
        duration_minutes=payload.duration_minutes,
        price=payload.price,
        currency=payload.currency,
        category=payload.category,
        is_active=payload.is_active,
    )

    session.add(service)
    await session.commit()
    await session.refresh(service)

    logger.info(
        "Service created",
        service_id=str(service.id),
        service_name=service.name,
        tenant_id=str(current_user.tenant_id),
    )

    return ServiceResponse.model_validate(service)


@router.get(
    "/{service_id}",
    response_model=ServiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get service by ID",
)
async def get_service(
    service_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> ServiceResponse:
    """Fetch details of a single service."""
    result = await session.execute(
        select(Service).where(
            Service.id == service_id,
            Service.tenant_id == current_user.tenant_id,
            Service.is_deleted == False,  # noqa: E712
        )
    )
    service = result.scalar_one_or_none()

    if service is None:
        raise NotFoundError("Service not found.", code="SERVICE_NOT_FOUND")

    return ServiceResponse.model_validate(service)


@router.patch(
    "/{service_id}",
    response_model=ServiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a service",
    description="Partially updates an existing service. Requires ADMIN or OWNER role.",
)
async def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdateRequest,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> ServiceResponse:
    """Update fields on an existing service."""
    result = await session.execute(
        select(Service).where(
            Service.id == service_id,
            Service.tenant_id == current_user.tenant_id,
            Service.is_deleted == False,  # noqa: E712
        )
    )
    service = result.scalar_one_or_none()

    if service is None:
        raise NotFoundError("Service not found.", code="SERVICE_NOT_FOUND")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(service, field, value)

    await session.commit()
    await session.refresh(service)

    logger.info(
        "Service updated",
        service_id=str(service.id),
        updated_fields=list(update_data.keys()),
        tenant_id=str(current_user.tenant_id),
    )

    return ServiceResponse.model_validate(service)


@router.delete(
    "/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a service",
    description="Soft-deletes a service from the catalog. Requires ADMIN or OWNER role.",
)
async def delete_service(
    service_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Soft-delete a service."""
    result = await session.execute(
        select(Service).where(
            Service.id == service_id,
            Service.tenant_id == current_user.tenant_id,
            Service.is_deleted == False,  # noqa: E712
        )
    )
    service = result.scalar_one_or_none()

    if service is None:
        raise NotFoundError("Service not found.", code="SERVICE_NOT_FOUND")

    service.is_deleted = True
    service.deleted_at = datetime.now(timezone.utc)

    await session.commit()

    logger.info(
        "Service soft-deleted",
        service_id=str(service.id),
        tenant_id=str(current_user.tenant_id),
    )
