"""
tests/test_tenants.py — Unit Tests for Tenant Management & RBAC

Testing strategy:
  - Auth token parsing and RBAC permissions enforcement
  - OWNER vs ADMIN vs STAFF permissions
  - Guard logic: protecting the last OWNER, preventing privilege escalation
  - Mocked DB sessions for fast, deterministic unit test execution
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.models.tenant import Tenant
from app.models.tenant_user import TenantUser, UserRole
from app.models.user import User


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def test_ids():
    return {
        "tenant_id": uuid.uuid4(),
        "owner_id": uuid.uuid4(),
        "admin_id": uuid.uuid4(),
        "staff_id": uuid.uuid4(),
        "other_user_id": uuid.uuid4(),
    }


@pytest.fixture
def tokens(test_ids):
    tid = test_ids["tenant_id"]
    return {
        "owner": create_access_token(test_ids["owner_id"], tid, "OWNER"),
        "admin": create_access_token(test_ids["admin_id"], tid, "ADMIN"),
        "staff": create_access_token(test_ids["staff_id"], tid, "STAFF"),
    }


@pytest.fixture
def mock_tenant(test_ids):
    t = MagicMock(spec=Tenant)
    t.id = test_ids["tenant_id"]
    t.name = "Acme Clinic"
    t.slug = "acme-clinic"
    t.plan = "starter"
    t.is_active = True
    t.created_at = datetime.now(timezone.utc)
    t.updated_at = datetime.now(timezone.utc)
    return t


# =============================================================================
# TEST: Tenant Details
# =============================================================================

class TestTenantDetails:
    def test_get_current_tenant_unauthorized(self, client):
        """Without Bearer token, returns 401."""
        response = client.get("/api/v1/tenants/current")
        assert response.status_code == 401

    def test_get_current_tenant_success(self, client, tokens, mock_tenant):
        """Any authenticated tenant member can view tenant details."""
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_tenant

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.get(
                "/api/v1/tenants/current",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Acme Clinic"
            assert data["slug"] == "acme-clinic"
        finally:
            app.dependency_overrides.pop(get_session, None)


# =============================================================================
# TEST: Tenant Update (RBAC)
# =============================================================================

class TestTenantUpdate:
    def test_update_tenant_forbidden_for_staff(self, client, tokens):
        """STAFF role receives 403 Forbidden when attempting to update organization."""
        response = client.patch(
            "/api/v1/tenants/current",
            json={"name": "New Name"},
            headers={"Authorization": f"Bearer {tokens['staff']}"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "INSUFFICIENT_ROLE"

    def test_update_tenant_allowed_for_admin(self, client, tokens, mock_tenant):
        """ADMIN role can update organization name."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.get.return_value = mock_tenant

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.patch(
                "/api/v1/tenants/current",
                json={"name": "Acme Health Group"},
                headers={"Authorization": f"Bearer {tokens['admin']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Acme Health Group"
            assert mock_tenant.name == "Acme Health Group"
        finally:
            app.dependency_overrides.pop(get_session, None)


# =============================================================================
# TEST: Team Members Management
# =============================================================================

class TestTeamMembers:
    def test_list_members_requires_auth(self, client):
        response = client.get("/api/v1/tenants/current/members")
        assert response.status_code == 401

    def test_list_members_success(self, client, tokens, test_ids):
        mock_user = MagicMock(spec=User)
        mock_user.id = test_ids["owner_id"]
        mock_user.email = "owner@acme.com"
        mock_user.full_name = "Dr. Owner"
        mock_user.is_deleted = False

        mock_membership = MagicMock(spec=TenantUser)
        mock_membership.id = uuid.uuid4()
        mock_membership.user_id = mock_user.id
        mock_membership.role = UserRole.OWNER
        mock_membership.is_active = True
        mock_membership.created_at = datetime.now(timezone.utc)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_membership, mock_user)]
        mock_session.execute.return_value = mock_result

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.get(
                "/api/v1/tenants/current/members",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["email"] == "owner@acme.com"
            assert data[0]["role"] == "OWNER"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_add_member_forbidden_for_staff(self, client, tokens):
        """STAFF cannot add members."""
        response = client.post(
            "/api/v1/tenants/current/members",
            json={"email": "newbie@acme.com", "role": "STAFF"},
            headers={"Authorization": f"Bearer {tokens['staff']}"},
        )
        assert response.status_code == 403

    def test_add_member_conflict_if_already_active(self, client, tokens):
        """Adding an already active member raises 409 Conflict."""
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = "existing@acme.com"

        mock_existing_membership = MagicMock(spec=TenantUser)
        mock_existing_membership.is_active = True

        mock_session = AsyncMock()
        # 1st execute: User lookup -> returns mock_user
        # 2nd execute: TenantUser lookup -> returns mock_existing_membership
        res1 = MagicMock()
        res1.scalar_one_or_none.return_value = mock_user
        res2 = MagicMock()
        res2.scalar_one_or_none.return_value = mock_existing_membership
        mock_session.execute.side_effect = [res1, res2]

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.post(
                "/api/v1/tenants/current/members",
                json={"email": "existing@acme.com", "role": "STAFF"},
                headers={"Authorization": f"Bearer {tokens['admin']}"},
            )
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "MEMBER_ALREADY_EXISTS"
        finally:
            app.dependency_overrides.pop(get_session, None)


# =============================================================================
# TEST: Member Role Updates & Guards
# =============================================================================

class TestMemberRoleUpdates:
    def test_update_role_forbidden_for_admin(self, client, tokens, test_ids):
        """Only OWNER can change roles; ADMIN receives 403."""
        target_id = test_ids["staff_id"]
        response = client.patch(
            f"/api/v1/tenants/current/members/{target_id}",
            json={"role": "ADMIN"},
            headers={"Authorization": f"Bearer {tokens['admin']}"},
        )
        assert response.status_code == 403

    def test_cannot_demote_only_owner(self, client, tokens, test_ids):
        """Attempting to demote the sole OWNER raises 409 Conflict."""
        mock_user = MagicMock(spec=User)
        mock_user.id = test_ids["owner_id"]
        mock_user.email = "owner@acme.com"
        mock_user.full_name = "Sole Owner"

        mock_membership = MagicMock(spec=TenantUser)
        mock_membership.id = uuid.uuid4()
        mock_membership.role = UserRole.OWNER
        mock_membership.is_active = True
        mock_membership.created_at = datetime.now(timezone.utc)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        # 1st execute: find membership & user
        res1 = MagicMock()
        res1.first.return_value = (mock_membership, mock_user)
        # 2nd execute: count owners -> 1
        res2 = MagicMock()
        res2.scalar_one.return_value = 1
        mock_session.execute.side_effect = [res1, res2]

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.patch(
                f"/api/v1/tenants/current/members/{test_ids['owner_id']}",
                json={"role": "ADMIN"},
                headers={"Authorization": f"Bearer {tokens['owner']}"},
            )
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "CANNOT_DEMOTE_LAST_OWNER"
        finally:
            app.dependency_overrides.pop(get_session, None)


# =============================================================================
# TEST: Member Removal & Guards
# =============================================================================

class TestMemberRemoval:
    def test_admin_cannot_remove_owner(self, client, tokens, test_ids):
        """ADMIN cannot remove an OWNER from the organization."""
        mock_membership = MagicMock(spec=TenantUser)
        mock_membership.role = UserRole.OWNER
        mock_membership.is_active = True

        mock_session = AsyncMock()
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_membership
        mock_session.execute.return_value = res

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.delete(
                f"/api/v1/tenants/current/members/{test_ids['owner_id']}",
                headers={"Authorization": f"Bearer {tokens['admin']}"},
            )
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "CANNOT_REMOVE_OWNER"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_remove_staff_member_success(self, client, tokens, test_ids):
        """ADMIN can remove a STAFF member successfully."""
        mock_membership = MagicMock(spec=TenantUser)
        mock_membership.role = UserRole.STAFF
        mock_membership.is_active = True

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_membership
        mock_session.execute.return_value = res

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.delete(
                f"/api/v1/tenants/current/members/{test_ids['staff_id']}",
                headers={"Authorization": f"Bearer {tokens['admin']}"},
            )
            assert response.status_code == 200
            assert mock_membership.is_active is False
        finally:
            app.dependency_overrides.pop(get_session, None)
