"""
app/ai/rag/chunker.py — Token-Aware Semantic Text Chunker

Splits large documents into overlapping semantic chunks optimized for
retrieval and LLM context injection.
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""

    chunk_index: int
    content: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


class TokenChunker:
    """
    Token-aware text chunker with sliding window overlap.
    Preserves paragraph and sentence boundaries wherever possible.
    """

    def __init__(
        self,
        chunk_size: int = 400,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding_name = encoding_name

        try:
            import tiktoken

            self._tokenizer = tiktoken.get_encoding(encoding_name)
        except Exception as exc:
            logger.warning("tiktoken_init_fallback", error=str(exc))
            self._tokenizer = None

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken, or fallback to 4 chars per token heuristic."""
        if not text:
            return 0
        if self._tokenizer:
            try:
                return len(self._tokenizer.encode(text))
            except Exception:
                pass
        return max(1, len(text) // 4)

    def chunk_text(
        self,
        text: str,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """
        Split text into overlapping chunks respecting paragraph/sentence boundaries.
        """
        base_metadata = base_metadata or {}
        cleaned = text.strip()
        if not cleaned:
            return []

        # If entire text fits inside one chunk, return single chunk
        total_tokens = self.count_tokens(cleaned)
        if total_tokens <= self.chunk_size:
            return [
                TextChunk(
                    chunk_index=0,
                    content=cleaned,
                    token_count=total_tokens,
                    metadata=base_metadata.copy(),
                )
            ]

        # Break text into natural blocks (paragraphs first)
        paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [cleaned]

        units: list[str] = []
        for p in paragraphs:
            # If paragraph itself is too large, split by sentences
            if self.count_tokens(p) > self.chunk_size:
                sentences = [s.strip() for s in p.replace(". ", ".\n").split("\n") if s.strip()]
                units.extend(sentences)
            else:
                units.append(p)

        chunks: list[TextChunk] = []
        current_units: list[str] = []
        current_tokens = 0
        chunk_idx = 0

        for unit in units:
            unit_tokens = self.count_tokens(unit)

            if current_tokens + unit_tokens > self.chunk_size and current_units:
                # Flush current chunk
                chunk_str = "\n\n".join(current_units)
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_idx,
                        content=chunk_str,
                        token_count=self.count_tokens(chunk_str),
                        metadata=base_metadata.copy(),
                    )
                )
                chunk_idx += 1

                # Carry over overlap units from tail
                overlap_units: list[str] = []
                overlap_tokens = 0
                for prev_unit in reversed(current_units):
                    p_tok = self.count_tokens(prev_unit)
                    if overlap_tokens + p_tok <= self.chunk_overlap:
                        overlap_units.insert(0, prev_unit)
                        overlap_tokens += p_tok
                    else:
                        break

                current_units = overlap_units
                current_tokens = overlap_tokens

            current_units.append(unit)
            current_tokens += unit_tokens

        # Flush remaining chunk
        if current_units:
            chunk_str = "\n\n".join(current_units)
            chunks.append(
                TextChunk(
                    chunk_index=chunk_idx,
                    content=chunk_str,
                    token_count=self.count_tokens(chunk_str),
                    metadata=base_metadata.copy(),
                )
            )

        return chunks
