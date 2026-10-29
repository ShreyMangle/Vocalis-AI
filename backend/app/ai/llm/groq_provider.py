"""
app/ai/llm/groq_provider.py — Groq Implementation of BaseLLMProvider

Connects to Groq API for ultra-low latency Llama-3.3-70b and Llama-3.1-8b inference.
Ideal for voice agents where sub-second latency is critical.
"""

import time
from collections.abc import AsyncIterator
from typing import Any

import structlog

from app.ai.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from app.core.config import settings

logger = structlog.get_logger(__name__)


class GroqLLMProvider(BaseLLMProvider):
    """Groq API Provider."""

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        api_key: str | None = None,
        client: Any | None = None,
    ):
        super().__init__(model=model, temperature=temperature)
        self.api_key = api_key or settings.GROQ_API_KEY
        if client:
            self.client = client
        else:
            from groq import AsyncGroq
            self.client = AsyncGroq(api_key=self.api_key or "mock-key")

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        start_time = time.perf_counter()
        formatted_messages = [m.to_dict() for m in messages]

        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": self.temperature,
            **kwargs,
        }
        if tools:
            request_kwargs["tools"] = tools

        response = await self.client.chat.completions.create(**request_kwargs)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls = []
        if getattr(choice.message, "tool_calls", None):
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        return LLMResponse(
            content=content,
            provider="groq",
            model=self.model,
            tool_calls=tool_calls,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        formatted_messages = [m.to_dict() for m in messages]
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": self.temperature,
            "stream": True,
            **kwargs,
        }
        if tools:
            request_kwargs["tools"] = tools

        stream_resp = await self.client.chat.completions.create(**request_kwargs)
        async for chunk in stream_resp:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

