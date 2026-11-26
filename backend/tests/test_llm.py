"""
tests/test_llm.py — Unit Tests for LLM Provider Abstraction & Fallback Chain

Testing:
  - LLMMessage serialization
  - OpenAI, Groq, Gemini, and Anthropic providers (completion, streaming, tool calls)
  - Multi-provider FallbackLLMProvider fail-over on error and pre-output stream errors
  - Free-first factory ordering (groq -> gemini -> openai -> anthropic)
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.llm.anthropic_provider import AnthropicLLMProvider
from app.ai.llm.base import LLMMessage, LLMResponse, LLMStreamChunk
from app.ai.llm.factory import get_llm_provider
from app.ai.llm.fallback import FallbackLLMProvider
from app.ai.llm.gemini_provider import GeminiLLMProvider
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
async def test_gemini_provider_stream_events_with_tool_call_delta():
    async def _fake_stream():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=None,
                    delta=SimpleNamespace(content="Checking ", tool_calls=None),
                )
            ]
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=None,
                    delta=SimpleNamespace(
                        content="now.",
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id="call_gem_1",
                                type="function",
                                function=SimpleNamespace(name="check_avail", arguments='{"target_date":'),
                            )
                        ],
                    ),
                )
            ]
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="tool_calls",
                    delta=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id=None,
                                type=None,
                                function=SimpleNamespace(name="ability", arguments='"2026-11-27"}'),
                            )
                        ],
                    ),
                )
            ]
        )

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_stream())

    provider = GeminiLLMProvider(model="gemini-2.0-flash", client=mock_client)
    chunks = [chunk async for chunk in provider.stream_events([LLMMessage(role="user", content="Slots tomorrow?")])]

    text = "".join(c.text_delta for c in chunks)
    done_chunk = [c for c in chunks if c.done][-1]
    assert text == "Checking now."
    assert done_chunk.provider == "gemini"
    assert done_chunk.model == "gemini-2.0-flash"
    assert len(done_chunk.tool_calls) == 1
    assert done_chunk.tool_calls[0]["id"] == "call_gem_1"
    assert done_chunk.tool_calls[0]["function"]["name"] == "check_availability"
    assert done_chunk.tool_calls[0]["function"]["arguments"] == '{"target_date":"2026-11-27"}'


@pytest.mark.asyncio
async def test_anthropic_provider_complete_and_payload_conversion():
    mock_client = MagicMock()
    mock_resp = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Checking slots. "),
            SimpleNamespace(
                type="tool_use",
                id="toolu_1",
                name="check_availability",
                input={"target_date": "2026-11-28"},
            ),
        ],
        usage=SimpleNamespace(input_tokens=30, output_tokens=15),
    )
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    provider = AnthropicLLMProvider(model="claude-3-5-haiku-latest", client=mock_client)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "check_availability",
                "description": "Check booking slots",
                "parameters": {"type": "object", "properties": {"target_date": {"type": "string"}}},
            },
        }
    ]
    res = await provider.complete(
        [
            LLMMessage(role="system", content="You are a polite receptionist."),
            LLMMessage(role="user", content="Do you have slots?"),
        ],
        tools=tools,
    )

    assert res.provider == "anthropic"
    assert res.content == "Checking slots. "
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0]["function"]["name"] == "check_availability"
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "You are a polite receptionist."
    assert call_kwargs["tools"][0]["input_schema"]["type"] == "object"


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
    secondary.model = "gemini-2.0-flash"
    secondary.temperature = 0.3
    secondary.complete = AsyncMock(
        return_value=LLMResponse(content="Secondary fallback response", provider="gemini", model="gemini-2.0-flash")
    )

    chain = FallbackLLMProvider(primary=primary, secondary=secondary)
    res = await chain.complete([LLMMessage(role="user", content="Hi")])

    assert res.content == "Secondary fallback response"
    assert res.provider == "gemini"
    primary.complete.assert_awaited_once()
    secondary.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_fallback_chain_streaming_failover_before_output():
    class FailingStreamProvider:
        model = "groq-primary"
        temperature = 0.3

        async def stream_events(self, messages, tools=None, **kwargs):
            raise RuntimeError("429 rate limited")
            yield LLMStreamChunk()  # pragma: no cover

    class HealthyStreamProvider:
        model = "gemini-2.0-flash"
        temperature = 0.3

        async def stream_events(self, messages, tools=None, **kwargs):
            yield LLMStreamChunk(text_delta="Hello from Gemini.", provider="gemini", model="gemini-2.0-flash")
            yield LLMStreamChunk(done=True, provider="gemini", model="gemini-2.0-flash")

    chain = FallbackLLMProvider(providers=[FailingStreamProvider(), HealthyStreamProvider()])
    chunks = [c async for c in chain.stream_events([LLMMessage(role="user", content="Hi")])]
    assert "".join(c.text_delta for c in chunks) == "Hello from Gemini."


@pytest.mark.asyncio
async def test_factory_free_first_chain_and_fast_unconfigured_error():
    with patch("app.ai.llm.factory.settings") as mock_settings:
        mock_settings.DEFAULT_LLM_PROVIDER = "groq"
        mock_settings.DEFAULT_LLM_MODEL = "llama-3.3-70b-versatile"
        mock_settings.GROQ_API_KEY = "gsk_test"
        mock_settings.GEMINI_API_KEY = "gem_test"
        mock_settings.OPENAI_API_KEY = "sk_test"
        mock_settings.ANTHROPIC_API_KEY = "ant_test"

        provider = get_llm_provider("groq")
        assert isinstance(provider, FallbackLLMProvider)
        names = [type(p).__name__ for p in provider.providers]
        assert names == [
            "GroqLLMProvider",
            "GeminiLLMProvider",
            "OpenAILLMProvider",
            "AnthropicLLMProvider",
        ]

    # Unconfigured provider fails cleanly without network calls
    unconfigured = GroqLLMProvider(api_key=None)
    with pytest.raises(RuntimeError, match="not configured"):
        await unconfigured.complete([LLMMessage(role="user", content="Hello")])
