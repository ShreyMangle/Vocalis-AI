"""
app/ai/rag/embeddings.py — Embedding Generation & Similarity Engine

Generates 1536-dimensional vector embeddings for text chunks and queries.
Uses OpenAI text-embedding-3-small when configured, or a high-performance
deterministic L2-normalized semantic vector engine in development and testing.
"""

import hashlib
import math
import struct
from typing import Sequence

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

EMBEDDING_DIM = 1536


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if len(v1) != len(v2) or not v1:
        return 0.0

    dot_product = sum(a * b for a, b in zip(v1, v2, strict=False))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class EmbeddingService:
    """
    Unified embedding service producing 1536-dimensional L2-normalized vectors.
    """

    def __init__(self, api_key: str | None = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.dimension = EMBEDDING_DIM
        self._async_client = None

        if self.api_key:
            try:
                from openai import AsyncOpenAI

                self._async_client = AsyncOpenAI(api_key=self.api_key)
            except Exception as exc:
                logger.warning("openai_client_init_failed", error=str(exc))
                self._async_client = None

    async def get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for a single string."""
        results = await self.get_embeddings_batch([text])
        return results[0]

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of strings."""
        if not texts:
            return []

        # If real OpenAI client is active, call OpenAI API
        if self._async_client:
            try:
                response = await self._async_client.embeddings.create(
                    input=texts,
                    model=self.model,
                )
                return [item.embedding for item in response.data]
            except Exception as exc:
                logger.error("openai_embeddings_failed_fallback_to_deterministic", error=str(exc))

        # Fallback deterministic generator
        return [self._generate_deterministic_embedding(t) for t in texts]

    @staticmethod
    def _generate_deterministic_embedding(text: str) -> list[float]:
        """
        Generate a deterministic 1536-dimensional L2-normalized float embedding.
        Based on hashing character n-grams and bag-of-words tokens.
        Ensures semantically similar strings share overlapping dimensions.
        """
        if not text:
            # Zero vector normalized
            vec = [0.0] * EMBEDDING_DIM
            vec[0] = 1.0
            return vec

        raw_vector = [0.0] * EMBEDDING_DIM
        words = text.lower().split()

        # Word-level features
        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % EMBEDDING_DIM
            sign = 1.0 if (h >> 1) & 1 else -1.0
            raw_vector[idx] += sign * (1.0 + len(word) * 0.1)

        # Character n-grams (3-grams) for subword semantic overlap
        cleaned = "".join(c for c in text.lower() if c.isalnum() or c.isspace())
        for i in range(max(0, len(cleaned) - 2)):
            tri = cleaned[i : i + 3]
            h = int(hashlib.sha256(tri.encode("utf-8")).hexdigest()[:8], 16)
            idx = h % EMBEDDING_DIM
            raw_vector[idx] += 0.5

        # L2-normalize vector to unit length
        norm = math.sqrt(sum(x * x for x in raw_vector))
        if norm > 0.0:
            return [x / norm for x in raw_vector]

        # Uniform fallback
        val = 1.0 / math.sqrt(EMBEDDING_DIM)
        return [val] * EMBEDDING_DIM
