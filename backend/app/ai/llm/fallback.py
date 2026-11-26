"""
app/ai/llm/fallback.py — Resilient Fallback Chain for LLM Invocations

Wraps an ordered chain of LLM providers (e.g. Groq -> Gemini -> OpenAI -> Anthropic).
If a provider fails before producing output (timeout, rate-limit, outage, or missing key),
it transparently fails over to the next healthy provider without dropping the voice turn.
"""

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any

import structlog

from app.ai.llm.base import BaseLLMProvider, LLMMessage, LLMResponse, LLMStreamChunk

logger = structlog.get_logger(__name__)


class FallbackLLMProvider(BaseLLMProvider):
    """Multi-provider resilient fallback chain with timeout protection."""

    def __init__(
        self,
        primary: BaseLLMProvider | None = None,
        secondary: BaseLLMProvider | None = None,
        *,
        providers: Sequence[BaseLLMProvider] | None = None,
        timeout_seconds: float = 15.0,
    ):
        chain: list[BaseLLMProvider] = []
        if providers:
            chain.extend(providers)
        else:
            if primary is not None:
                chain.append(primary)
            if secondary is not None:
                chain.append(secondary)

        if not chain:
            raise ValueError("FallbackLLMProvider requires at least one LLM provider")

        super().__init__(model=chain[0].model, temperature=chain[0].temperature)
        self.providers = chain
        self.primary = chain[0]
        self.secondary = chain[1] if len(chain) > 1 else chain[0]
        self.timeout_seconds = timeout_seconds

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        last_error: Exception | None = None
        for idx, provider in enumerate(self.providers):
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    return await provider.complete(messages, tools, **kwargs)
            except Exception as e:
                last_error = e
                has_next = idx + 1 < len(self.providers)
                if has_next:
                    logger.warning(
                        "LLM provider failed, failing over to next provider",
                        failed_model=provider.model,
                        next_model=self.providers[idx + 1].model,
                        error=str(e),
                    )
        assert last_error is not None
        raise last_error

    async def stream_events(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMStreamChunk]:
        last_error: Exception | None = None
        for idx, provider in enumerate(self.providers):
            emitted_output = False
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    async for chunk in provider.stream_events(messages, tools, **kwargs):
                        if chunk.text_delta or chunk.tool_calls:
                            emitted_output = True
                        yield chunk
                return
            except Exception as e:
                last_error = e
                if emitted_output or idx + 1 >= len(self.providers):
                    raise
                logger.warning(
                    "LLM streaming failed before output, failing over to next provider",
                    failed_model=provider.model,
                    next_model=self.providers[idx + 1].model,
                    error=str(e),
                )
        if last_error is not None:
            raise last_error

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        async for chunk in self.stream_events(messages, tools, **kwargs):
            if chunk.text_delta:
                yield chunk.text_delta
