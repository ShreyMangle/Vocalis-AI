"""
app/api/v1/documents.py — Knowledge Base & Document Management Endpoints

Routes:
  GET    /api/v1/business/documents                 → List business knowledge documents
  POST   /api/v1/business/documents/upload          → Upload PDF/DOCX/TXT document (ADMIN+)
  POST   /api/v1/business/documents/faq             → Add structured FAQ set (ADMIN+)
  GET    /api/v1/business/documents/{document_id}   → Get document details & chunks
  DELETE /api/v1/business/documents/{document_id}   → Delete document (ADMIN+)
  POST   /api/v1/business/documents/search          → Semantic vector search
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.rag.service import KnowledgeBaseService
from app.core.dependencies import (
    CurrentUser,
    require_authenticated,
    require_role,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_session
from app.models.business import Business
from app.models.document import Document
from app.models.tenant_user import UserRole
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    FAQCreateRequest,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    KnowledgeSearchResult,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/business/documents", tags=["Knowledge Base"])
kb_service = KnowledgeBaseService()


async def _get_tenant_business(session: AsyncSession, tenant_id: uuid.UUID) -> Business:
    """Helper to verify that tenant has an active business profile."""
    result = await session.execute(
        select(Business).where(
            Business.tenant_id == tenant_id,
            Business.is_deleted == False,  # noqa: E712
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise NotFoundError(
            "Business profile not configured. Create a business profile first.",
            code="BUSINESS_NOT_FOUND",
        )
    return business


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List knowledge documents",
    description="Returns all uploaded documents and FAQ collections for the business.",
)
async def list_documents(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> DocumentListResponse:
    business = await _get_tenant_business(session, current_user.tenant_id)
    docs = await kb_service.list_documents(session, current_user.tenant_id, business.id)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload knowledge document",
    description="Upload a PDF, DOCX, or TXT file to be chunked and embedded with pgvector.",
)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload (PDF, DOCX, TXT)"),
    title: str | None = Form(default=None, description="Optional custom title for the document"),
    current_user: CurrentUser = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    business = await _get_tenant_business(session, current_user.tenant_id)

    filename = file.filename or "uploaded_document.txt"
    content = await file.read()
    if not content:
        raise ValidationError("Uploaded file is empty.", code="EMPTY_FILE")

    doc = await kb_service.ingest_file(
        session=session,
        tenant_id=current_user.tenant_id,
        business_id=business.id,
        filename=filename,
        content=content,
        title=title,
    )
    return DocumentResponse.model_validate(doc)


@router.post(
    "/faq",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create FAQ collection",
    description="Create an FAQ knowledge document directly from question/answer pairs.",
)
async def create_faq(
    payload: FAQCreateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    business = await _get_tenant_business(session, current_user.tenant_id)

    raw_faqs = [
        {"question": item.question, "answer": item.answer, "category": item.category}
        for item in payload.items
    ]
    doc = await kb_service.ingest_faqs(
        session=session,
        tenant_id=current_user.tenant_id,
        business_id=business.id,
        title=payload.title,
        faqs=raw_faqs,
        metadata=payload.metadata,
    )
    return DocumentResponse.model_validate(doc)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document details",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    business = await _get_tenant_business(session, current_user.tenant_id)
    doc = await kb_service.get_document(session, current_user.tenant_id, business.id, document_id)
    return DocumentResponse.model_validate(doc)


@router.get(
    "/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
    status_code=status.HTTP_200_OK,
    summary="Get document chunks",
)
async def get_document_chunks(
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentChunkResponse]:
    business = await _get_tenant_business(session, current_user.tenant_id)
    stmt = (
        select(Document)
        .where(
            Document.id == document_id,
            Document.tenant_id == current_user.tenant_id,
            Document.business_id == business.id,
            Document.is_deleted == False,  # noqa: E712
        )
        .options(selectinload(Document.chunks))
    )
    res = await session.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document not found.", code="DOCUMENT_NOT_FOUND")

    return [DocumentChunkResponse.model_validate(c) for c in doc.chunks]


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete knowledge document",
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> None:
    business = await _get_tenant_business(session, current_user.tenant_id)
    await kb_service.delete_document(session, current_user.tenant_id, business.id, document_id)


@router.post(
    "/search",
    response_model=KnowledgeQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic vector search",
    description="Test semantic similarity search against the business knowledge base.",
)
async def search_knowledge(
    payload: KnowledgeQueryRequest,
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeQueryResponse:
    business = await _get_tenant_business(session, current_user.tenant_id)
    results = await kb_service.query_knowledge_base(
        session=session,
        tenant_id=current_user.tenant_id,
        business_id=business.id,
        query=payload.query,
        top_k=payload.top_k,
        threshold=payload.threshold,
    )

    items = [
        KnowledgeSearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            document_title=r.document_title,
            content=r.content,
            similarity_score=r.similarity_score,
            metadata=r.metadata,
        )
        for r in results
    ]

    return KnowledgeQueryResponse(
        query=payload.query,
        results=items,
        total_found=len(items),
    )
