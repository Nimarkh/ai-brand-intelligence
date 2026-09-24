from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Development fallbacks that must never be accepted when ENVIRONMENT=production.
_UNSAFE_JWT_SECRETS = frozenset(
    {
        "change-me-in-development",
        "change-me-in-development-only!!!",
        "secret",
        "changeme",
        "jwt-secret",
        "your-secret-here",
        "dev-secret",
        "test-secret",
    }
)
_MIN_PRODUCTION_JWT_SECRET_LENGTH = 32
_DEV_JWT_SECRET = "change-me-in-development-only!!!"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql://postgres:postgres@postgres:5432/brand_intelligence"
    REDIS_URL: str = "redis://redis:6379/0"
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api/v1"

    JWT_SECRET: str = _DEV_JWT_SECRET
    JWT_EXPIRE_MINUTES: int = 60
    COOKIE_NAME: str = "ai_brand_access_token"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    CORS_ORIGINS: str = "http://localhost:4200,http://127.0.0.1:4200"

    CRAWLER_MAX_PAGES: int = Field(default=20, ge=1)
    CRAWLER_MAX_DEPTH: int = Field(default=3, ge=0)
    CRAWLER_REQUEST_TIMEOUT_SECONDS: float = Field(default=10, gt=0)
    CRAWLER_DELAY_SECONDS: float = Field(default=0.1, ge=0)
    CRAWLER_MAX_RESPONSE_BYTES: int = Field(default=5_000_000, ge=1)
    CRAWLER_USER_AGENT: str = "AI-Brand-Intelligence-Crawler/1.0"
    CRAWLER_MAX_REDIRECTS: int = Field(default=5, ge=0)

    SEO_TITLE_MAX_LENGTH: int = Field(default=60, ge=1)
    SEO_TITLE_MIN_LENGTH: int = Field(default=10, ge=1)
    SEO_META_DESCRIPTION_MAX_LENGTH: int = Field(default=160, ge=1)
    SEO_META_DESCRIPTION_MIN_LENGTH: int = Field(default=50, ge=1)
    SEO_LOW_WORD_COUNT: int = Field(default=300, ge=0)
    SEO_SLOW_RESPONSE_MS: int = Field(default=2000, ge=1)

    AI_PROVIDER: str = "mock"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)
    # Max AI queries generated/executed per audit run (Phase 11 Query Engine).
    # Templates produce ~18 queries; values above the template count have no effect.
    # Truncation preserves category diversity via round-robin across categories.
    AI_QUERY_MAX_PER_AUDIT: int = Field(default=18, ge=1, le=50)
    # Max recommendations persisted per audit (Phase 14). Highest priority kept first.
    RECOMMENDATIONS_MAX_PER_AUDIT: int = Field(default=20, ge=1, le=100)
    REPORTS_DIR: str = "./data/reports"

    @field_validator("CRAWLER_USER_AGENT")
    @classmethod
    def user_agent_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("CRAWLER_USER_AGENT must not be blank")
        return cleaned

    @field_validator("AI_PROVIDER")
    @classmethod
    def normalize_ai_provider(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("AI_PROVIDER must not be blank")
        return cleaned

    @field_validator("OPENAI_MODEL")
    @classmethod
    def openai_model_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("OPENAI_MODEL must not be blank")
        return cleaned

    @field_validator("COOKIE_SAMESITE")
    @classmethod
    def normalize_samesite(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be one of: lax, strict, none")
        return normalized

    @field_validator("CORS_ORIGINS")
    @classmethod
    def reject_wildcard_cors(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must list at least one explicit origin")
        if any(origin == "*" for origin in origins):
            raise ValueError(
                "CORS_ORIGINS must not include '*' when credentialed cookies are used"
            )
        for origin in origins:
            if "://" not in origin:
                raise ValueError(f"CORS origin must include a scheme: {origin}")
        return value

    @model_validator(mode="after")
    def enforce_production_security(self) -> Self:
        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")

        if self.ENVIRONMENT.strip().lower() != "production":
            return self

        secret = self.JWT_SECRET.strip()
        if (
            not secret
            or secret.lower() in _UNSAFE_JWT_SECRETS
            or len(secret) < _MIN_PRODUCTION_JWT_SECRET_LENGTH
        ):
            raise ValueError(
                "Production requires a strong JWT_SECRET "
                f"(at least {_MIN_PRODUCTION_JWT_SECRET_LENGTH} characters) "
                "and must not use a known development default."
            )
        if not self.COOKIE_SECURE:
            raise ValueError("Production requires COOKIE_SECURE=true")

        db_url = self.DATABASE_URL.strip()
        if not db_url:
            raise ValueError("Production requires DATABASE_URL")
        db_lower = db_url.lower()
        if db_lower.startswith("sqlite"):
            raise ValueError("Production requires PostgreSQL; SQLite is not supported")
        if not (
            db_lower.startswith("postgresql://")
            or db_lower.startswith("postgres://")
            or db_lower.startswith("postgresql+")
        ):
            raise ValueError("Production DATABASE_URL must be a PostgreSQL connection URL")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"


settings = Settings()
