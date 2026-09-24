"""Build the configured AI provider. Prefer this over constructing providers ad hoc."""

from __future__ import annotations

from app.core.config import Settings, settings
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai.models import AIConfigurationError
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.provider import AIProvider

SUPPORTED_PROVIDERS = frozenset({"mock", "openai"})


def get_ai_provider(config: Settings | None = None) -> AIProvider:
    """Return a new provider instance for the active configuration.

    Pass ``config`` in tests to avoid mutating global settings. Does not cache
    a process-wide singleton so tests can inject alternatives freely.
    """
    cfg = config or settings
    name = (cfg.AI_PROVIDER or "").strip().lower()
    if name not in SUPPORTED_PROVIDERS:
        raise AIConfigurationError(
            f"Unsupported AI_PROVIDER={cfg.AI_PROVIDER!r}. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
        )
    if name == "mock":
        return MockAIProvider()
    return OpenAIProvider(
        api_key=cfg.OPENAI_API_KEY,
        default_model=cfg.OPENAI_MODEL,
        timeout_seconds=cfg.OPENAI_TIMEOUT_SECONDS,
    )
