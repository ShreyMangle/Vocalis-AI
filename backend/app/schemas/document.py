"""
app/schemas/document.py — Pydantic Schemas for Knowledge Base Documents & Search
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Details of a knowledge base document."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    business_id: uuid.UUID
    title: str
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    error_message: str | None = None
    chunk_count: int
    doc_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """List response for business documents."""

    items: list[DocumentResponse]
    total: int


class DocumentChunkResponse(BaseModel):
    """Text chunk response with index and metadata."""

    id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    chunk_metadata: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class FAQItem(BaseModel):
    """Individual question and answer pair."""

    question: str = Field(..., min_length=3, max_length=1000, description="The customer question")
    answer: str = Field(..., min_length=2, max_length=4000, description="The authoritative answer")
    category: str | None = Field(default=None, max_length=100, description="Optional topic category")


class FAQCreateRequest(BaseModel):
    """Payload to create an FAQ document."""

    title: str = Field(..., min_length=2, max_length=255, description="FAQ document title")
    items: list[FAQItem] = Field(..., min_length=1, description="List of Q&A items")
    metadata: dict[str, Any] | None = None


class KnowledgeQueryRequest(BaseModel):
    """Semantic vector search query payload."""

    query: str = Field(..., min_length=2, max_length=1000, description="Natural language search query")
    top_k: int = Field(default=3, ge=1, le=10, description="Maximum number of relevant chunks to retrieve")
    threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum similarity score")


class KnowledgeSearchResult(BaseModel):
    """Matched semantic chunk result."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    content: str
    similarity_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeQueryResponse(BaseModel):
    """Search query response."""

    query: str
    results: list[KnowledgeSearchResult]
    total_found: int
