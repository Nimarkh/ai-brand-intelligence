"""AI provider abstraction tests. No real OpenAI network calls."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.api.deps import get_configured_ai_provider
from app.core.config import Settings
from app.services.ai import (
    AIConfigurationError,
    AIProviderError,
    AIRequest,
    AIRequestError,
    MockAIProvider,
    OpenAIProvider,
    get_ai_provider,
)
from app.services.ai.mock_provider import MOCK_MODEL_NAME, MOCK_PROVIDER_NAME


def _settings(**overrides) -> Settings:
    data = {
        "DATABASE_URL": "sqlite://",
        "REDIS_URL": "redis://localhost:6379/0",
        "AI_PROVIDER": "mock",
        "OPENAI_API_KEY": "",
        "OPENAI_MODEL": "gpt-4o-mini",
        "OPENAI_TIMEOUT_SECONDS": 30.0,
    }
    data.update(overrides)
    return Settings(**data)


@pytest.mark.asyncio
async def test_mock_provider_returns_valid_deterministic_response() -> None:
    provider = MockAIProvider()
    request = AIRequest(prompt="Hello brand", system_prompt="Be brief", temperature=0.0, max_tokens=64)
    first = await provider.generate(request)
    second = await provider.generate(request)

    assert first.provider == MOCK_PROVIDER_NAME
    assert first.model == MOCK_MODEL_NAME
    assert first.text.startswith("[mock]")
    assert first.latency_ms >= 0
    assert first.usage is not None
    assert first.usage.total_tokens is not None
    assert first.metadata.get("deterministic") is True
    assert first.text == second.text
    assert first.metadata["digest"] == second.metadata["digest"]


@pytest.mark.asyncio
async def test_mock_provider_rejects_blank_prompt() -> None:
    provider = MockAIProvider()
    with pytest.raises(AIRequestError):
        await provider.generate(AIRequest(prompt="   "))


@pytest.mark.asyncio
async def test_mock_provider_respects_explicit_model() -> None:
    provider = MockAIProvider()
    response = await provider.generate(AIRequest(prompt="x", model="custom-mock"))
    assert response.model == "custom-mock"


def test_factory_returns_mock_by_default() -> None:
    provider = get_ai_provider(_settings())
    assert isinstance(provider, MockAIProvider)
    assert provider.name == "mock"


def test_factory_returns_openai_when_configured() -> None:
    provider = get_ai_provider(
        _settings(AI_PROVIDER="openai", OPENAI_API_KEY="sk-test-key", OPENAI_MODEL="gpt-4o-mini")
    )
    assert isinstance(provider, OpenAIProvider)
    assert provider.name == "openai"


def test_factory_rejects_unsupported_provider() -> None:
    with pytest.raises(AIConfigurationError, match="Unsupported AI_PROVIDER"):
        get_ai_provider(_settings(AI_PROVIDER="anthropic"))


def test_default_settings_use_mock_without_api_key() -> None:
    cfg = _settings()
    assert cfg.AI_PROVIDER == "mock"
    assert cfg.OPENAI_API_KEY == ""
    provider = get_ai_provider(cfg)
    assert isinstance(provider, MockAIProvider)


def test_openai_provider_requires_api_key() -> None:
    with pytest.raises(AIConfigurationError, match="OPENAI_API_KEY"):
        OpenAIProvider(api_key="", default_model="gpt-4o-mini", timeout_seconds=10)


def test_openai_provider_requires_model() -> None:
    with pytest.raises(AIConfigurationError, match="OPENAI_MODEL"):
        OpenAIProvider(api_key="sk-test", default_model="  ", timeout_seconds=10)


def test_settings_reject_blank_ai_provider() -> None:
    with pytest.raises(ValidationError):
        _settings(AI_PROVIDER="  ")


@pytest.mark.asyncio
async def test_openai_provider_maps_successful_response() -> None:
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="Brand looks strong."),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=4, total_tokens=15),
    )
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=completion)

    provider = OpenAIProvider(
        api_key="sk-test",
        default_model="gpt-4o-mini",
        timeout_seconds=12,
        client=client,
    )
    response = await provider.generate(
        AIRequest(prompt="Summarize", system_prompt="Analyst", temperature=0.2, max_tokens=50)
    )

    assert response.provider == "openai"
    assert response.model == "gpt-4o-mini"
    assert response.text == "Brand looks strong."
    assert response.latency_ms >= 0
    assert response.usage is not None
    assert response.usage.total_tokens == 15
    assert response.metadata.get("finish_reason") == "stop"

    kwargs = client.chat.completions.create.await_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 50
    assert kwargs["messages"][0] == {"role": "system", "content": "Analyst"}
    assert kwargs["messages"][1] == {"role": "user", "content": "Summarize"}


@pytest.mark.asyncio
async def test_openai_provider_uses_request_model_override() -> None:
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"), finish_reason="stop")],
        usage=None,
    )
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=completion)
    provider = OpenAIProvider(
        api_key="sk-test",
        default_model="gpt-4o-mini",
        timeout_seconds=10,
        client=client,
    )
    response = await provider.generate(AIRequest(prompt="Hi", model="gpt-4o"))
    assert response.model == "gpt-4o"
    assert client.chat.completions.create.await_args.kwargs["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_openai_provider_maps_bad_request() -> None:
    class BadRequestError(Exception):
        pass

    BadRequestError.__module__ = "openai"

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=BadRequestError("bad"))
    provider = OpenAIProvider(
        api_key="sk-test",
        default_model="gpt-4o-mini",
        timeout_seconds=10,
        client=client,
    )
    with pytest.raises(AIRequestError, match="OpenAI rejected"):
        await provider.generate(AIRequest(prompt="Hi"))


@pytest.mark.asyncio
async def test_openai_provider_maps_timeout() -> None:
    class APITimeoutError(Exception):
        pass

    APITimeoutError.__module__ = "openai"

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=APITimeoutError("timeout"))
    provider = OpenAIProvider(
        api_key="sk-test",
        default_model="gpt-4o-mini",
        timeout_seconds=10,
        client=client,
    )
    with pytest.raises(AIProviderError, match="OpenAI provider error"):
        await provider.generate(AIRequest(prompt="Hi"))


@pytest.mark.asyncio
async def test_openai_provider_maps_auth_failure() -> None:
    class AuthenticationError(Exception):
        pass

    AuthenticationError.__module__ = "openai"

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=AuthenticationError("api_key invalid"))
    provider = OpenAIProvider(
        api_key="sk-test",
        default_model="gpt-4o-mini",
        timeout_seconds=10,
        client=client,
    )
    with pytest.raises(AIConfigurationError, match="authentication"):
        await provider.generate(AIRequest(prompt="Hi"))


@pytest.mark.asyncio
async def test_openai_provider_rejects_blank_prompt() -> None:
    provider = OpenAIProvider(
        api_key="sk-test",
        default_model="gpt-4o-mini",
        timeout_seconds=10,
        client=MagicMock(),
    )
    with pytest.raises(AIRequestError):
        await provider.generate(AIRequest(prompt=""))


def test_dependency_helper_returns_configured_provider() -> None:
    provider = get_configured_ai_provider()
    assert isinstance(provider, MockAIProvider)


def test_no_public_ai_generate_route_registered() -> None:
    from app.main import app

    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/v1/ai/generate" not in paths
    assert not any(path.endswith("/ai/generate") for path in paths)
