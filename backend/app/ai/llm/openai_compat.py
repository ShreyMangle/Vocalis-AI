"""
app/ai/llm/openai_compat.py — Shared OpenAI Chat Completions Compatible Base Provider

Eliminates duplicated completion and streaming logic across OpenAI, Groq, and
Google Gemini OpenAI-compatible APIs while cleanly supporting streamed tool calls.
"""

import time
from collections.abc import AsyncIterator
from typing import Any

from app.ai.llm.base import BaseLLMProvider, LLMMessage, LLMResponse, LLMStreamChunk


class OpenAICompatibleLLMProvider(BaseLLMProvider):
    """Shared implementation for providers exposing OpenAI Chat Completions APIs."""

    provider_name: str = "openai"

    def __init__(
        self,
        model: str,
        temperature: float = 0.3,
        api_key: str | None = None,
        base_url: str | None = None,
        client: Any | None = None,
        provider_name: str = "openai",
    ):
        super().__init__(model=model, temperature=temperature)
        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = base_url
        self._has_credentials = bool(client is not None or (api_key and api_key.strip()))

        if client is not None:
            self.client = client
        else:
            self.client = self._build_default_client(api_key=api_key, base_url=base_url)

    def _build_default_client(self, api_key: str | None, base_url: str | None) -> Any:
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {"api_key": api_key or "mock-key"}
        if base_url:
            kwargs["base_url"] = base_url
        return AsyncOpenAI(**kwargs)

    def _ensure_ready(self) -> None:
        if not self._has_credentials:
            raise RuntimeError(f"{self.provider_name} API key is not configured")

    @staticmethod
    def _build_request_kwargs(
        model: str,
        temperature: float,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None,
        stream: bool,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            **extra,
        }
        if stream:
            request_kwargs["stream"] = True
        if tools:
            request_kwargs["tools"] = tools
        return request_kwargs

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self._ensure_ready()
        start_time = time.perf_counter()
        request_kwargs = self._build_request_kwargs(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
            tools=tools,
            stream=False,
            extra=kwargs,
        )

        response = await self.client.chat.completions.create(**request_kwargs)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls: list[dict[str, Any]] = []
        if getattr(choice.message, "tool_calls", None):
            for idx, tc in enumerate(choice.message.tool_calls):
                tool_calls.append(
                    {
                        "id": getattr(tc, "id", None) or f"call_{idx}",
                        "type": getattr(tc, "type", "function") or "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0 if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0 if usage else 0

        return LLMResponse(
            content=content,
            provider=self.provider_name,
            model=self.model,
            tool_calls=tool_calls,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def stream_events(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMStreamChunk]:
        self._ensure_ready()
        start_time = time.perf_counter()
        request_kwargs = self._build_request_kwargs(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
            tools=tools,
            stream=True,
            extra=kwargs,
        )

        stream_resp = await self.client.chat.completions.create(**request_kwargs)
        tool_buffers: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None

        async for chunk in stream_resp:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue

            choice = choices[0]
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason

            delta = getattr(choice, "delta", None)
            if not delta:
                continue

            text_piece = getattr(delta, "content", None)
            if text_piece:
                yield LLMStreamChunk(
                    text_delta=text_piece,
                    provider=self.provider_name,
                    model=self.model,
                )

            delta_tool_calls = getattr(delta, "tool_calls", None)
            if delta_tool_calls:
                for tc_delta in delta_tool_calls:
                    idx = getattr(tc_delta, "index", 0)
                    if idx is None:
                        idx = 0
                    entry = tool_buffers.setdefault(
                        idx,
                        {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        },
                    )
                    if getattr(tc_delta, "id", None):
                        entry["id"] = tc_delta.id
                    if getattr(tc_delta, "type", None):
                        entry["type"] = tc_delta.type
                    fn_delta = getattr(tc_delta, "function", None)
                    if fn_delta:
                        if getattr(fn_delta, "name", None):
                            entry["function"]["name"] += fn_delta.name
                        if getattr(fn_delta, "arguments", None):
                            entry["function"]["arguments"] += fn_delta.arguments

        final_tool_calls: list[dict[str, Any]] = []
        for idx in sorted(tool_buffers):
            tc = tool_buffers[idx]
            if not tc["id"]:
                tc["id"] = f"call_{idx}"
            final_tool_calls.append(tc)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        yield LLMStreamChunk(
            done=True,
            tool_calls=final_tool_calls,
            provider=self.provider_name,
            model=self.model,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        async for chunk in self.stream_events(messages, tools, **kwargs):
            if chunk.text_delta:
                yield chunk.text_delta
