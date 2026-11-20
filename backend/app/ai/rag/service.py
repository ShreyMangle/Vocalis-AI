"""
app/ai/rag/service.py — Knowledge Base Ingestion & Management Service

Orchestrates file parsing, semantic chunking, batch vector embedding,
and database persistence for business knowledge bases.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.chunker import TokenChunker
from app.ai.rag.embeddings import EmbeddingService
from app.ai.rag.parsers import DocumentParser
from app.ai.rag.retriever import KnowledgeRetriever, SearchResult
from app.core.exceptions import NotFoundError, ValidationError
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentType

logger = structlog.get_logger(__name__)


class KnowledgeBaseService:
    """Service for ingesting and querying business knowledge documents."""

    def __init__(
        self,
        chunker: TokenChunker | None = None,
        embedding_service: EmbeddingService | None = None,
        retriever: KnowledgeRetriever | None = None,
    ):
        self.chunker = chunker or TokenChunker(chunk_size=400, chunk_overlap=50)
        self.embedding_service = embedding_service or EmbeddingService()
        self.retriever = retriever or KnowledgeRetriever(self.embedding_service)

    async def ingest_file(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        business_id: uuid.UUID,
        filename: str,
        content: bytes,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        """
        Parse, chunk, embed, and persist an uploaded file.
        """
        if not content:
            raise ValidationError("Uploaded file is empty.", code="EMPTY_FILE")

        ext = filename.lower().split(".")[-1] if "." in filename else "txt"
        file_type = (
            DocumentType.PDF.value
            if ext == "pdf"
            else DocumentType.DOCX.value
            if ext in ("docx", "doc")
            else DocumentType.TXT.value
        )
        doc_title = title.strip() if title and title.strip() else filename

        now = datetime.now(timezone.utc)
        document = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            title=doc_title,
            filename=filename,
            file_type=file_type,
            file_size_bytes=len(content),
            status=DocumentStatus.PROCESSING.value,
            doc_metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        session.add(document)
        await session.flush()  # Allocate document.id

        try:
            # 1. Parse text from bytes
            text = DocumentParser.extract_text(filename, content)
            if not text.strip():
                raise ValidationError("No readable text found in document.", code="NO_TEXT_FOUND")

            # 2. Split into semantic chunks
            base_meta = {"filename": filename, "title": doc_title}
            chunks = self.chunker.chunk_text(text, base_metadata=base_meta)
            if not chunks:
                raise ValidationError("Failed to produce text chunks.", code="CHUNKING_FAILED")

            # 3. Batch generate 1536-dim vector embeddings
            chunk_texts = [c.content for c in chunks]
            embeddings = await self.embedding_service.get_embeddings_batch(chunk_texts)

            # 4. Insert chunks into database
            chunk_entities: list[DocumentChunk] = []
            for chunk_data, emb in zip(chunks, embeddings, strict=False):
                chunk_record = DocumentChunk(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    document_id=document.id,
                    chunk_index=chunk_data.chunk_index,
                    content=chunk_data.content,
                    token_count=chunk_data.token_count,
                    embedding=emb,
                    chunk_metadata=chunk_data.metadata,
                )
                chunk_entities.append(chunk_record)

            session.add_all(chunk_entities)

            # 5. Mark document READY
            document.chunk_count = len(chunk_entities)
            document.status = DocumentStatus.READY.value
            document.error_message = None
            await session.commit()
            await session.refresh(document)

            logger.info(
                "document_ingestion_completed",
                document_id=str(document.id),
                chunks=len(chunk_entities),
            )
            return document

        except Exception as exc:
            logger.error("document_ingestion_failed", error=str(exc))
            document.status = DocumentStatus.FAILED.value
            document.error_message = str(exc)
            await session.commit()
            raise

    async def ingest_faqs(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        business_id: uuid.UUID,
        title: str,
        faqs: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        """
        Ingest FAQ question-and-answer pairs as a structured knowledge document.
        """
        if not faqs:
            raise ValidationError("FAQ list cannot be empty.", code="EMPTY_FAQ_LIST")

        now = datetime.now(timezone.utc)
        document = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            title=title,
            filename=f"faq_{uuid.uuid4().hex[:8]}.json",
            file_type=DocumentType.FAQ.value,
            file_size_bytes=len(str(faqs)),
            status=DocumentStatus.PROCESSING.value,
            doc_metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        session.add(document)
        await session.flush()

        try:
            # Build individual chunks per FAQ pair or group
            chunks_data = []
            for idx, faq in enumerate(faqs):
                q = faq.get("question", "").strip()
                a = faq.get("answer", "").strip()
                cat = faq.get("category", "")
                if not q or not a:
                    continue

                formatted_content = f"Question: {q}\nAnswer: {a}"
                if cat:
                    formatted_content = f"Category: {cat}\n{formatted_content}"

                token_cnt = self.chunker.count_tokens(formatted_content)
                chunks_data.append((idx, formatted_content, token_cnt, {"category": cat, "question": q}))

            if not chunks_data:
                raise ValidationError("No valid Q&A pairs provided.", code="INVALID_FAQS")

            embeddings = await self.embedding_service.get_embeddings_batch(
                [c[1] for c in chunks_data]
            )

            chunk_entities: list[DocumentChunk] = []
            for (idx, content, tok_cnt, meta), emb in zip(chunks_data, embeddings, strict=False):
                chunk_record = DocumentChunk(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    document_id=document.id,
                    chunk_index=idx,
                    content=content,
                    token_count=tok_cnt,
                    embedding=emb,
                    chunk_metadata=meta,
                )
                chunk_entities.append(chunk_record)

            session.add_all(chunk_entities)
            document.chunk_count = len(chunk_entities)
            document.status = DocumentStatus.READY.value
            await session.commit()
            await session.refresh(document)
            return document

        except Exception as exc:
            logger.error("faq_ingestion_failed", error=str(exc))
            document.status = DocumentStatus.FAILED.value
            document.error_message = str(exc)
            await session.commit()
            raise

    async def get_document(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        business_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Document:
        """Fetch document by ID verifying tenant and business isolation."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
            Document.business_id == business_id,
            Document.is_deleted == False,  # noqa: E712
        )
        res = await session.execute(stmt)
        doc = res.scalar_one_or_none()
        if not doc:
            raise NotFoundError(f"Document {document_id} not found.", code="DOCUMENT_NOT_FOUND")
        return doc

    async def list_documents(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> list[Document]:
        """List active documents for a business."""
        stmt = (
            select(Document)
            .where(
                Document.tenant_id == tenant_id,
                Document.business_id == business_id,
                Document.is_deleted == False,  # noqa: E712
            )
            .order_by(Document.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def delete_document(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        business_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> bool:
        """Soft delete a document and its chunks."""
        doc = await self.get_document(session, tenant_id, business_id, document_id)
        doc.is_deleted = True
        doc.deleted_at = datetime.now(timezone.utc)
        await session.commit()
        return True

    async def query_knowledge_base(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        business_id: uuid.UUID,
        query: str,
        top_k: int = 3,
        threshold: float = 0.3,
    ) -> list[SearchResult]:
        """Query knowledge base semantically."""
        return await self.retriever.search(
            session=session,
            business_id=business_id,
            tenant_id=tenant_id,
            query=query,
            top_k=top_k,
            similarity_threshold=threshold,
        )
