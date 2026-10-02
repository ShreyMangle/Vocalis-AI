"""
app/models/__init__.py — Model Registry

CRITICAL: ALL models must be imported here.
Alembic's env.py imports this module. If a model is missing here,
Alembic won't know the table exists → it won't generate migrations for it.

Rule: Every time you create a new model file, add its import here.
"""

from app.models.base import Base, SoftDeleteMixin, TimestampMixin

# Week 2 — Auth & Multi-tenancy
from app.models.tenant import Tenant
from app.models.tenant_user import TenantUser, UserRole
from app.models.user import User

# Week 3 — Business Profile & Working Hours
from app.models.business import Business, DayOfWeek, WorkingHours

__all__ = [
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    # Week 2
    "Tenant",
    "User",
    "TenantUser",
    "UserRole",
    # Week 3
    "Business",
    "DayOfWeek",
    "WorkingHours",
]
