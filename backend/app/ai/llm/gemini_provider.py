"""
app/ai/llm/gemini_provider.py — Google Gemini Free-Tier Implementation of BaseLLMProvider

Connects to Google AI Studio's Gemini API (default: gemini-2.0-flash, generous free tier)
via Google's official OpenAI-compatible endpoint for full streaming and tool calling.
"""

from typing import Any

from app.ai.llm.openai_compat import OpenAICompatibleLLMProvider
from app.core.config import settings


class GeminiLLMProvider(OpenAICompatibleLLMProvider):
    """Google Gemini API Provider (free-tier zero-cost primary/fallback)."""

    GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.3,
        api_key: str | None = None,
        client: Any | None = None,
    ):
        resolved_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        super().__init__(
            model=model,
            temperature=temperature,
            api_key=resolved_key,
            base_url=self.GEMINI_OPENAI_BASE_URL,
            client=client,
            provider_name="gemini",
        )
