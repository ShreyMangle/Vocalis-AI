"""
app/models/document.py — Knowledge Base Document & Chunk Models (pgvector)

CONCEPT: RAG Knowledge Base in VoxAI
====================================
Every business has unique domain knowledge:
  - Clinic: doctor schedules, treatment prices, insurance accepted, pre-op instructions
  - Salon: service menu, cancellation policy, stylist specialties
  - Hotel: check-in/out times, amenities, pet policies, directions

When a caller asks: "Do you take Blue Cross insurance?" or "Can I bring my dog?":
  1. The audio is transcribed to text (STT).
  2. The AI identifies a question needing business knowledge.
  3. `search_knowledge_base` retrieves the most semantically relevant text chunks from PostgreSQL via pgvector.
  4. The LLM answers the caller naturally using verified facts, preventing hallucination.
"""

import enum
import uuid
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class DocumentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class DocumentType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    FAQ = "faq"
    TEXT = "text"


class Document(Base, TimestampMixin, SoftDeleteMixin):
    """
    Represents an uploaded knowledge document or FAQ set for a business.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant isolation",
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Business owning this document",
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable title (e.g. 'Clinic Pricing & Insurance FAQ')",
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original filename or FAQ source tag",
    )

    file_type: Mapped[str] = mapped_column(
        String(50),
        default=DocumentType.TXT.value,
        nullable=False,
        comment="File extension/type: pdf, docx, txt, faq, text",
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default=DocumentStatus.READY.value,
        nullable=False,
        index=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    doc_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Arbitrary metadata such as category, tags, or author",
    )

    # Relationships
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )

    __table_args__ = (
        Index("ix_documents_tenant_business", "tenant_id", "business_id"),
    )


class DocumentChunk(Base, TimestampMixin):
    """
    Individual text chunk with 1536-dimensional pgvector embedding.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential index of the chunk within the document",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The text content snippet",
    )

    token_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # 1536 dimensions matches OpenAI text-embedding-3-small and text-embedding-ada-002
    embedding = mapped_column(
        Vector(1536),
        nullable=False,
        comment="pgvector 1536-dim vector for cosine similarity retrieval",
    )

    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Optional chunk metadata like page number or heading",
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )

    __table_args__ = (
        Index("ix_chunks_tenant_business", "tenant_id", "business_id"),
        Index("ix_chunks_document_index", "document_id", "chunk_index"),
    )
