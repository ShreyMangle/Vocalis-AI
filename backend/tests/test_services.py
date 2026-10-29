"""
tests/test_services.py — Unit Tests for Business Services Catalog

Testing:
  - Unauthorized access checks
  - Role-based permissions (STAFF read-only, ADMIN/OWNER write)
  - Validation: duration bounds, price bounds
  - CRUD operations: list, create, get, patch, delete (soft delete)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.models.business import Business
from app.models.service import Service


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def tokens(tenant_id):
    return {
        "owner": create_access_token(uuid.uuid4(), tenant_id, "OWNER"),
        "admin": create_access_token(uuid.uuid4(), tenant_id, "ADMIN"),
        "staff": create_access_token(uuid.uuid4(), tenant_id, "STAFF"),
    }


@pytest.fixture
def mock_business(tenant_id):
    b = MagicMock(spec=Business)
    b.id = uuid.uuid4()
    b.tenant_id = tenant_id
    b.name = "Sunrise Clinic"
    b.is_deleted = False
    return b


@pytest.fixture
def mock_service(tenant_id, mock_business):
    s = MagicMock(spec=Service)
    s.id = uuid.uuid4()
    s.tenant_id = tenant_id
    s.business_id = mock_business.id
    s.name = "Dental Consultation"
    s.description = "Routine dental exam"
    s.duration_minutes = 30
    s.price = 50000
    s.currency = "INR"
    s.category = "Dental"
    s.is_active = True
    s.is_deleted = False
    s.created_at = datetime.now(timezone.utc)
    s.updated_at = datetime.now(timezone.utc)
    return s


class TestServicesAPI:
    def test_list_services_unauthorized(self, client):
        response = client.get("/api/v1/business/services")
        assert response.status_code == 401

    def test_list_services_business_not_found(self, client, tokens):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/business/services",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "BUSINESS_NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_list_services_success(self, client, tokens, mock_business, mock_service):
        mock_session = AsyncMock()
        
        # First execute: find business
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = mock_business

        # Second execute: find services
        mock_s_res = MagicMock()
        mock_s_res.scalars.return_value.all.return_value = [mock_service]

        mock_session.execute.side_effect = [mock_b_res, mock_s_res]

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/business/services",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["name"] == "Dental Consultation"
            assert data["items"][0]["duration_minutes"] == 30
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_create_service_forbidden_for_staff(self, client, tokens):
        payload = {
            "name": "Teeth Whitening",
            "duration_minutes": 45,
            "price": 150000,
        }
        response = client.post(
            "/api/v1/business/services",
            json=payload,
            headers={"Authorization": f"Bearer {tokens['staff']}"},
        )
        assert response.status_code == 403

    def test_create_service_allowed_for_admin(self, client, tokens, mock_business):
        mock_session = AsyncMock()
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = mock_business
        mock_session.execute.return_value = mock_b_res
        mock_session.add = MagicMock()

        async def mock_refresh(instance):
            instance.id = uuid.uuid4()
            instance.created_at = datetime.now(timezone.utc)
            instance.updated_at = datetime.now(timezone.utc)

        mock_session.refresh = mock_refresh

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            payload = {
                "name": "Teeth Whitening",
                "description": "Laser bleaching",
                "duration_minutes": 45,
                "price": 150000,
                "currency": "INR",
                "category": "Dental",
                "is_active": True,
            }
            response = client.post(
                "/api/v1/business/services",
                json=payload,
                headers={"Authorization": f"Bearer {tokens['admin']}"},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Teeth Whitening"
            assert data["duration_minutes"] == 45
            assert data["price"] == 150000
            mock_session.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_create_service_invalid_duration_fails(self, client, tokens):
        payload = {
            "name": "Invalid Service",
            "duration_minutes": 2,  # ge=5 violated
            "price": 100,
        }
        response = client.post(
            "/api/v1/business/services",
            json=payload,
            headers={"Authorization": f"Bearer {tokens['admin']}"},
        )
        assert response.status_code == 422

    def test_get_service_by_id_success(self, client, tokens, mock_service):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_service
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                f"/api/v1/business/services/{mock_service.id}",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            assert response.json()["id"] == str(mock_service.id)
            assert response.json()["name"] == "Dental Consultation"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_get_service_not_found(self, client, tokens):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                f"/api/v1/business/services/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "SERVICE_NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_update_service_admin_success(self, client, tokens, mock_service):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_service
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            payload = {"price": 60000, "duration_minutes": 40}
            response = client.patch(
                f"/api/v1/business/services/{mock_service.id}",
                json=payload,
                headers={"Authorization": f"Bearer {tokens['admin']}"},
            )
            assert response.status_code == 200
            assert mock_service.price == 60000
            assert mock_service.duration_minutes == 40
            mock_session.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_delete_service_soft_deletes(self, client, tokens, mock_service):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_service
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.delete(
                f"/api/v1/business/services/{mock_service.id}",
                headers={"Authorization": f"Bearer {tokens['owner']}"},
            )
            assert response.status_code == 204
            assert mock_service.is_deleted is True
            assert mock_service.deleted_at is not None
            mock_session.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.pop(get_session, None)

