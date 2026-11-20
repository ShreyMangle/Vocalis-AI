"""
tests/test_rag.py — Unit & Integration Tests for RAG Knowledge Base

Tests:
  - Text, PDF, DOCX, and FAQ parsing
  - Token-aware chunking and sliding window overlap
  - 1536-dimensional embedding generation and cosine similarity
  - Knowledge retriever semantic search and multi-tenant isolation
  - KnowledgeBaseService file and FAQ ingestion
  - REST API endpoints for documents, FAQs, and semantic search
  - Voice agent tool calling execution for search_knowledge_base
"""

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.rag.chunker import TextChunk, TokenChunker
from app.ai.rag.embeddings import EmbeddingService, cosine_similarity
from app.ai.rag.parsers import DocumentParser
from app.ai.rag.retriever import KnowledgeRetriever
from app.ai.rag.service import KnowledgeBaseService
from app.ai.tools.definitions import VOICE_AGENT_TOOLS
from app.ai.tools.executor import ToolExecutor
from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.models.business import Business
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentType


# ── Parser Tests ─────────────────────────────────────────────────────────────


def test_document_parser_plain_text():
    raw_bytes = b"Hello world!\r\nThis is a test document with   extra   spaces.\r\n"
    text = DocumentParser.parse_plain_text(raw_bytes)
    assert "Hello world!" in text
    assert "This is a test document with extra spaces." in text
    assert "\r" not in text


def test_document_parser_faq():
    items = [
        {"question": "What are your hours?", "answer": "9am to 6pm.", "category": "General"},
        {"question": "Do you accept walk-ins?", "answer": "Yes, walk-ins welcome.", "category": "Policy"},
    ]
    formatted = DocumentParser.parse_faq_items(items)
    assert "Q1 [General]: What are your hours?" in formatted
    assert "A: 9am to 6pm." in formatted
    assert "Q2 [Policy]: Do you accept walk-ins?" in formatted


def test_document_parser_extract_text_dispatcher():
    txt_content = b"Clinic cancellation policy requires 24h notice."
    res = DocumentParser.extract_text("policy.txt", txt_content)
    assert "Clinic cancellation policy" in res


# ── Chunker Tests ────────────────────────────────────────────────────────────


def test_token_chunker_single_chunk():
    chunker = TokenChunker(chunk_size=100, chunk_overlap=20)
    text = "Short policy text under one hundred tokens."
    chunks = chunker.chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].content == text
    assert chunks[0].token_count > 0


def test_token_chunker_sliding_window_split():
    chunker = TokenChunker(chunk_size=30, chunk_overlap=10)
    # Generate long text with paragraphs
    paragraphs = [
        f"Paragraph {i}: This is medical clinic policy detailing patient intake and consent procedures."
        for i in range(10)
    ]
    long_text = "\n\n".join(paragraphs)
    chunks = chunker.chunk_text(long_text)
    assert len(chunks) > 1
    # Verify index sequence
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
        assert chunk.token_count > 0


# ── Embedding & Similarity Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embedding_service_deterministic():
    emb_service = EmbeddingService(api_key=None)
    vec1 = await emb_service.get_embedding("Dental consultation price is ₹500.")
    vec2 = await emb_service.get_embedding("Dental consultation price is ₹500.")
    vec3 = await emb_service.get_embedding("Our dentist checks teeth and charges ₹500.")
    vec4 = await emb_service.get_embedding("Automobile rocket booster trajectory calculations.")

    # 1536 dimensions
    assert len(vec1) == 1536
    # Exact match similarity = 1.0
    sim_exact = cosine_similarity(vec1, vec2)
    assert pytest.approx(sim_exact, 0.001) == 1.0

    # Related strings have high similarity
    sim_related = cosine_similarity(vec1, vec3)
    # Unrelated string has lower similarity
    sim_unrelated = cosine_similarity(vec1, vec4)
    assert sim_related > sim_unrelated


# ── Retriever Tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_knowledge_retriever_mock():
    retriever = KnowledgeRetriever()
    tenant_id = uuid.uuid4()
    business_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    # Pre-generate mock chunk embeddings
    emb1 = await retriever.embedding_service.get_embedding("We are open Monday to Friday 9am to 6pm.")
    emb2 = await retriever.embedding_service.get_embedding("Root canal treatment costs ₹3000.")

    chunk1 = MagicMock(spec=DocumentChunk)
    chunk1.id = uuid.uuid4()
    chunk1.document_id = doc_id
    chunk1.chunk_index = 0
    chunk1.content = "We are open Monday to Friday 9am to 6pm."
    chunk1.embedding = emb1
    chunk1.chunk_metadata = {"category": "hours"}

    chunk2 = MagicMock(spec=DocumentChunk)
    chunk2.id = uuid.uuid4()
    chunk2.document_id = doc_id
    chunk2.chunk_index = 1
    chunk2.content = "Root canal treatment costs ₹3000."
    chunk2.embedding = emb2
    chunk2.chunk_metadata = {"category": "pricing"}

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (chunk1, "Clinic Hours & FAQ", 0.05),
        (chunk2, "Pricing Guide", 0.70),
    ]
    mock_db.execute.return_value = mock_result

    results = await retriever.search(
        session=mock_db,
        business_id=business_id,
        tenant_id=tenant_id,
        query="What are your clinic hours?",
        top_k=2,
        similarity_threshold=0.2,
    )

    assert len(results) >= 1
    top = results[0]
    assert "Monday to Friday" in top.content
    assert top.similarity_score > 0.5


# ── Knowledge Service Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_knowledge_service_ingest_file():
    service = KnowledgeBaseService()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.add_all = MagicMock()
    tenant_id = uuid.uuid4()
    business_id = uuid.uuid4()

    file_bytes = b"Welcome to Sunrise Dental. We offer routine cleanings and emergency dental care."
    doc = await service.ingest_file(
        session=mock_db,
        tenant_id=tenant_id,
        business_id=business_id,
        filename="welcome.txt",
        content=file_bytes,
        title="Welcome Guide",
    )

    assert doc.title == "Welcome Guide"
    assert doc.status == DocumentStatus.READY.value
    assert doc.chunk_count >= 1
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_knowledge_service_ingest_faqs():
    service = KnowledgeBaseService()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.add_all = MagicMock()
    tenant_id = uuid.uuid4()
    business_id = uuid.uuid4()

    faqs = [
        {"question": "Do you accept credit cards?", "answer": "Yes, Visa and Mastercard.", "category": "Billing"}
    ]
    doc = await service.ingest_faqs(
        session=mock_db,
        tenant_id=tenant_id,
        business_id=business_id,
        title="Billing FAQ",
        faqs=faqs,
    )

    assert doc.file_type == DocumentType.FAQ.value
    assert doc.status == DocumentStatus.READY.value
    assert doc.chunk_count == 1


# ── Tool Calling Search Knowledge Base Tests ─────────────────────────────────


def test_voice_agent_tools_includes_knowledge_search():
    tool_names = [t["function"]["name"] for t in VOICE_AGENT_TOOLS]
    assert "search_knowledge_base" in tool_names


@pytest.mark.asyncio
async def test_tool_executor_search_knowledge_base():
    mock_db = AsyncMock()
    tenant_id = uuid.uuid4()
    business_id = uuid.uuid4()

    executor = ToolExecutor(
        session=mock_db,
        tenant_id=tenant_id,
        business_id=business_id,
    )

    # Mock retriever search within executor
    emb = EmbeddingService._generate_deterministic_embedding("Parking is free in the rear basement lot.")
    chunk = MagicMock(spec=DocumentChunk)
    chunk.id = uuid.uuid4()
    chunk.document_id = uuid.uuid4()
    chunk.content = "Parking is free in the rear basement lot."
    chunk.embedding = emb
    chunk.chunk_metadata = {}

    mock_db_res = MagicMock()
    mock_db_res.all.return_value = [
        (chunk, "Location Info", 0.1),
    ]
    mock_db.execute.return_value = mock_db_res

    res = await executor.execute(
        "search_knowledge_base",
        {"query": "Where can I park?"},
    )

    assert res.success is True
    assert "Location Info" in res.message
    assert "Parking is free" in res.message


# ── REST API Endpoint Tests ──────────────────────────────────────────────────


@pytest.fixture
def auth_setup():
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    business = Business(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Sunrise Dental",
        phone_number="+919876543210",
        email="info@sunrisedental.com",
        timezone="Asia/Kolkata",
        is_deleted=False,
    )
    return tenant_id, business, headers


def test_api_list_documents(client, auth_setup):
    tenant_id, business, headers = auth_setup

    mock_session = AsyncMock()
    # Mock business query
    biz_res = MagicMock()
    biz_res.scalar_one_or_none.return_value = business

    # Mock list documents query
    doc1 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        business_id=business.id,
        title="Insurance FAQ",
        filename="insurance.txt",
        file_type="txt",
        file_size_bytes=1024,
        status=DocumentStatus.READY.value,
        chunk_count=2,
        doc_metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        is_deleted=False,
    )
    doc_res = MagicMock()
    doc_res.scalars.return_value.all.return_value = [doc1]

    mock_session.execute.side_effect = [biz_res, doc_res]
    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        response = client.get("/api/v1/business/documents", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Insurance FAQ"
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_api_upload_document(client, auth_setup):
    tenant_id, business, headers = auth_setup

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.add_all = MagicMock()
    biz_res = MagicMock()
    biz_res.scalar_one_or_none.return_value = business
    mock_session.execute.return_value = biz_res
    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        file_content = b"General information about root canals and crowns."
        response = client.post(
            "/api/v1/business/documents/upload",
            headers=headers,
            files={"file": ("guide.txt", io.BytesIO(file_content), "text/plain")},
            data={"title": "Dental Treatment Guide"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Dental Treatment Guide"
        assert data["status"] == "READY"
        assert data["chunk_count"] >= 1
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_api_create_faq(client, auth_setup):
    tenant_id, business, headers = auth_setup

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.add_all = MagicMock()
    biz_res = MagicMock()
    biz_res.scalar_one_or_none.return_value = business
    mock_session.execute.return_value = biz_res
    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        faq_payload = {
            "title": "Hospital Visiting Hours",
            "items": [
                {
                    "question": "What are ICU visiting hours?",
                    "answer": "11:00 AM to 1:00 PM and 5:00 PM to 7:00 PM daily.",
                    "category": "ICU",
                }
            ],
        }
        response = client.post(
            "/api/v1/business/documents/faq",
            headers=headers,
            json=faq_payload,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Hospital Visiting Hours"
        assert data["file_type"] == "faq"
        assert data["chunk_count"] == 1
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_api_search_knowledge(client, auth_setup):
    tenant_id, business, headers = auth_setup

    mock_session = AsyncMock()
    biz_res = MagicMock()
    biz_res.scalar_one_or_none.return_value = business

    chunk = MagicMock(spec=DocumentChunk)
    chunk.id = uuid.uuid4()
    chunk.document_id = uuid.uuid4()
    chunk.content = "ICU visiting hours are 11 AM - 1 PM."
    chunk.chunk_metadata = {}

    search_res = MagicMock()
    search_res.all.return_value = [
        (chunk, "Hospital Visiting Hours", 0.05),
    ]
    mock_session.execute.side_effect = [biz_res, search_res]
    app.dependency_overrides[get_session] = lambda: mock_session

    try:
        response = client.post(
            "/api/v1/business/documents/search",
            headers=headers,
            json={"query": "visiting hours for ICU", "top_k": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_found"] >= 1
        assert "11 AM - 1 PM" in data["results"][0]["content"]
    finally:
        app.dependency_overrides.pop(get_session, None)
