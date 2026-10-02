"""
app/api/v1/tenants.py — Tenant Organization & Team Member Management

Routes:
  GET    /api/v1/tenants/current                     → View organization profile
  PATCH  /api/v1/tenants/current                     → Update organization name (ADMIN+)
  GET    /api/v1/tenants/current/members             → List team members
  POST   /api/v1/tenants/current/members             → Add / invite team member (ADMIN+)
  PATCH  /api/v1/tenants/current/members/{user_id}   → Update member role (OWNER only)
  DELETE /api/v1/tenants/current/members/{user_id}   → Remove member (ADMIN+, OWNER guard)
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    CurrentUser,
    require_authenticated,
    require_role,
)
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from app.core.security import hash_password
from app.db.session import get_session
from app.models.tenant import Tenant
from app.models.tenant_user import TenantUser, UserRole
from app.models.user import User
from app.schemas.tenant import (
    AddMemberRequest,
    TenantDetailResponse,
    TenantMemberResponse,
    TenantUpdateRequest,
    UpdateMemberRoleRequest,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/tenants", tags=["Tenant Management"])


# =============================================================================
# TENANT ORGANIZATION
# =============================================================================

@router.get(
    "/current",
    response_model=TenantDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current tenant details",
)
async def get_current_tenant(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> TenantDetailResponse:
    """Returns the authenticated user's tenant organization details."""
    tenant = await session.get(Tenant, current_user.tenant_id)
    if tenant is None or not tenant.is_active:
        raise NotFoundError("Organization not found or inactive.", code="TENANT_NOT_FOUND")

    return TenantDetailResponse.model_validate(tenant)


@router.patch(
    "/current",
    response_model=TenantDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current tenant organization",
    description="Updates organization details. Requires ADMIN or OWNER role.",
)
async def update_current_tenant(
    body: TenantUpdateRequest,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> TenantDetailResponse:
    """Updates the organization name."""
    tenant = await session.get(Tenant, current_user.tenant_id)
    if tenant is None or not tenant.is_active:
        raise NotFoundError("Organization not found or inactive.", code="TENANT_NOT_FOUND")

    tenant.name = body.name.strip()
    session.add(tenant)
    await session.flush()

    logger.info(
        "Tenant organization updated",
        tenant_id=str(tenant.id),
        updated_by=str(current_user.user_id),
        name=tenant.name,
    )

    return TenantDetailResponse.model_validate(tenant)


# =============================================================================
# TEAM MEMBERS
# =============================================================================

@router.get(
    "/current/members",
    response_model=list[TenantMemberResponse],
    status_code=status.HTTP_200_OK,
    summary="List team members",
    description="Returns all active team members in the organization.",
)
async def list_members(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> list[TenantMemberResponse]:
    """List all team members with user details and roles."""
    result = await session.execute(
        select(TenantUser, User)
        .join(User, TenantUser.user_id == User.id)
        .where(
            TenantUser.tenant_id == current_user.tenant_id,
            TenantUser.is_active == True,  # noqa: E712
            User.is_deleted == False,  # noqa: E712
        )
        .order_by(TenantUser.created_at.asc())
    )
    rows = result.all()

    return [
        TenantMemberResponse(
            id=membership.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=membership.role,
            is_active=membership.is_active,
            created_at=membership.created_at,
        )
        for membership, user in rows
    ]


@router.post(
    "/current/members",
    response_model=TenantMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add or invite team member",
    description="Adds a team member to the organization. Requires ADMIN or OWNER role.",
)
async def add_member(
    body: AddMemberRequest,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> TenantMemberResponse:
    """Adds a new or existing user to the tenant with a specified role."""
    email_clean = body.email.lower().strip()

    # Find if user already exists globally
    user_result = await session.execute(
        select(User).where(User.email == email_clean)
    )
    user = user_result.scalar_one_or_none()

    if user is None:
        # Create a new user with a secure random password hash
        user = User(
            email=email_clean,
            password_hash=hash_password(uuid.uuid4().hex),
            full_name=body.full_name.strip(),
            is_verified=False,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        logger.info("New user account created for invited member", user_id=str(user.id), email=email_clean)

    # Check if user is already a member of this tenant
    member_result = await session.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == current_user.tenant_id,
            TenantUser.user_id == user.id,
        )
    )
    existing_membership = member_result.scalar_one_or_none()

    if existing_membership is not None:
        if existing_membership.is_active:
            raise ConflictError(
                f"User '{email_clean}' is already a member of this organization.",
                code="MEMBER_ALREADY_EXISTS",
            )
        # Reactivate existing membership with the requested role
        existing_membership.is_active = True
        existing_membership.role = body.role
        session.add(existing_membership)
        membership = existing_membership
    else:
        membership = TenantUser(
            tenant_id=current_user.tenant_id,
            user_id=user.id,
            role=body.role,
            is_active=True,
        )
        session.add(membership)

    await session.flush()

    logger.info(
        "Team member added",
        tenant_id=str(current_user.tenant_id),
        user_id=str(user.id),
        role=body.role.value,
        added_by=str(current_user.user_id),
    )

    return TenantMemberResponse(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        is_active=membership.is_active,
        created_at=membership.created_at,
    )


@router.patch(
    "/current/members/{member_user_id}",
    response_model=TenantMemberResponse,
    status_code=status.HTTP_200_OK,
    summary="Update member role",
    description="Updates a team member's role. Requires OWNER role.",
)
async def update_member_role(
    member_user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.OWNER)),
    session: AsyncSession = Depends(get_session),
) -> TenantMemberResponse:
    """Updates a member's role, ensuring at least one OWNER remains."""
    result = await session.execute(
        select(TenantUser, User)
        .join(User, TenantUser.user_id == User.id)
        .where(
            TenantUser.tenant_id == current_user.tenant_id,
            TenantUser.user_id == member_user_id,
            TenantUser.is_active == True,  # noqa: E712
        )
    )
    row = result.first()
    if row is None:
        raise NotFoundError("Team member not found.", code="MEMBER_NOT_FOUND")

    membership, user = row

    # Guard: Cannot demote the last OWNER
    if membership.role == UserRole.OWNER and body.role != UserRole.OWNER:
        owner_count_result = await session.execute(
            select(func.count())
            .select_from(TenantUser)
            .where(
                TenantUser.tenant_id == current_user.tenant_id,
                TenantUser.role == UserRole.OWNER,
                TenantUser.is_active == True,  # noqa: E712
            )
        )
        owner_count = owner_count_result.scalar_one()
        if owner_count <= 1:
            raise ConflictError(
                "Cannot demote the only OWNER of the organization. Promote another member to OWNER first.",
                code="CANNOT_DEMOTE_LAST_OWNER",
            )

    membership.role = body.role
    session.add(membership)
    await session.flush()

    logger.info(
        "Member role updated",
        tenant_id=str(current_user.tenant_id),
        target_user_id=str(member_user_id),
        new_role=body.role.value,
        updated_by=str(current_user.user_id),
    )

    return TenantMemberResponse(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        is_active=membership.is_active,
        created_at=membership.created_at,
    )


@router.delete(
    "/current/members/{member_user_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove team member",
    description="Removes a member from the organization. Requires ADMIN or OWNER role.",
)
async def remove_member(
    member_user_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Removes a team member from the organization."""
    result = await session.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == current_user.tenant_id,
            TenantUser.user_id == member_user_id,
            TenantUser.is_active == True,  # noqa: E712
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Team member not found.", code="MEMBER_NOT_FOUND")

    # Guard: Non-owners cannot remove an OWNER
    if membership.role == UserRole.OWNER and current_user.role != UserRole.OWNER:
        raise AuthorizationError(
            "Admins cannot remove an OWNER from the organization.",
            code="CANNOT_REMOVE_OWNER",
        )

    # Guard: Cannot remove the last OWNER
    if membership.role == UserRole.OWNER:
        owner_count_result = await session.execute(
            select(func.count())
            .select_from(TenantUser)
            .where(
                TenantUser.tenant_id == current_user.tenant_id,
                TenantUser.role == UserRole.OWNER,
                TenantUser.is_active == True,  # noqa: E712
            )
        )
        owner_count = owner_count_result.scalar_one()
        if owner_count <= 1:
            raise ConflictError(
                "Cannot remove the only OWNER of the organization.",
                code="CANNOT_REMOVE_LAST_OWNER",
            )

    membership.is_active = False
    session.add(membership)
    await session.flush()

    logger.info(
        "Team member removed",
        tenant_id=str(current_user.tenant_id),
        target_user_id=str(member_user_id),
        removed_by=str(current_user.user_id),
    )

    return {"message": "Team member removed successfully."}
