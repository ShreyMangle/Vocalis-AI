"""
app/models/base.py — SQLAlchemy Base Class & Reusable Mixins

CONCEPT: SQLAlchemy 2.x Declarative Mapping
=============================================
Every database table is represented as a Python class.
SQLAlchemy converts between Python objects and database rows automatically.

EXAMPLE:
  Python class:              Database table:
  ───────────────            ─────────────────────────────
  class User(Base):          CREATE TABLE users (
      __tablename__ = "users"    id UUID PRIMARY KEY,
      id: Mapped[UUID]           email VARCHAR UNIQUE,
      email: Mapped[str]         created_at TIMESTAMPTZ
      created_at: Mapped[datetime]   );
  )

  Python object:             Database row:
  user.email = "a@b.com"  → INSERT INTO users (email) VALUES ('a@b.com')
  user.email              ← SELECT email FROM users WHERE id = ?

CONCEPT: Mapped[] and mapped_column()
=======================================
`Mapped[type]` tells SQLAlchemy (and Python's type checker) what type a column is.
`mapped_column()` defines how the column behaves in the database.

Example:
  email: Mapped[str] = mapped_column(
      String(255),      # VARCHAR(255) in SQL
      unique=True,      # UNIQUE constraint
      index=True,       # Creates an index for fast lookups
      nullable=False,   # NOT NULL constraint
  )

CONCEPT: UUID Primary Keys
============================
Traditional databases use AUTO INCREMENT integers (1, 2, 3, ...) as primary keys.
We use UUIDs instead. Why?

UUID example: "550e8400-e29b-41d4-a716-446655440000"

Benefits of UUIDs:
1. Globally unique — no collision across tenants, even across databases.
2. Non-sequential — attackers can't guess IDs or enumerate records.
   (If IDs are 1, 2, 3 → attacker knows user #1 exists, tries /api/users/1)
3. Can be generated before inserting — useful for event-driven systems.

Downside: larger storage (16 bytes vs 4 bytes for int), slightly slower index.
For our scale: irrelevant. The security benefit is worth it.

CONCEPT: Mixins
================
A "mixin" is a class that adds specific fields to other classes via inheritance.
Instead of writing `created_at`, `updated_at` in every single model,
we write it once in `TimestampMixin` and inherit.

  class User(Base, TimestampMixin):     ← gets created_at, updated_at automatically
  class Tenant(Base, TimestampMixin):   ← same fields, no repetition
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base.

    Every table model inherits from this.
    DeclarativeBase (SQLAlchemy 2.x) replaces the old `declarative_base()` function.

    When Alembic runs `alembic revision --autogenerate`, it looks at all classes
    that inherit from Base and generates SQL to create/alter their tables.
    """

    # type_annotation_map can map Python types → SQL types globally
    # We'll extend this as needed
    type_annotation_map = {
        uuid.UUID: UUID(as_uuid=True),  # Python uuid.UUID ↔ PostgreSQL UUID
    }


class TimestampMixin:
    """
    Adds `created_at` and `updated_at` columns to any model.

    created_at: set once when the row is INSERTed. Never changes.
    updated_at: set on INSERT, then automatically updated on every UPDATE.

    server_default=func.now():
      → The DATABASE generates this value, not Python.
      → Ensures consistency even if someone bypasses our app and writes directly to DB.

    onupdate=func.now():
      → SQLAlchemy automatically updates this column on every UPDATE statement.
      → No need to manually set it in code.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # DB generates: NOW()
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),        # Automatically updated by SQLAlchemy on UPDATE
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Adds soft delete support — records are "deleted" by setting is_deleted=True,
    not actually removed from the database.

    WHY soft delete?
    - Accidental deletion recovery: the data is still there.
    - Audit trail: you can see deleted records.
    - Referential integrity: other tables pointing to this record don't break.
    - Compliance: "delete" in GDPR means make it inaccessible, not necessarily gone.

    HOW TO USE:
      # "Delete" a record (mark it, don't remove it)
      tenant.is_deleted = True
      tenant.deleted_at = datetime.now(UTC)
      await session.commit()

      # Query active records only (ALWAYS include this filter)
      select(Tenant).where(Tenant.is_deleted == False)

    IMPORTANT: Every query on soft-deletable models MUST filter by is_deleted=False.
    We'll enforce this in repositories to prevent accidents.
    """

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,         # Index because we filter by this on EVERY query
        server_default="false",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,      # NULL means not deleted
        default=None,
    )
