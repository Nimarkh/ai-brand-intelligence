"""API tests for SEO analysis endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import Audit
from app.models.enums import AuditStatus
from app.models.website import SeoFinding, WebsitePage

USER_A = {
    "email": "seo-owner-a@example.com",
    "password": "password123",
    "full_name": "SEO Owner A",
}
USER_B = {
    "email": "seo-owner-b@example.com",
    "password": "password123",
    "full_name": "SEO Owner B",
}
BRAND_A = {
    "name": "Northwind SEO",
    "website_url": "https://northwind.example",
    "industry": "Retail",
    "country": "United States",
    "target_market": "North America",
    "description": "Outdoor goods",
}
SCORE_FIELDS = (
    "overall_score",
    "website_score",
    "seo_score",
    "ai_visibility_score",
    "entity_score",
    "semantic_score",
)


def _register_and_login(client: TestClient, user: dict[str, str]) -> None:
    assert client.post("/api/v1/auth/register", json=user).status_code == 201
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": user["email"], "password": user["password"]},
        ).status_code
        == 200
    )


def _create_brand(client: TestClient) -> dict:
    response = client.post("/api/v1/brands", json=BRAND_A)
    assert response.status_code == 201
    return response.json()


def _create_audit(client: TestClient, brand_id: str) -> dict:
    response = client.post(f"/api/v1/brands/{brand_id}/audits")
    assert response.status_code == 201
    return response.json()


def _add_page(db: Session, audit_id: str | UUID, **overrides) -> WebsitePage:
    values = {
        "audit_id": audit_id if isinstance(audit_id, UUID) else UUID(str(audit_id)),
        "url": "https://northwind.example/page",
        "status_code": 200,
        "title": "A solid page title here",
        "meta_description": (
            "A meta description that is long enough to pass the minimum length heuristic for tests."
        ),
        "canonical_url": "https://northwind.example/page",
        "word_count": 500,
        "h1_count": 1,
        "h2_count": 2,
        "has_schema": True,
        "schema_types": ["Organization"],
        "load_time_ms": 400,
    }
    values.update(overrides)
    page = WebsitePage(**values)
    db.add(page)
    db.commit()
    db.refresh(page)
    return page


def test_analyze_seo_unauthenticated(client: TestClient) -> None:
    audit_id = uuid4()
    response = client.post(f"/api/v1/audits/{audit_id}/analyze-seo")
    assert response.status_code == 401


def test_seo_findings_unauthenticated(client: TestClient) -> None:
    audit_id = uuid4()
    response = client.get(f"/api/v1/audits/{audit_id}/seo-findings")
    assert response.status_code == 401


def test_owner_can_analyze_seo(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _add_page(db, audit["id"], title=None)

    response = client.post(f"/api/v1/audits/{audit['id']}/analyze-seo")
    assert response.status_code == 200
    body = response.json()
    assert body["audit_id"] == audit["id"]
    assert body["status"] == "COMPLETED"
    assert body["findings_count"] >= 1
    assert "items" not in body

    detail = client.get(f"/api/v1/audits/{audit['id']}")
    assert detail.status_code == 200
    for field in SCORE_FIELDS:
        assert detail.json()[field] is None
    assert detail.json()["status"] == "PENDING"


def test_non_owner_analyze_returns_404(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _add_page(db, audit["id"], title=None)

    client.post("/api/v1/auth/logout")
    _register_and_login(client, USER_B)
    response = client.post(f"/api/v1/audits/{audit['id']}/analyze-seo")
    assert response.status_code == 404


def test_nonexistent_audit_analyze_returns_404(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    response = client.post(f"/api/v1/audits/{uuid4()}/analyze-seo")
    assert response.status_code == 404


def test_empty_audit_creates_crawl_finding(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])

    analyzed = client.post(f"/api/v1/audits/{audit['id']}/analyze-seo")
    assert analyzed.status_code == 200
    assert analyzed.json()["findings_count"] == 1

    findings = client.get(f"/api/v1/audits/{audit['id']}/seo-findings")
    assert findings.status_code == 200
    body = findings.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "CRAWL"
    assert body["items"][0]["severity"] == "HIGH"
    assert body["items"][0]["title"] == "No pages were successfully crawled"
    assert body["items"][0]["page_id"] is None


def test_repeated_analysis_does_not_duplicate_findings(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _add_page(db, audit["id"], title=None, meta_description=None)

    first = client.post(f"/api/v1/audits/{audit['id']}/analyze-seo")
    second = client.post(f"/api/v1/audits/{audit['id']}/analyze-seo")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["findings_count"] == second.json()["findings_count"]

    listed = client.get(f"/api/v1/audits/{audit['id']}/seo-findings")
    assert listed.json()["total"] == second.json()["findings_count"]

    count = db.scalar(
        select(func.count()).select_from(SeoFinding).where(SeoFinding.audit_id == UUID(audit["id"]))
    )
    assert count == second.json()["findings_count"]


def test_owner_can_list_seo_findings_ordered(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    page = _add_page(db, audit["id"], title=None, status_code=500, has_schema=False)

    analyzed = client.post(f"/api/v1/audits/{audit['id']}/analyze-seo")
    assert analyzed.status_code == 200

    response = client.get(f"/api/v1/audits/{audit['id']}/seo-findings")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(body["items"])
    assert body["total"] >= 2

    severities = [item["severity"] for item in body["items"]]
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    assert severities == sorted(severities, key=lambda value: rank[value])

    first = body["items"][0]
    assert first["page"]["url"] == page.url
    assert first["page"]["status_code"] == 500
    assert first["recommendation"]
    assert "owner" not in first
    assert "password" not in str(body).lower()


def test_non_owner_findings_return_404(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _add_page(db, audit["id"], title=None)
    assert client.post(f"/api/v1/audits/{audit['id']}/analyze-seo").status_code == 200

    client.post("/api/v1/auth/logout")
    _register_and_login(client, USER_B)
    assert client.get(f"/api/v1/audits/{audit['id']}/seo-findings").status_code == 404


def test_nonexistent_findings_return_404(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    assert client.get(f"/api/v1/audits/{uuid4()}/seo-findings").status_code == 404


def test_analyze_does_not_change_audit_status_or_scores(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])

    row = db.get(Audit, UUID(audit["id"]))
    assert row is not None
    row.status = AuditStatus.COMPLETED
    db.commit()

    _add_page(db, audit["id"], title=None)
    response = client.post(f"/api/v1/audits/{audit['id']}/analyze-seo")
    assert response.status_code == 200

    refreshed = client.get(f"/api/v1/audits/{audit['id']}")
    body = refreshed.json()
    assert body["status"] == "COMPLETED"
    for field in SCORE_FIELDS:
        assert body[field] is None
