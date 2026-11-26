"""
app/ai/rag/parsers.py — Document Parser for RAG Ingestion

Supports:
  - Plain Text (.txt, .md, .csv)
  - PDF Documents (.pdf) via pdfplumber / pypdf
  - Microsoft Word (.docx) via python-docx
  - Structured FAQ (question-and-answer pairs)
"""

import io
import json
import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class DocumentParser:
    """Extracts clean text and metadata from files for RAG processing."""

    @staticmethod
    def parse_plain_text(data: bytes | str) -> str:
        """Decode and clean plain text bytes."""
        if isinstance(data, bytes):
            # Try utf-8 first, fallback to latin-1
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("latin-1", errors="replace")
        else:
            text = str(data)

        # Normalize line endings and whitespace
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    @staticmethod
    def parse_pdf(data: bytes) -> str:
        """Extract text from PDF file bytes."""
        text_parts: list[str] = []

        # 1. Attempt with pdfplumber first (best layout preservation)
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"[Page {page_idx + 1}]\n{page_text.strip()}")
            if text_parts:
                return "\n\n".join(text_parts)
        except Exception as exc:
            logger.warning("pdfplumber_failed_trying_pypdf", error=str(exc))

        # 2. Fallback to pypdf
        try:
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(data))
            for page_idx, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"[Page {page_idx + 1}]\n{page_text.strip()}")
            if text_parts:
                return "\n\n".join(text_parts)
        except Exception as exc:
            logger.error("pypdf_failed", error=str(exc))

        # If empty or extraction failed, return plain text fallback
        if not text_parts:
            return DocumentParser.parse_plain_text(data)

        return "\n\n".join(text_parts)

    @staticmethod
    def parse_docx(data: bytes) -> str:
        """Extract paragraphs and tables from DOCX bytes."""
        try:
            import docx

            doc = docx.Document(io.BytesIO(data))
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

            # Also extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        paragraphs.append(row_text)

            return "\n\n".join(paragraphs)
        except Exception as exc:
            logger.error("docx_parsing_failed", error=str(exc))
            return DocumentParser.parse_plain_text(data)

    @staticmethod
    def parse_faq_items(faq_items: list[dict[str, Any]]) -> str:
        """Format FAQ pairs into rich, structured markdown text."""
        sections: list[str] = []
        for idx, item in enumerate(faq_items, 1):
            q = item.get("question", "").strip()
            a = item.get("answer", "").strip()
            category = item.get("category", "")
            cat_header = f" [{category}]" if category else ""
            if q and a:
                sections.append(f"Q{idx}{cat_header}: {q}\nA: {a}")

        return "\n\n".join(sections)

    @classmethod
    def extract_text(cls, filename: str, content: bytes) -> str:
        """Detect file type by extension and extract clean text content."""
        ext = filename.lower().split(".")[-1] if "." in filename else ""

        if ext == "pdf":
            return cls.parse_pdf(content)
        elif ext in ("docx", "doc"):
            return cls.parse_docx(content)
        elif ext in ("json",):
            try:
                parsed = json.loads(content.decode("utf-8", errors="replace"))
                if isinstance(parsed, list):
                    # Check if list of FAQ items
                    if all(isinstance(i, dict) and "question" in i for i in parsed):
                        return cls.parse_faq_items(parsed)
                return json.dumps(parsed, indent=2)
            except Exception:
                return cls.parse_plain_text(content)
        else:
            return cls.parse_plain_text(content)
