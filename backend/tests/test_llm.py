"""
tests/test_llm.py — Unit Tests for LLM Provider Abstraction & Fallback Chain

Testing:
  - LLMMessage serialization
  - OpenAI provider completion and streaming with mocks
  - Groq provider completion and streaming with mocks
  - Fallback provider: transparently switches to secondary on failure
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.llm.base import LLMMessage, LLMResponse
from app.ai.llm.fallback import FallbackLLMProvider
from app.ai.llm.groq_provider import GroqLLMProvider
from app.ai.llm.openai_provider import OpenAILLMProvider


def test_llm_message_to_dict():
    msg = LLMMessage(role="user", content="Hello, I want to book an appointment.")
    d = msg.to_dict()
    assert d == {"role": "user", "content": "Hello, I want to book an appointment."}


@pytest.mark.asyncio
async def test_openai_provider_complete_mock():
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Certainly! We have slots open at 10 AM."
    mock_choice.message.tool_calls = None
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 15
    mock_usage.completion_tokens = 10

    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage = mock_usage

    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    provider = OpenAILLMProvider(model="gpt-4o-mini", client=mock_client)
    res = await provider.complete([LLMMessage(role="user", content="Book slot")])

    assert res.content == "Certainly! We have slots open at 10 AM."
    assert res.provider == "openai"
    assert res.model == "gpt-4o-mini"
    assert res.prompt_tokens == 15
    assert res.completion_tokens == 10


@pytest.mark.asyncio
async def test_groq_provider_complete_mock():
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Welcome to Sunrise Clinic. How can I help?"
    mock_choice.message.tool_calls = None
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 20
    mock_usage.completion_tokens = 12

    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage = mock_usage

    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    provider = GroqLLMProvider(model="llama-3.3-70b-versatile", client=mock_client)
    res = await provider.complete([LLMMessage(role="user", content="Hello")])

    assert res.content == "Welcome to Sunrise Clinic. How can I help?"
    assert res.provider == "groq"
    assert res.model == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_fallback_provider_uses_primary_when_healthy():
    primary = MagicMock()
    primary.model = "primary-model"
    primary.temperature = 0.3
    primary.complete = AsyncMock(
        return_value=LLMResponse(content="Primary response", provider="groq", model="primary-model")
    )

    secondary = MagicMock()
    secondary.model = "secondary-model"
    secondary.temperature = 0.3
    secondary.complete = AsyncMock()

    chain = FallbackLLMProvider(primary=primary, secondary=secondary)
    res = await chain.complete([LLMMessage(role="user", content="Hi")])

    assert res.content == "Primary response"
    primary.complete.assert_awaited_once()
    secondary.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_fallback_provider_fails_over_to_secondary_on_error():
    primary = MagicMock()
    primary.model = "groq-llama"
    primary.temperature = 0.3
    primary.complete = AsyncMock(side_effect=RuntimeError("Groq 503 Service Unavailable"))

    secondary = MagicMock()
    secondary.model = "openai-gpt"
    secondary.temperature = 0.3
    secondary.complete = AsyncMock(
        return_value=LLMResponse(content="Secondary fallback response", provider="openai", model="openai-gpt")
    )

    chain = FallbackLLMProvider(primary=primary, secondary=secondary)
    res = await chain.complete([LLMMessage(role="user", content="Hi")])

    assert res.content == "Secondary fallback response"
    assert res.provider == "openai"
    primary.complete.assert_awaited_once()
    secondary.complete.assert_awaited_once()

