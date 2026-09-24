"""Deterministic mock AI provider for tests and local development."""

from __future__ import annotations

import hashlib
import logging
import time

from app.services.ai.models import AIRequest, AIRequestError, AIResponse, AIUsage

logger = logging.getLogger("app.ai")

MOCK_PROVIDER_NAME = "mock"
MOCK_MODEL_NAME = "mock-deterministic-v1"
_INTELLIGENCE_MARKER = "You are the intelligence analyst inside this application."
_AUDIT_WORDS = (
    "audit",
    "score",
    "seo",
    "brand",
    "visibility",
    "entity",
    "website",
    "recommend",
    "query",
    "page",
    "fix",
    "opportunit",
)


class MockAIProvider:
    """Never calls an external API. Output is deterministic for a given request."""

    @property
    def name(self) -> str:
        return MOCK_PROVIDER_NAME

    async def generate(self, request: AIRequest) -> AIResponse:
        if not request.prompt or not request.prompt.strip():
            raise AIRequestError("prompt must not be blank")

        started = time.perf_counter()
        model = (request.model or MOCK_MODEL_NAME).strip() or MOCK_MODEL_NAME
        if request.system_prompt and _INTELLIGENCE_MARKER in request.system_prompt:
            text = _intelligence_text(request)
            latency_ms = max(0, int((time.perf_counter() - started) * 1000))
            logger.info(
                "ai_generate provider=%s model=%s latency_ms=%s",
                MOCK_PROVIDER_NAME,
                model,
                latency_ms,
            )
            return AIResponse(
                text=text,
                provider=MOCK_PROVIDER_NAME,
                model=model,
                latency_ms=latency_ms,
                usage=AIUsage(
                    prompt_tokens=max(1, len(request.prompt.split())),
                    completion_tokens=max(1, len(text.split())),
                    total_tokens=max(2, len(request.prompt.split()) + len(text.split())),
                ),
                metadata={"deterministic": True, "intelligence": True},
            )

        digest = hashlib.sha256(
            f"{request.system_prompt or ''}\n{request.prompt}\n{model}\n"
            f"{request.temperature}\n{request.max_tokens}".encode("utf-8")
        ).hexdigest()[:12]

        system_note = "with-system" if request.system_prompt else "no-system"
        text = (
            f"[mock] provider={MOCK_PROVIDER_NAME} model={model} "
            f"mode={system_note} digest={digest} "
            f"chars={len(request.prompt.strip())}"
        )
        # Bound output length similarly to max_tokens heuristic (chars ≈ tokens * 4)
        max_chars = max(32, request.max_tokens * 4)
        if len(text) > max_chars:
            text = text[: max_chars - 1] + "…"

        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        logger.info(
            "ai_generate provider=%s model=%s latency_ms=%s",
            MOCK_PROVIDER_NAME,
            model,
            latency_ms,
        )
        return AIResponse(
            text=text,
            provider=MOCK_PROVIDER_NAME,
            model=model,
            latency_ms=latency_ms,
            usage=AIUsage(
                prompt_tokens=max(1, len(request.prompt.split())),
                completion_tokens=max(1, len(text.split())),
                total_tokens=max(2, len(request.prompt.split()) + len(text.split())),
            ),
            metadata={"deterministic": True, "digest": digest},
        )


def _intelligence_text(request: AIRequest) -> str:
    """Deterministic analyst reply from the prepared question and context header."""
    question = _header_value(request.prompt, "Question")
    intent = _header_value(request.prompt, "Intent") or "GENERAL"
    brand = _header_value(request.prompt, "Brand") or "this brand"
    lowered = question.lower()
    if intent == "GENERAL" and not any(word in lowered for word in _AUDIT_WORDS):
        return (
            "I'm focused on analyzing your brand intelligence data for this audit. "
            "I don't have enough audit context to answer that question."
        )
    readable = intent.replace("_", " ").lower()
    return (
        f"Based on the selected audit, your current {readable} data for {brand} "
        "is drawn only from persisted audit context. "
        "This is an interpretation of stored measurements, not a new measurement. "
        f"Question: {question}"
    )


def _header_value(prompt: str, name: str) -> str:
    prefix = f"{name}:"
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""
