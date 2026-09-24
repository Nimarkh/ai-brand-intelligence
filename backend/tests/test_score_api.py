"""API tests for score calculation and retrieval."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit import Audit
from app.models.enums import FindingSeverity
from app.models.website import SeoFinding, WebsitePage

USER_A = {
    "email": "score-owner-a@example.com",
    "password": "password123",
    "full_name": "Score Owner A",
}
USER_B = {
    "email": "score-owner-b@example.com",
    "password": "password123",
    "full_name": "Score Owner B",
}
BRAND_A = {
    "name": "Northwind Score",
    "website_url": "https://northwind.example",
    "industry": "Retail",
    "country": "United States",
    "target_market": "North America",
    "description": "Outdoor goods",
}
AI_FIELDS = ("ai_visibility_score", "entity_score", "semantic_score")


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


def _add_page(db: Session, audit_id: str, **overrides) -> WebsitePage:
    values = {
        "audit_id": UUID(str(audit_id)),
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


def _add_finding(
    db: Session,
    audit_id: str,
    *,
    category: str,
    severity: FindingSeverity,
    title: str,
    page_id: UUID | None,
) -> SeoFinding:
    row = SeoFinding(
        audit_id=UUID(str(audit_id)),
        page_id=page_id,
        category=category,
        severity=severity,
        title=title,
        description="test",
        recommendation="test",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_calculate_score_unauthenticated(client: TestClient) -> None:
    assert client.post(f"/api/v1/audits/{uuid4()}/calculate-score").status_code == 401


def test_get_score_unauthenticated(client: TestClient) -> None:
    assert client.get(f"/api/v1/audits/{uuid4()}/score").status_code == 401


def test_owner_can_calculate_and_persist_scores(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    page = _add_page(db, audit["id"])
    _add_finding(
        db,
        audit["id"],
        category="TITLE",
        severity=FindingSeverity.HIGH,
        title="Missing page title",
        page_id=page.id,
    )

    response = client.post(f"/api/v1/audits/{audit['id']}/calculate-score")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PROVISIONAL"
    assert body["website_health"]["status"] == "AVAILABLE"
    assert body["seo"]["status"] == "AVAILABLE"
    assert body["overall"]["status"] == "PROVISIONAL"
    assert body["ai_visibility"]["status"] == "UNAVAILABLE"
    assert body["ai_visibility"]["score"] is None
    assert body["entity_strength"]["status"] == "UNAVAILABLE"
    assert body["entity_strength"]["score"] is None
    assert body["findings_count"] == 1
    assert body["affected_pages"] == 1
    assert "provisional" in (body.get("note") or "").lower()

    detail = client.get(f"/api/v1/audits/{audit['id']}")
    assert detail.status_code == 200
    stored = detail.json()
    assert stored["website_score"] is not None
    assert stored["seo_score"] is not None
    assert stored["overall_score"] is not None
    for field in AI_FIELDS:
        assert stored[field] is None


def test_rerun_replaces_scores(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    page = _add_page(db, audit["id"])
    first = client.post(f"/api/v1/audits/{audit['id']}/calculate-score")
    assert first.status_code == 200
    first_overall = float(first.json()["overall"]["score"])

    _add_finding(
        db,
        audit["id"],
        category="TITLE",
        severity=FindingSeverity.HIGH,
        title="Missing page title",
        page_id=page.id,
    )
    second = client.post(f"/api/v1/audits/{audit['id']}/calculate-score")
    assert second.status_code == 200
    assert float(second.json()["overall"]["score"]) < first_overall


def test_get_score_before_calculate_is_unavailable(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _add_page(db, audit["id"])

    response = client.get(f"/api/v1/audits/{audit['id']}/score")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNAVAILABLE"
    assert body["overall"]["score"] is None
    assert body["website_health"]["score"] is None


def test_empty_pages_unavailable_not_zero(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])

    calculated = client.post(f"/api/v1/audits/{audit['id']}/calculate-score")
    assert calculated.status_code == 200
    body = calculated.json()
    assert body["status"] == "UNAVAILABLE"
    assert body["overall"]["score"] is None
    assert body["website_health"]["score"] is None

    detail = client.get(f"/api/v1/audits/{audit['id']}")
    assert detail.json()["overall_score"] is None
    assert detail.json()["website_score"] is None
    assert detail.json()["seo_score"] is None


def test_non_owner_score_returns_404(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _add_page(db, audit["id"])
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-score").status_code == 200

    client.post("/api/v1/auth/logout")
    _register_and_login(client, USER_B)
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-score").status_code == 404
    assert client.get(f"/api/v1/audits/{audit['id']}/score").status_code == 404


def test_nonexistent_score_returns_404(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    missing = uuid4()
    assert client.post(f"/api/v1/audits/{missing}/calculate-score").status_code == 404
    assert client.get(f"/api/v1/audits/{missing}/score").status_code == 404


def test_get_score_after_calculate(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _add_page(db, audit["id"])
    calculated = client.post(f"/api/v1/audits/{audit['id']}/calculate-score")
    fetched = client.get(f"/api/v1/audits/{audit['id']}/score")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "PROVISIONAL"
    assert fetched.json()["overall"]["score"] == calculated.json()["overall"]["score"]
    assert len(fetched.json()["components"]) == 4


def test_calculate_does_not_change_audit_status(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    row = db.get(Audit, UUID(audit["id"]))
    assert row is not None
    from app.models.enums import AuditStatus

    row.status = AuditStatus.COMPLETED
    db.commit()
    _add_page(db, audit["id"])
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-score").status_code == 200
    assert client.get(f"/api/v1/audits/{audit['id']}").json()["status"] == "COMPLETED"
