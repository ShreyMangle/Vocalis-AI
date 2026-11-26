"""
app/ai/llm/anthropic_provider.py — Anthropic Claude Implementation of BaseLLMProvider

Supports Claude 3.5 Haiku / Sonnet via Anthropic Messages API (SDK if installed,
or clean async httpx REST/SSE fallback with full tool_use / tool_result support).
"""

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.ai.llm.base import BaseLLMProvider, LLMMessage, LLMResponse, LLMStreamChunk
from app.core.config import settings


class AnthropicLLMProvider(BaseLLMProvider):
    """Anthropic Claude API Provider (optional paid fallback)."""

    ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(
        self,
        model: str = "claude-3-5-haiku-latest",
        temperature: float = 0.3,
        api_key: str | None = None,
        client: Any | None = None,
        max_tokens: int = 1024,
    ):
        super().__init__(model=model, temperature=temperature)
        resolved_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        self.api_key = resolved_key
        self.max_tokens = max_tokens
        self._has_credentials = bool(client is not None or (resolved_key and resolved_key.strip()))
        self.client = client

        if self.client is None:
            try:
                from anthropic import AsyncAnthropic

                self.client = AsyncAnthropic(api_key=resolved_key or "mock-key")
            except ImportError:
                self.client = None

    def _ensure_ready(self) -> None:
        if not self._has_credentials:
            raise RuntimeError("anthropic API key is not configured")

    def _build_payload(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None,
        stream: bool,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        system_parts: list[str] = []
        formatted: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                if msg.content:
                    system_parts.append(msg.content)
                continue

            if msg.role == "tool":
                tool_block = {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "call_0",
                    "content": msg.content or "",
                }
                if formatted and formatted[-1]["role"] == "user" and isinstance(formatted[-1]["content"], list):
                    formatted[-1]["content"].append(tool_block)
                else:
                    formatted.append({"role": "user", "content": [tool_block]})
                continue

            if msg.role == "assistant" and msg.tool_calls:
                blocks: list[dict[str, Any]] = []
                if msg.content:
                    blocks.append({"type": "text", "text": msg.content})
                for idx, tc in enumerate(msg.tool_calls):
                    fn = tc.get("function", {})
                    raw_args = fn.get("arguments", "{}")
                    try:
                        parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except json.JSONDecodeError:
                        parsed_args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id") or f"call_{idx}",
                            "name": fn.get("name", ""),
                            "input": parsed_args,
                        }
                    )
                formatted.append({"role": "assistant", "content": blocks})
                continue

            formatted.append({"role": msg.role, "content": msg.content or ""})

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": self.temperature,
            "messages": formatted,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if tools:
            payload["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
                }
                for t in tools
                if "function" in t
            ]
        if stream:
            payload["stream"] = True
        return payload

    @staticmethod
    def _parse_response_blocks(content_blocks: Any) -> tuple[str, list[dict[str, Any]]]:
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for idx, block in enumerate(content_blocks or []):
            b_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
            if b_type == "text":
                text_val = block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
                if text_val:
                    text_parts.append(text_val)
            elif b_type == "tool_use":
                tc_id = block.get("id") if isinstance(block, dict) else getattr(block, "id", None)
                tc_name = block.get("name") if isinstance(block, dict) else getattr(block, "name", "")
                tc_input = block.get("input", {}) if isinstance(block, dict) else getattr(block, "input", {})
                tool_calls.append(
                    {
                        "id": tc_id or f"call_{idx}",
                        "type": "function",
                        "function": {
                            "name": tc_name,
                            "arguments": json.dumps(tc_input if isinstance(tc_input, dict) else {}),
                        },
                    }
                )
        return "".join(text_parts), tool_calls

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self._ensure_ready()
        start_time = time.perf_counter()
        payload = self._build_payload(messages, tools, stream=False, kwargs=kwargs)

        if self.client is not None:
            response = await self.client.messages.create(**payload)
            content_blocks = getattr(response, "content", [])
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "input_tokens", 0) or 0 if usage else 0
            completion_tokens = getattr(usage, "output_tokens", 0) or 0 if usage else 0
        else:
            headers = {
                "x-api-key": self.api_key or "",
                "anthropic-version": self.ANTHROPIC_VERSION,
                "content-type": "application/json",
            }
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(self.ANTHROPIC_MESSAGES_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            content_blocks = data.get("content", [])
            usage_dict = data.get("usage") or {}
            prompt_tokens = usage_dict.get("input_tokens", 0) or 0
            completion_tokens = usage_dict.get("output_tokens", 0) or 0

        text, tool_calls = self._parse_response_blocks(content_blocks)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return LLMResponse(
            content=text,
            provider="anthropic",
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
        payload = self._build_payload(messages, tools, stream=True, kwargs=kwargs)

        # Fallback to non-streaming if injected SDK/mock only implements create without streaming flag
        if self.client is not None:
            resp = await self.client.messages.create(**payload)
            if hasattr(resp, "__aiter__"):
                async for chunk in self._iter_sdk_events(resp, start_time):
                    yield chunk
                return
            text, tool_calls = self._parse_response_blocks(getattr(resp, "content", []))
            if text:
                yield LLMStreamChunk(text_delta=text, provider="anthropic", model=self.model)
            yield LLMStreamChunk(
                done=True,
                tool_calls=tool_calls,
                provider="anthropic",
                model=self.model,
                latency_ms=int((time.perf_counter() - start_time) * 1000),
            )
            return

        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": self.ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        tool_buffers: dict[int, dict[str, Any]] = {}
        async with httpx.AsyncClient(timeout=20.0) as http:
            async with http.stream("POST", self.ANTHROPIC_MESSAGES_URL, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw_json = line[6:].strip()
                    if not raw_json or raw_json == "[DONE]":
                        continue
                    event = json.loads(raw_json)
                    chunk = self._process_sse_event(event, tool_buffers)
                    if chunk:
                        yield chunk

        yield self._finalize_tool_chunk(tool_buffers, start_time)

    async def _iter_sdk_events(self, stream_resp: Any, start_time: float) -> AsyncIterator[LLMStreamChunk]:
        tool_buffers: dict[int, dict[str, Any]] = {}
        async for event in stream_resp:
            event_dict = event if isinstance(event, dict) else event.model_dump() if hasattr(event, "model_dump") else {}
            if not event_dict:
                ev_type = getattr(event, "type", None)
                delta = getattr(event, "delta", None)
                if ev_type == "content_block_delta" and getattr(delta, "type", None) == "text_delta":
                    text_val = getattr(delta, "text", "")
                    if text_val:
                        yield LLMStreamChunk(text_delta=text_val, provider="anthropic", model=self.model)
                continue
            chunk = self._process_sse_event(event_dict, tool_buffers)
            if chunk:
                yield chunk
        yield self._finalize_tool_chunk(tool_buffers, start_time)

    def _process_sse_event(
        self,
        event: dict[str, Any],
        tool_buffers: dict[int, dict[str, Any]],
    ) -> LLMStreamChunk | None:
        ev_type = event.get("type")
        idx = event.get("index", 0)
        if ev_type == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                tool_buffers[idx] = {
                    "id": block.get("id") or f"call_{idx}",
                    "type": "function",
                    "function": {"name": block.get("name", ""), "arguments": ""},
                }
        elif ev_type == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta" and delta.get("text"):
                return LLMStreamChunk(text_delta=delta["text"], provider="anthropic", model=self.model)
            if delta.get("type") == "input_json_delta" and idx in tool_buffers:
                tool_buffers[idx]["function"]["arguments"] += delta.get("partial_json", "")
        return None

    def _finalize_tool_chunk(
        self,
        tool_buffers: dict[int, dict[str, Any]],
        start_time: float,
    ) -> LLMStreamChunk:
        final_tools = []
        for idx in sorted(tool_buffers):
            tc = tool_buffers[idx]
            if not tc["function"]["arguments"]:
                tc["function"]["arguments"] = "{}"
            final_tools.append(tc)
        return LLMStreamChunk(
            done=True,
            tool_calls=final_tools,
            provider="anthropic",
            model=self.model,
            latency_ms=int((time.perf_counter() - start_time) * 1000),
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
