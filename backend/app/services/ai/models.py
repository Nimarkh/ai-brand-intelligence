"""Provider-neutral AI request/response models and errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AIProviderError(Exception):
    """Base error for AI provider failures."""


class AIConfigurationError(AIProviderError):
    """Invalid or missing AI provider configuration."""


class AIRequestError(AIProviderError):
    """The request was invalid or rejected by the provider."""


@dataclass(frozen=True)
class AIUsage:
    """Optional token usage. Provider-neutral."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class AIRequest:
    """Provider-neutral generation request."""

    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    temperature: float = 0.0
    max_tokens: int = 1024


@dataclass(frozen=True)
class AIResponse:
    """Provider-neutral generation response."""

    text: str
    provider: str
    model: str
    latency_ms: int
    usage: AIUsage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
