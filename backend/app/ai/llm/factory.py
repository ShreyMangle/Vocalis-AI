"""
app/ai/llm/factory.py — Factory Function to Instantiate Configured LLM Providers

Prioritizes free-tier zero-cost providers first (Groq Llama 3.3 -> Google Gemini Flash)
followed by optional paid backups (OpenAI -> Anthropic) whenever credentials are configured.
"""

from app.ai.llm.anthropic_provider import AnthropicLLMProvider
from app.ai.llm.base import BaseLLMProvider
from app.ai.llm.fallback import FallbackLLMProvider
from app.ai.llm.gemini_provider import GeminiLLMProvider
from app.ai.llm.groq_provider import GroqLLMProvider
from app.ai.llm.openai_provider import OpenAILLMProvider
from app.core.config import settings

DEFAULT_MODELS: dict[str, str] = {
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
}


def _build_provider(name: str, model: str | None, temperature: float) -> BaseLLMProvider:
    resolved_model = model or DEFAULT_MODELS.get(name, DEFAULT_MODELS["groq"])
    if name == "groq":
        return GroqLLMProvider(model=resolved_model, temperature=temperature)
    if name == "gemini":
        return GeminiLLMProvider(model=resolved_model, temperature=temperature)
    if name == "anthropic":
        return AnthropicLLMProvider(model=resolved_model, temperature=temperature)
    return OpenAILLMProvider(model=resolved_model, temperature=temperature)


def get_llm_provider(
    provider_name: str | None = None,
    model: str | None = None,
    temperature: float = 0.3,
    enable_fallback: bool = True,
    timeout_seconds: float = 15.0,
) -> BaseLLMProvider:
    """Instantiate the requested LLM provider with free-first resilient fallbacks."""
    requested = (provider_name or settings.DEFAULT_LLM_PROVIDER).lower().strip()
    if requested not in DEFAULT_MODELS:
        requested = "groq"

    primary_model = model
    if primary_model is None and requested == settings.DEFAULT_LLM_PROVIDER.lower():
        primary_model = settings.DEFAULT_LLM_MODEL

    primary = _build_provider(requested, primary_model, temperature)
    if not enable_fallback:
        return primary

    fallback_candidates: list[tuple[str, str | None]] = [
        ("groq", settings.GROQ_API_KEY),
        ("gemini", settings.GEMINI_API_KEY),
        ("openai", settings.OPENAI_API_KEY),
        ("anthropic", settings.ANTHROPIC_API_KEY),
    ]

    chain: list[BaseLLMProvider] = [primary]
    for candidate_name, api_key in fallback_candidates:
        if candidate_name != requested and api_key:
            chain.append(_build_provider(candidate_name, None, temperature))

    if len(chain) == 1:
        return primary
    return FallbackLLMProvider(providers=chain, timeout_seconds=timeout_seconds)
