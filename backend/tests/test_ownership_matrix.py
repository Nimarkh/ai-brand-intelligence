"""Phase 20 — ownership isolation matrix (User A resources hidden from User B)."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.audits import get_crawler
from app.api.deps import get_configured_ai_provider
from app.api.intelligence import get_intelligence_provider
from app.core.config import settings
from app.main import app
from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.enums import AiQueryCategory, AuditStatus, FindingSeverity, RecommendationPriority, ReportStatus
from app.models.recommendation import Recommendation
from app.models.report import Report
from app.models.website import SeoFinding, WebsitePage
from app.services.ai.mock_provider import MockAIProvider
from app.services.crawler import WebsiteCrawler
from tests.fixtures.test_site import FIXTURE_ORIGIN, build_fixture_crawler

USER_A = {
    "email": "owner-matrix-a@example.com",
    "password": "password123",
    "full_name": "Owner A",
}
USER_B = {
    "email": "owner-matrix-b@example.com",
    "password": "password123",
    "full_name": "Owner B",
}
BRAND_A = {
    "name": "Secret Brand Alpha",
    "website_url": FIXTURE_ORIGIN,
    "industry": "Outdoor",
    "country": "United States",
    "target_market": "North America",
    "description": "Must stay hidden from User B.",
}
MOMENT = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def fixture_crawler() -> Generator[None, None, None]:
    def override() -> Generator[WebsiteCrawler, None, None]:
        crawler = build_fixture_crawler(max_pages=5, max_depth=1)
        try:
            yield crawler
        finally:
            crawler.close()

    app.dependency_overrides[get_crawler] = override
    app.dependency_overrides[get_configured_ai_provider] = lambda: MockAIProvider()
    app.dependency_overrides[get_intelligence_provider] = lambda: MockAIProvider()
    yield
    app.dependency_overrides.pop(get_crawler, None)
    app.dependency_overrides.pop(get_configured_ai_provider, None)
    app.dependency_overrides.pop(get_intelligence_provider, None)


@pytest.fixture()
def reports_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    folder = tmp_path / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "REPORTS_DIR", str(folder))
    return folder


def _register_and_login(client: TestClient, user: dict[str, str]) -> None:
    assert client.post("/api/v1/auth/register", json=user).status_code == 201
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": user["email"], "password": user["password"]},
        ).status_code
        == 200
    )


def _assert_hidden(response, *, secret: str = "Secret Brand Alpha") -> None:
    assert response.status_code == 404
    detail = response.json().get("detail")
    assert detail in {"Not found.", "Brand not found."}
    assert secret not in response.text


def test_user_b_cannot_access_user_a_resources(
    client: TestClient,
    db: Session,
    fixture_crawler: None,
    reports_dir,
) -> None:
    _register_and_login(client, USER_A)
    brand = client.post("/api/v1/brands", json=BRAND_A).json()
    brand_id = brand["id"]
    audit_id = client.post(f"/api/v1/brands/{brand_id}/audits").json()["id"]

    assert client.post(f"/api/v1/audits/{audit_id}/crawl").status_code == 200
    assert client.post(f"/api/v1/audits/{audit_id}/analyze-seo").status_code == 200
    assert client.post(f"/api/v1/audits/{audit_id}/calculate-score").status_code == 200
    assert client.post(f"/api/v1/audits/{audit_id}/ai-queries/run").status_code == 200
    assert client.post(f"/api/v1/audits/{audit_id}/calculate-ai-visibility").status_code == 200
    assert client.post(f"/api/v1/audits/{audit_id}/calculate-entity").status_code == 200
    assert client.post(f"/api/v1/audits/{audit_id}/calculate-recommendations").status_code == 200

    report = client.post("/api/v1/reports", json={"audit_id": audit_id})
    assert report.status_code == 201
    report_id = report.json()["id"]

    queries = client.get(f"/api/v1/audits/{audit_id}/ai-queries").json()["items"]
    assert queries
    query_id = queries[0]["id"]

    client.post("/api/v1/auth/logout")
    _register_and_login(client, USER_B)

    hidden_gets = (
        client.get(f"/api/v1/brands/{brand_id}"),
        client.get(f"/api/v1/brands/{brand_id}/audits"),
        client.get(f"/api/v1/audits/{audit_id}"),
        client.get(f"/api/v1/audits/{audit_id}/seo-findings"),
        client.get(f"/api/v1/audits/{audit_id}/score"),
        client.get(f"/api/v1/audits/{audit_id}/ai-queries"),
        client.get(f"/api/v1/audits/{audit_id}/ai-queries/{query_id}"),
        client.get(f"/api/v1/audits/{audit_id}/ai-visibility"),
        client.get(f"/api/v1/audits/{audit_id}/entity"),
        client.get(f"/api/v1/audits/{audit_id}/recommendations"),
        client.get("/api/v1/query-explorer", params={"audit_id": audit_id}),
        client.get(f"/api/v1/reports/{report_id}"),
        client.get(f"/api/v1/reports/{report_id}/download"),
    )
    for response in hidden_gets:
        _assert_hidden(response)

    hidden_posts = (
        client.post(f"/api/v1/brands/{brand_id}/audits"),
        client.post(f"/api/v1/audits/{audit_id}/crawl"),
        client.post(f"/api/v1/audits/{audit_id}/analyze-seo"),
        client.post(f"/api/v1/audits/{audit_id}/calculate-score"),
        client.post(f"/api/v1/audits/{audit_id}/ai-queries/run"),
        client.post(f"/api/v1/audits/{audit_id}/calculate-ai-visibility"),
        client.post(f"/api/v1/audits/{audit_id}/calculate-entity"),
        client.post(f"/api/v1/audits/{audit_id}/calculate-recommendations"),
        client.post("/api/v1/reports", json={"audit_id": audit_id}),
        client.post(
            "/api/v1/intelligence/ask",
            json={"audit_id": audit_id, "question": "Summarize this audit.", "history": []},
        ),
    )
    for response in hidden_posts:
        _assert_hidden(response)

    # Dashboard for B must not surface A's brand name or audit id.
    overview = client.get("/api/v1/dashboard/overview")
    assert overview.status_code == 200
    body = overview.json()
    encoded = str(body)
    assert "Secret Brand Alpha" not in encoded
    assert audit_id not in encoded
    assert brand_id not in encoded
    assert report_id not in encoded


def test_seeded_foreign_resources_stay_404(client: TestClient, db: Session, reports_dir) -> None:
    """Ownership checks hold even when rows exist without crawling."""
    _register_and_login(client, USER_A)
    brand = client.post(
        "/api/v1/brands",
        json={**BRAND_A, "name": "Seeded Secret", "website_url": "https://seeded.example"},
    ).json()
    audit = Audit(
        brand_id=UUID(brand["id"]),
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
        overall_score=Decimal("71.00"),
        website_score=Decimal("80.00"),
        seo_score=Decimal("60.00"),
        ai_visibility_score=Decimal("50.00"),
        entity_score=Decimal("55.00"),
        semantic_score=Decimal("40.00"),
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    page = WebsitePage(audit_id=audit.id, url="https://seeded.example/", title="Seeded Secret", status_code=200)
    db.add(page)
    db.commit()
    db.refresh(page)
    db.add(
        SeoFinding(
            audit_id=audit.id,
            page_id=page.id,
            category="Metadata",
            severity=FindingSeverity.HIGH,
            title="Missing title",
            description="Title is missing.",
            recommendation="Add a title",
        )
    )
    query = AiQuery(
        audit_id=audit.id,
        category=AiQueryCategory.BRAND,
        query_text="Who is Seeded Secret?",
    )
    db.add(query)
    db.commit()
    db.refresh(query)
    db.add(
        AiResponse(
            query_id=query.id,
            response_text="Seeded Secret is known.",
            brand_mentioned=True,
            provider="mock",
            model="mock",
        )
    )
    db.add(
        Recommendation(
            audit_id=audit.id,
            category="SEO",
            title="Fix title",
            description="Missing title hurts SEO.",
            priority=RecommendationPriority.HIGH,
            impact_score=Decimal("80.00"),
            effort_score=Decimal("20.00"),
        )
    )
    report = Report(
        audit_id=audit.id,
        status=ReportStatus.READY,
        title="Seeded Secret report",
        file_path=None,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    report.file_path = f"{report.id}.pdf"
    db.commit()
    (reports_dir / f"{report.id}.pdf").write_bytes(b"%PDF-1.4 seeded")

    client.post("/api/v1/auth/logout")
    _register_and_login(client, USER_B)

    for response in (
        client.get(f"/api/v1/brands/{brand['id']}"),
        client.get(f"/api/v1/audits/{audit.id}"),
        client.get(f"/api/v1/audits/{audit.id}/seo-findings"),
        client.get(f"/api/v1/audits/{audit.id}/ai-queries"),
        client.get(f"/api/v1/audits/{audit.id}/ai-queries/{query.id}"),
        client.get(f"/api/v1/audits/{audit.id}/ai-visibility"),
        client.get(f"/api/v1/audits/{audit.id}/entity"),
        client.get(f"/api/v1/audits/{audit.id}/recommendations"),
        client.get("/api/v1/query-explorer", params={"audit_id": str(audit.id)}),
        client.get(f"/api/v1/reports/{report.id}"),
        client.get(f"/api/v1/reports/{report.id}/download"),
        client.post(
            "/api/v1/intelligence/ask",
            json={"audit_id": str(audit.id), "question": "Summarize.", "history": []},
        ),
    ):
        assert response.status_code == 404
        assert "Seeded Secret" not in response.text
        assert b"%PDF" not in response.content
