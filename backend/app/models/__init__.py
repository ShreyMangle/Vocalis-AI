"""
app/models/__init__.py — marks models/ as a Python package

IMPORTANT: Import ALL models here.
Why? Alembic's `env.py` imports this file to discover all table definitions
when generating migrations. If a model isn't imported here, Alembic
won't know about it and won't create its table.

As we add models in future weeks, we add them here.
"""

# Import Base so Alembic can find it via: from app.models import Base
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

__all__ = ["Base", "TimestampMixin", "SoftDeleteMixin"]

# Week 2+: import models here as we create them
# from app.models.tenant import Tenant
# from app.models.user import User
# from app.models.business import Business
# ... etc
