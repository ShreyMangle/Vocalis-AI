"""
app/ai/llm/factory.py — Factory Function to Instantiate Configured LLM Providers
"""

from app.ai.llm.base import BaseLLMProvider
from app.ai.llm.fallback import FallbackLLMProvider
from app.ai.llm.groq_provider import GroqLLMProvider
from app.ai.llm.openai_provider import OpenAILLMProvider
from app.core.config import settings


def get_llm_provider(
    provider_name: str | None = None,
    model: str | None = None,
    temperature: float = 0.3,
    enable_fallback: bool = True,
) -> BaseLLMProvider:
    """Instantiate the requested LLM provider with optional fallback."""
    provider = (provider_name or settings.DEFAULT_LLM_PROVIDER).lower()

    if provider == "groq":
        primary = GroqLLMProvider(
            model=model or "llama-3.3-70b-versatile",
            temperature=temperature,
        )
        if enable_fallback and settings.OPENAI_API_KEY:
            secondary = OpenAILLMProvider(
                model="gpt-4o-mini",
                temperature=temperature,
            )
            return FallbackLLMProvider(primary=primary, secondary=secondary)
        return primary

    # Default to OpenAI
    primary = OpenAILLMProvider(
        model=model or "gpt-4o-mini",
        temperature=temperature,
    )
    if enable_fallback and settings.GROQ_API_KEY:
        secondary = GroqLLMProvider(
            model="llama-3.3-70b-versatile",
            temperature=temperature,
        )
        return FallbackLLMProvider(primary=primary, secondary=secondary)
    return primary

