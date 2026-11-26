"""
app/ai/llm/openai_provider.py — OpenAI Implementation of BaseLLMProvider

Connects to OpenAI API using AsyncOpenAI for GPT-4o, GPT-4o-mini, etc.
Supports streaming tokens and function/tool calls.
"""

from typing import Any

from app.ai.llm.openai_compat import OpenAICompatibleLLMProvider
from app.core.config import settings


class OpenAILLMProvider(OpenAICompatibleLLMProvider):
    """OpenAI API Provider."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        api_key: str | None = None,
        client: Any | None = None,
    ):
        resolved_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        super().__init__(
            model=model,
            temperature=temperature,
            api_key=resolved_key,
            client=client,
            provider_name="openai",
        )
