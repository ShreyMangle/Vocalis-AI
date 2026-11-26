"""
app/ai/llm/groq_provider.py — Groq Implementation of BaseLLMProvider

Connects to Groq API for ultra-low latency Llama-3.3-70b-versatile and Llama-3.1-8b-instant inference.
Uses the groq SDK when installed, falling back seamlessly to Groq's OpenAI-compatible endpoint.
"""

from typing import Any

from app.ai.llm.openai_compat import OpenAICompatibleLLMProvider
from app.core.config import settings


class GroqLLMProvider(OpenAICompatibleLLMProvider):
    """Groq API Provider (free-tier ultra-low latency primary)."""

    GROQ_OPENAI_BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        api_key: str | None = None,
        client: Any | None = None,
    ):
        resolved_key = api_key if api_key is not None else settings.GROQ_API_KEY
        super().__init__(
            model=model,
            temperature=temperature,
            api_key=resolved_key,
            base_url=self.GROQ_OPENAI_BASE_URL,
            client=client,
            provider_name="groq",
        )

    def _build_default_client(self, api_key: str | None, base_url: str | None) -> Any:
        try:
            from groq import AsyncGroq

            return AsyncGroq(api_key=api_key or "mock-key")
        except ImportError:
            return super()._build_default_client(api_key=api_key, base_url=base_url)
