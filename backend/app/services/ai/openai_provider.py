"""OpenAI SDK adapter. Keep all OpenAI-specific types inside this module."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.services.ai.models import (
    AIConfigurationError,
    AIProviderError,
    AIRequest,
    AIRequestError,
    AIResponse,
    AIUsage,
)

logger = logging.getLogger("app.ai")

OPENAI_PROVIDER_NAME = "openai"


class OpenAIProvider:
    """Calls OpenAI Chat Completions via the official SDK."""

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str,
        timeout_seconds: float,
        client: Any | None = None,
    ) -> None:
        cleaned_key = (api_key or "").strip()
        if not cleaned_key:
            raise AIConfigurationError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
        cleaned_model = (default_model or "").strip()
        if not cleaned_model:
            raise AIConfigurationError("OPENAI_MODEL must not be blank")
        if timeout_seconds <= 0:
            raise AIConfigurationError("OPENAI_TIMEOUT_SECONDS must be greater than 0")

        self._api_key = cleaned_key
        self._default_model = cleaned_model
        self._timeout_seconds = timeout_seconds
        self._client = client

    @property
    def name(self) -> str:
        return OPENAI_PROVIDER_NAME

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - dependency should be installed
            raise AIConfigurationError(
                "The openai package is required when AI_PROVIDER=openai"
            ) from exc
        self._client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout_seconds)
        return self._client

    async def generate(self, request: AIRequest) -> AIResponse:
        if not request.prompt or not request.prompt.strip():
            raise AIRequestError("prompt must not be blank")

        model = (request.model or self._default_model).strip() or self._default_model
        messages: list[dict[str, str]] = []
        if request.system_prompt and request.system_prompt.strip():
            messages.append({"role": "system", "content": request.system_prompt.strip()})
        messages.append({"role": "user", "content": request.prompt.strip()})

        client = self._get_client()
        started = time.perf_counter()
        try:
            completion = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except Exception as exc:
            raise _map_openai_exception(exc) from exc

        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        text = _extract_text(completion)
        usage = _extract_usage(completion)

        logger.info(
            "ai_generate provider=%s model=%s latency_ms=%s",
            OPENAI_PROVIDER_NAME,
            model,
            latency_ms,
        )
        return AIResponse(
            text=text,
            provider=OPENAI_PROVIDER_NAME,
            model=model,
            latency_ms=latency_ms,
            usage=usage,
            metadata={"finish_reason": _finish_reason(completion)},
        )


def _extract_text(completion: Any) -> str:
    try:
        choices = completion.choices
        if not choices:
            raise AIProviderError("OpenAI returned no choices")
        content = choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise AIProviderError("Unexpected OpenAI response shape") from exc
    if content is None:
        return ""
    return str(content)


def _extract_usage(completion: Any) -> AIUsage | None:
    usage = getattr(completion, "usage", None)
    if usage is None:
        return None
    return AIUsage(
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    )


def _finish_reason(completion: Any) -> str | None:
    try:
        return completion.choices[0].finish_reason
    except (AttributeError, IndexError, TypeError):
        return None


def _map_openai_exception(exc: Exception) -> AIProviderError:
    """Map SDK exceptions to normalized errors without leaking secrets."""
    module = type(exc).__module__ or ""
    name = type(exc).__name__
    message = str(exc).strip() or name

    # Avoid echoing authorization material if the SDK ever includes it.
    lowered = message.lower()
    if "api_key" in lowered or "authorization" in lowered or "bearer " in lowered:
        message = name

    if "openai" in module:
        if name in {"AuthenticationError", "PermissionDeniedError"}:
            return AIConfigurationError(f"OpenAI authentication failed ({name})")
        if name in {"BadRequestError", "UnprocessableEntityError", "LengthFinishReasonError"}:
            return AIRequestError(f"OpenAI rejected the request ({name})")
        if name in {"APITimeoutError", "APIConnectionError", "RateLimitError", "APIStatusError", "APIError"}:
            return AIProviderError(f"OpenAI provider error ({name})")

    if name in {"TimeoutError", "CancelledError"}:
        return AIProviderError(f"OpenAI request timed out ({name})")

    return AIProviderError(f"OpenAI provider error ({name})")
