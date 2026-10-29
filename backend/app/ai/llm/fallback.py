"""
app/ai/llm/fallback.py — Resilient Fallback Chain for LLM Invocations

Wraps a primary and secondary LLM provider.
If the primary encounters an outage, timeout, or rate-limit error,
it automatically falls back to the secondary provider without dropping
the caller's voice stream.
"""

from collections.abc import AsyncIterator
from typing import Any

import structlog

from app.ai.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = structlog.get_logger(__name__)


class FallbackLLMProvider(BaseLLMProvider):
    """Resilient provider chain."""

    def __init__(
        self,
        primary: BaseLLMProvider,
        secondary: BaseLLMProvider,
    ):
        super().__init__(model=primary.model, temperature=primary.temperature)
        self.primary = primary
        self.secondary = secondary

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        try:
            return await self.primary.complete(messages, tools, **kwargs)
        except Exception as e:
            logger.warning(
                "Primary LLM provider failed, falling back to secondary",
                primary_model=self.primary.model,
                secondary_model=self.secondary.model,
                error=str(e),
            )
            return await self.secondary.complete(messages, tools, **kwargs)

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        try:
            async for chunk in self.primary.stream(messages, tools, **kwargs):
                yield chunk
        except Exception as e:
            logger.warning(
                "Primary LLM streaming failed, falling back to secondary",
                primary_model=self.primary.model,
                secondary_model=self.secondary.model,
                error=str(e),
            )
            async for chunk in self.secondary.stream(messages, tools, **kwargs):
                yield chunk

