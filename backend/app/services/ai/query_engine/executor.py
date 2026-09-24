"""Execute a single AI query through the configured AIProvider."""

from __future__ import annotations

import logging

from app.services.ai.models import AIProviderError, AIRequest, AIRequestError, AIResponse
from app.services.ai.provider import AIProvider

logger = logging.getLogger("app.ai.query_engine")

DEFAULT_SYSTEM_PROMPT = (
    "You are an AI assistant participating in a brand visibility analysis. "
    "Answer the user's question naturally and factually."
)


class QueryExecutor:
    """Thin wrapper around AIProvider for one query."""

    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    async def execute(self, query_text: str) -> AIResponse:
        request = AIRequest(
            prompt=query_text,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=512,
        )
        try:
            return await self.provider.generate(request)
        except (AIRequestError, AIProviderError):
            logger.warning(
                "ai_query_failed provider=%s",
                getattr(self.provider, "name", "unknown"),
            )
            raise
