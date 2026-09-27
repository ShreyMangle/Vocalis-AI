"""
app/core/config.py — Application Configuration

CONCEPT: Configuration Management
==================================
Every application needs settings: database URL, API keys, port numbers, etc.
The WRONG way: hardcode them directly in code → secrets leak to GitHub, can't change per environment.
The RIGHT way: read from environment variables (.env file locally, real env vars in production).

pydantic-settings does this beautifully:
- It reads environment variables automatically.
- It validates them (e.g., ensures DATABASE_URL is a real URL).
- It gives you type-safe config objects.

HOW IT WORKS:
1. You define a Settings class with typed fields.
2. pydantic-settings reads matching env vars (case-insensitive).
3. You access settings like: settings.DATABASE_URL

EXAMPLE:
  .env file:          DATABASE_URL=postgresql://...
  Code:               settings.database_url  ← pydantic reads it automatically
"""

from functools import lru_cache

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All application configuration lives here.
    
    @lru_cache (used below) means this class is only instantiated ONCE
    and reused everywhere. This is important because reading .env files
    has a small cost — we don't want to do it 1000 times per second.
    """

    # -------------------------------------------------------------------------
    # Pydantic-settings config
    # env_file = ".env" tells it to load from the .env file in the backend dir
    # extra = "ignore" means unknown env vars won't cause errors
    # -------------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # APPLICATION
    # =========================================================================
    APP_NAME: str = "VoxAI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    # =========================================================================
    # SERVER
    # =========================================================================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # CORS: Which frontend origins are allowed to call our API.
    # In dev, we allow localhost. In prod, only our actual domain.
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
        "http://localhost:80",    # Docker nginx
    ]

    # =========================================================================
    # DATABASE
    # =========================================================================
    # PostgresDsn is a pydantic type that validates the URL format.
    # Example: postgresql+asyncpg://user:password@localhost:5432/voxai_db
    # The "+asyncpg" part tells SQLAlchemy to use the async driver.
    DATABASE_URL: PostgresDsn

    # How many DB connections to keep open in the pool.
    # Pool = a group of pre-opened connections so we don't open/close for each request.
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20  # Extra connections allowed during traffic spikes
    DB_POOL_TIMEOUT: int = 30  # Seconds to wait for a connection from the pool

    # =========================================================================
    # REDIS
    # =========================================================================
    # Example: redis://localhost:6379/0
    # The /0 means "database 0" — Redis supports 16 logical databases (0-15).
    REDIS_URL: RedisDsn

    # =========================================================================
    # SECURITY
    # =========================================================================
    # JWT_SECRET is used to sign tokens. If someone steals this, they can forge
    # any user's token. In production this MUST be a long random string.
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"  # HMAC SHA-256 — the signing algorithm
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15   # Short-lived: 15 minutes
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7       # Long-lived: 7 days

    @field_validator("JWT_SECRET")
    @classmethod
    def jwt_secret_must_be_long(cls, v: str) -> str:
        """Enforce minimum secret length to prevent weak signing keys."""
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long")
        return v

    # =========================================================================
    # AI PROVIDERS
    # =========================================================================
    # These are optional — if not set, the system falls back to free providers.
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    # Default LLM to use when creating a new agent
    DEFAULT_LLM_PROVIDER: str = "groq"   # groq is free, great for development
    DEFAULT_LLM_MODEL: str = "llama-3.1-70b-versatile"

    # =========================================================================
    # SPEECH PROVIDERS
    # =========================================================================
    DEEPGRAM_API_KEY: str | None = None
    CARTESIA_API_KEY: str | None = None
    ELEVENLABS_API_KEY: str | None = None

    DEFAULT_STT_PROVIDER: str = "deepgram"
    DEFAULT_TTS_PROVIDER: str = "edge"   # edge-tts is free, for development

    # =========================================================================
    # TELEPHONY
    # =========================================================================
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_PHONE_NUMBER: str | None = None

    VOBIZ_API_KEY: str | None = None
    VOBIZ_ACCOUNT_ID: str | None = None

    DEFAULT_TELEPHONY_PROVIDER: str = "twilio"

    # =========================================================================
    # AWS / STORAGE
    # =========================================================================
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "ap-south-1"  # Mumbai region for India
    S3_BUCKET_NAME: str = "voxai-uploads"

    # =========================================================================
    # OBSERVABILITY
    # =========================================================================
    SENTRY_DSN: str | None = None
    LOG_LEVEL: str = "INFO"

    # =========================================================================
    # FEATURE FLAGS
    # =========================================================================
    # Feature flags let you turn features on/off without deploying new code.
    ENABLE_BILLING: bool = False   # Billing is not part of MVP
    ENABLE_ANALYTICS: bool = True
    ENABLE_RAG: bool = True


@lru_cache
def get_settings() -> Settings:
    """
    Returns the Settings singleton.
    
    @lru_cache means this function's result is cached after the first call.
    Every subsequent call returns the same object — no re-reading .env files.
    
    Usage in FastAPI:
        from app.core.config import get_settings
        settings = get_settings()
        print(settings.DATABASE_URL)
    
    Or as a dependency:
        def my_route(settings: Settings = Depends(get_settings)):
            ...
    """
    return Settings()


# Module-level convenience — import and use directly:
# from app.core.config import settings
settings = get_settings()
