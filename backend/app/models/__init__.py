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
from app.models.service import Service

# Week 4 — Voice Agent Configuration
from app.models.agent import AgentConfig

# Week 5 — Knowledge Base & RAG Documents (pgvector)
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentType

# Week 7 — Appointments & Scheduling
from app.models.appointment import Appointment, AppointmentStatus

# Week 10 — Call Analytics & Telemetry
from app.models.call import Call, CallDirection, CallSentiment, CallStatus

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
    "Service",
    # Week 4
    "AgentConfig",
    # Week 5
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "DocumentType",
    # Week 7
    "Appointment",
    "AppointmentStatus",
    # Week 10
    "Call",
    "CallDirection",
    "CallStatus",
    "CallSentiment",
]
