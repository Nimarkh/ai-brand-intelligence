"""AI provider abstraction. Business logic depends only on this interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.services.ai.models import AIRequest, AIResponse


@runtime_checkable
class AIProvider(Protocol):
    """Common interface for LLM providers."""

    @property
    def name(self) -> str:
        """Short provider identifier (e.g. ``mock``, ``openai``)."""

    async def generate(self, request: AIRequest) -> AIResponse:
        """Generate a completion for ``request``.

        Raises:
            AIConfigurationError: misconfiguration (missing key, etc.)
            AIRequestError: invalid request or provider rejection
            AIProviderError: other provider/API failures
        """
