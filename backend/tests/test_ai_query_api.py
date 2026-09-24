"""API and integration tests for the AI Query Engine."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_configured_ai_provider
from app.core.config import Settings
from app.main import app
from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.enums import AuditStatus
from app.services.ai.models import AIRequest, AIRequestError, AIResponse as ProviderResponse, AIUsage
from app.services.ai.mock_provider import MOCK_MODEL_NAME, MOCK_PROVIDER_NAME, MockAIProvider

USER_A = {
    "email": "aiq-owner-a@example.com",
    "password": "password123",
    "full_name": "AIQ Owner A",
}
USER_B = {
    "email": "aiq-owner-b@example.com",
    "password": "password123",
    "full_name": "AIQ Owner B",
}
BRAND_A = {
    "name": "Acme Analytics",
    "website_url": "https://acme.example",
    "industry": "marketing analytics",
    "country": "Sweden",
    "target_market": "Nordics",
    "description": "B2B analytics",
}


class BrandMentionProvider:
    """Mock provider that mentions the brand and includes a citation URL."""

    @property
    def name(self) -> str:
        return "brand-mention-mock"

    async def generate(self, request: AIRequest) -> ProviderResponse:
        text = (
            "Rival Labs is popular. Acme Analytics is a strong option. "
            "See https://example.com/source for more."
        )
        return ProviderResponse(
            text=text,
            provider=self.name,
            model="brand-mention-v1",
            latency_ms=12,
            usage=AIUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


class PartialFailProvider:
    """Succeeds for all but the first three prompts (by call order)."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "partial-fail-mock"

    async def generate(self, request: AIRequest) -> ProviderResponse:
        self.calls += 1
        if self.calls <= 3:
            raise AIRequestError("simulated provider failure")
        return await MockAIProvider().generate(request)


def _register_and_login(client: TestClient, user: dict[str, str]) -> None:
    assert client.post("/api/v1/auth/register", json=user).status_code == 201
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": user["email"], "password": user["password"]},
        ).status_code
        == 200
    )


def _create_brand(client: TestClient, payload: dict | None = None) -> dict:
    response = client.post("/api/v1/brands", json=payload or BRAND_A)
    assert response.status_code == 201
    return response.json()


def _create_audit(client: TestClient, brand_id: str) -> dict:
    response = client.post(f"/api/v1/brands/{brand_id}/audits")
    assert response.status_code == 201
    return response.json()


def test_run_ai_queries_unauthenticated(client: TestClient) -> None:
    response = client.post(f"/api/v1/audits/{uuid4()}/ai-queries/run")
    assert response.status_code == 401


def test_list_ai_queries_unauthenticated(client: TestClient) -> None:
    response = client.get(f"/api/v1/audits/{uuid4()}/ai-queries")
    assert response.status_code == 401


def test_get_ai_query_unauthenticated(client: TestClient) -> None:
    response = client.get(f"/api/v1/audits/{uuid4()}/ai-queries/{uuid4()}")
    assert response.status_code == 401


def test_run_ai_queries_success_with_mock(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    prior_status = audit["status"]

    response = client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run")
    assert response.status_code == 200
    body = response.json()
    assert body["audit_id"] == audit["id"]
    assert 12 <= body["queries_generated"] <= 18
    assert body["responses_succeeded"] == body["queries_generated"]
    assert body["responses_failed"] == 0
    assert body["status"] == "COMPLETED"

    query_count = db.scalar(select(func.count()).select_from(AiQuery))
    response_count = db.scalar(select(func.count()).select_from(AiResponse))
    assert query_count == body["queries_generated"]
    assert response_count == body["responses_succeeded"]

    sample = db.scalars(select(AiResponse)).first()
    assert sample is not None
    assert sample.provider == MOCK_PROVIDER_NAME
    assert sample.model == MOCK_MODEL_NAME
    assert sample.latency_ms is not None
    assert sample.semantic_alignment is None

    refreshed = db.get(Audit, UUID(audit["id"]))
    assert refreshed is not None
    assert refreshed.status.value == prior_status or refreshed.status == AuditStatus(prior_status)


def test_run_persists_extractions_with_custom_provider(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])

    app.dependency_overrides[get_configured_ai_provider] = lambda: BrandMentionProvider()
    try:
        response = client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run")
    finally:
        app.dependency_overrides.pop(get_configured_ai_provider, None)

    assert response.status_code == 200
    row = db.scalars(select(AiResponse)).first()
    assert row is not None
    assert row.brand_mentioned is True
    assert row.brand_position == 2
    assert row.citation_found is True
    assert row.semantic_alignment is None
    assert row.provider == "brand-mention-mock"


def test_partial_failure_keeps_queries_without_fake_responses(
    client: TestClient, db: Session
) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    provider = PartialFailProvider()
    app.dependency_overrides[get_configured_ai_provider] = lambda: provider
    try:
        response = client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run")
    finally:
        app.dependency_overrides.pop(get_configured_ai_provider, None)

    assert response.status_code == 200
    body = response.json()
    assert body["queries_generated"] >= 12
    assert body["responses_failed"] == 3
    assert body["responses_succeeded"] == body["queries_generated"] - 3
    assert body["status"] == "COMPLETED"

    assert db.scalar(select(func.count()).select_from(AiQuery)) == body["queries_generated"]
    assert db.scalar(select(func.count()).select_from(AiResponse)) == body["responses_succeeded"]


def test_rerun_replaces_snapshot(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])

    first = client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run")
    assert first.status_code == 200
    first_ids = {str(qid) for qid in db.scalars(select(AiQuery.id)).all()}
    first_count = first.json()["queries_generated"]

    second = client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run")
    assert second.status_code == 200
    second_ids = {str(qid) for qid in db.scalars(select(AiQuery.id)).all()}
    second_count = second.json()["queries_generated"]

    assert first_count == second_count
    assert first_ids.isdisjoint(second_ids)
    assert db.scalar(select(func.count()).select_from(AiQuery)) == second_count
    assert db.scalar(select(func.count()).select_from(AiResponse)) == second_count


def test_list_and_detail_endpoints(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    assert client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run").status_code == 200

    listed = client.get(f"/api/v1/audits/{audit['id']}/ai-queries")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] >= 12
    assert payload["items"][0]["has_response"] is True
    assert "category" in payload["items"][0]

    query_id = payload["items"][0]["id"]
    detail = client.get(f"/api/v1/audits/{audit['id']}/ai-queries/{query_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["response"] is not None
    assert body["response"]["semantic_alignment"] is None
    assert body["response"]["provider"] == MOCK_PROVIDER_NAME


def test_missing_query_returns_404(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    response = client.get(f"/api/v1/audits/{audit['id']}/ai-queries/{uuid4()}")
    assert response.status_code == 404


def test_cross_user_audit_returns_404(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    assert client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run").status_code == 200
    listed = client.get(f"/api/v1/audits/{audit['id']}/ai-queries").json()
    query_id = listed["items"][0]["id"]
    client.post("/api/v1/auth/logout")

    _register_and_login(client, USER_B)
    assert client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run").status_code == 404
    assert client.get(f"/api/v1/audits/{audit['id']}/ai-queries").status_code == 404
    assert client.get(f"/api/v1/audits/{audit['id']}/ai-queries/{query_id}").status_code == 404


def test_query_engine_does_not_import_openai() -> None:
    import app.services.ai.query_engine as package
    import app.services.ai.query_engine.executor as executor
    import app.services.ai.query_engine.generator as generator
    import app.services.ai.query_engine.service as service

    for module in (package, executor, generator, service):
        source = open(module.__file__, encoding="utf-8").read()
        assert "openai" not in source.casefold()
        assert "AsyncOpenAI" not in source
        assert "from openai" not in source


@pytest.mark.asyncio
async def test_settings_ai_query_max_bounds() -> None:
    with pytest.raises(Exception):
        Settings(
            DATABASE_URL="sqlite://",
            REDIS_URL="redis://localhost:6379/0",
            AI_QUERY_MAX_PER_AUDIT=0,
        )
    with pytest.raises(Exception):
        Settings(
            DATABASE_URL="sqlite://",
            REDIS_URL="redis://localhost:6379/0",
            AI_QUERY_MAX_PER_AUDIT=99,
        )
