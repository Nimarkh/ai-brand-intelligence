"""Phase 20 — critical full-audit API workflow against the fixture site."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.audits import get_crawler
from app.api.deps import get_configured_ai_provider
from app.api.intelligence import get_intelligence_provider
from app.core.config import settings
from app.main import app
from app.services.ai.mock_provider import MockAIProvider
from app.services.crawler import WebsiteCrawler
from tests.fixtures.test_site import FIXTURE_ORIGIN, build_fixture_crawler

USER = {
    "email": "workflow@example.com",
    "password": "password123",
    "full_name": "Workflow Owner",
}
BRAND = {
    "name": "Fixture Brand",
    "website_url": FIXTURE_ORIGIN,
    "industry": "Outdoor",
    "country": "United States",
    "target_market": "North America",
    "description": "Durable outdoor equipment for independent retailers.",
}


@pytest.fixture()
def fixture_crawler() -> Generator[None, None, None]:
    def override() -> Generator[WebsiteCrawler, None, None]:
        crawler = build_fixture_crawler(max_pages=10, max_depth=2)
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


def test_full_audit_workflow(
    client: TestClient,
    db: Session,
    fixture_crawler: None,
    reports_dir,
) -> None:
    # 1–2. Register + login
    assert client.post("/api/v1/auth/register", json=USER).status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": USER["email"], "password": USER["password"]},
    )
    assert login.status_code == 200

    # 3–4. Create + open brand
    brand = client.post("/api/v1/brands", json=BRAND)
    assert brand.status_code == 201
    brand_id = brand.json()["id"]
    opened = client.get(f"/api/v1/brands/{brand_id}")
    assert opened.status_code == 200
    assert opened.json()["name"] == "Fixture Brand"

    # 5. Create audit
    created = client.post(f"/api/v1/brands/{brand_id}/audits")
    assert created.status_code == 201
    audit_id = created.json()["id"]
    assert created.json()["status"] == "PENDING"

    # 6–7. Crawl fixture site and verify pages
    crawled = client.post(f"/api/v1/audits/{audit_id}/crawl")
    assert crawled.status_code == 200
    assert crawled.json()["status"] == "COMPLETED"
    assert crawled.json()["pages_crawled"] >= 4

    audit = client.get(f"/api/v1/audits/{audit_id}")
    assert audit.status_code == 200
    assert audit.json()["pages_crawled"] >= 4

    # 8–9. SEO analysis + findings
    seo = client.post(f"/api/v1/audits/{audit_id}/analyze-seo")
    assert seo.status_code == 200
    assert seo.json()["findings_count"] >= 1

    findings = client.get(f"/api/v1/audits/{audit_id}/seo-findings")
    assert findings.status_code == 200
    finding_items = findings.json()["items"]
    assert findings.json()["total"] == len(finding_items)
    categories = {item["category"] for item in finding_items}
    # About is missing meta; product has multiple H1 / long title.
    assert categories  # non-empty deterministic findings from fixture pages
    severities = {item["severity"] for item in finding_items}
    assert severities <= {"HIGH", "MEDIUM", "LOW", "INFO"}

    # 10. Deterministic score
    scored = client.post(f"/api/v1/audits/{audit_id}/calculate-score")
    assert scored.status_code == 200
    score_body = scored.json()
    assert score_body["website_health"]["score"] is not None
    assert score_body["seo"]["score"] is not None
    assert score_body["overall"]["score"] is not None
    assert 0 <= float(score_body["website_health"]["score"]) <= 100
    assert 0 <= float(score_body["seo"]["score"]) <= 100
    assert 0 <= float(score_body["overall"]["score"]) <= 100

    # 11. AI queries via MockAIProvider
    ai_run = client.post(f"/api/v1/audits/{audit_id}/ai-queries/run")
    assert ai_run.status_code == 200
    assert ai_run.json()["queries_generated"] == 18
    assert ai_run.json()["responses_succeeded"] >= 1

    queries = client.get(f"/api/v1/audits/{audit_id}/ai-queries")
    assert queries.status_code == 200
    assert queries.json()["total"] == 18

    # 12. AI Visibility
    visibility = client.post(f"/api/v1/audits/{audit_id}/calculate-ai-visibility")
    assert visibility.status_code == 200
    assert visibility.json()["status"] in {"AVAILABLE", "PROVISIONAL"}
    assert visibility.json()["overall_score"] is not None

    # 13. Entity Intelligence
    entity = client.post(f"/api/v1/audits/{audit_id}/calculate-entity")
    assert entity.status_code == 200
    assert entity.json()["status"] in {"AVAILABLE", "UNAVAILABLE"}
    if entity.json()["status"] == "AVAILABLE":
        assert entity.json()["overall_score"] is not None

    # 14. Recommendations
    recs = client.post(f"/api/v1/audits/{audit_id}/calculate-recommendations")
    assert recs.status_code == 200
    assert recs.json()["recommendations_generated"] >= 1

    listed_recs = client.get(f"/api/v1/audits/{audit_id}/recommendations")
    assert listed_recs.status_code == 200
    assert listed_recs.json()["total"] >= 1

    # 15. Dashboard
    dashboard = client.get("/api/v1/dashboard/overview")
    assert dashboard.status_code == 200
    overview = dashboard.json()
    assert overview["workspace"]["brand_count"] >= 1
    assert overview["workspace"]["audit_count"] >= 1

    # 16. Query Explorer
    explorer = client.get("/api/v1/query-explorer", params={"audit_id": audit_id})
    assert explorer.status_code == 200
    explorer_body = explorer.json()
    assert explorer_body["pagination"]["total"] >= 1
    assert len(explorer_body["items"]) >= 1
    assert explorer_body["summary"] is not None
    assert explorer_body["summary"]["total_queries"] >= 1

    # 17. Ask Intelligence (MockAIProvider)
    ask = client.post(
        "/api/v1/intelligence/ask",
        json={
            "audit_id": audit_id,
            "question": "What are the main SEO issues for this brand?",
            "history": [],
        },
    )
    assert ask.status_code == 200
    answer = ask.json()
    assert isinstance(answer.get("answer"), str)
    assert answer["answer"]
    encoded = str(answer)
    assert "OPENAI_API_KEY" not in encoded
    assert "sk-proj-" not in encoded
    assert "password_hash" not in encoded

    # 18–20. Generate + download PDF report
    report = client.post("/api/v1/reports", json={"audit_id": audit_id})
    assert report.status_code == 201
    report_body = report.json()
    assert report_body["status"] == "READY"
    report_id = report_body["id"]

    detail = client.get(f"/api/v1/reports/{report_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "READY"

    download = client.get(f"/api/v1/reports/{report_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/pdf")
    assert download.content.startswith(b"%PDF")
    assert len(download.content) > 500

    pdf_file = reports_dir / f"{report_id}.pdf"
    assert pdf_file.is_file()
    assert pdf_file.read_bytes().startswith(b"%PDF")
