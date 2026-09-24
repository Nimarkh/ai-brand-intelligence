"""API tests for Recommendations Engine."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import Audit
from app.models.enums import FindingSeverity
from app.models.recommendation import Recommendation
from app.models.website import SeoFinding, WebsitePage

USER_A = {
    "email": "rec-owner-a@example.com",
    "password": "password123",
    "full_name": "Rec Owner A",
}
USER_B = {
    "email": "rec-owner-b@example.com",
    "password": "password123",
    "full_name": "Rec Owner B",
}
BRAND_A = {
    "name": "Acme Analytics",
    "website_url": "https://acme.example",
    "industry": "marketing analytics",
    "country": "Sweden",
    "target_market": "Nordics",
    "description": "B2B analytics",
}


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


def _seed_page(db: Session, audit_id: str | UUID) -> WebsitePage:
    page = WebsitePage(
        audit_id=audit_id if isinstance(audit_id, UUID) else UUID(str(audit_id)),
        url="https://acme.example/",
        status_code=200,
        title="Acme Analytics",
        meta_description=None,
        canonical_url="https://acme.example/",
        word_count=400,
        h1_count=1,
        h2_count=1,
        has_schema=True,
        schema_types=["Organization"],
        load_time_ms=200,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return page


def _seed_finding(db: Session, audit_id: str | UUID, page_id: UUID | None, title: str) -> None:
    db.add(
        SeoFinding(
            audit_id=audit_id if isinstance(audit_id, UUID) else UUID(str(audit_id)),
            page_id=page_id,
            category="META_DESCRIPTION",
            severity=FindingSeverity.MEDIUM,
            title=title,
            description="test",
            recommendation="fix",
        )
    )
    db.commit()


def test_calculate_unauthenticated(client: TestClient) -> None:
    assert client.post(f"/api/v1/audits/{uuid4()}/calculate-recommendations").status_code == 401


def test_list_unauthenticated(client: TestClient) -> None:
    assert client.get(f"/api/v1/audits/{uuid4()}/recommendations").status_code == 401


def test_calculate_and_list(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    audit_row = db.get(Audit, UUID(audit["id"]))
    assert audit_row is not None
    audit_row.overall_score = Decimal("80")
    audit_row.website_score = Decimal("90")
    audit_row.seo_score = Decimal("70")
    audit_row.ai_visibility_score = Decimal("60")
    audit_row.entity_score = Decimal("55")
    db.commit()

    page = _seed_page(db, audit["id"])
    for _ in range(3):
        _seed_finding(db, audit["id"], page.id, "Missing meta description")

    response = client.post(f"/api/v1/audits/{audit['id']}/calculate-recommendations")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["recommendations_generated"] >= 1
    assert body["high"] + body["medium"] + body["low"] == body["recommendations_generated"]

    db.refresh(audit_row)
    assert audit_row.overall_score == Decimal("80")
    assert audit_row.website_score == Decimal("90")
    assert audit_row.seo_score == Decimal("70")
    assert audit_row.ai_visibility_score == Decimal("60")
    assert audit_row.entity_score == Decimal("55")

    listed = client.get(f"/api/v1/audits/{audit['id']}/recommendations")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == body["recommendations_generated"]
    assert any(item["title"] == "Add missing meta descriptions" for item in payload["items"])
    # Deduped — one meta recommendation despite 3 findings
    meta_items = [i for i in payload["items"] if i["title"] == "Add missing meta descriptions"]
    assert len(meta_items) == 1

    # Idempotent replace
    again = client.post(f"/api/v1/audits/{audit['id']}/calculate-recommendations")
    assert again.status_code == 200
    assert db.scalar(select(func.count()).select_from(Recommendation)) == again.json()[
        "recommendations_generated"
    ]


def test_cross_user_404(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    page = _seed_page(db, audit["id"])
    _seed_finding(db, audit["id"], page.id, "Missing page title")
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-recommendations").status_code == 200
    client.post("/api/v1/auth/logout")

    _register_and_login(client, USER_B)
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-recommendations").status_code == 404
    assert client.get(f"/api/v1/audits/{audit['id']}/recommendations").status_code == 404


def test_seo_rerun_clears_recommendations(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    page = _seed_page(db, audit["id"])
    _seed_finding(db, audit["id"], page.id, "Missing page title")
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-recommendations").status_code == 200
    assert db.scalar(select(func.count()).select_from(Recommendation)) >= 1

    assert client.post(f"/api/v1/audits/{audit['id']}/analyze-seo").status_code == 200
    assert db.scalar(select(func.count()).select_from(Recommendation)) == 0


def test_ai_query_rerun_clears_recommendations(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    page = _seed_page(db, audit["id"])
    _seed_finding(db, audit["id"], page.id, "Missing page title")
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-recommendations").status_code == 200
    assert client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run").status_code == 200
    assert db.scalar(select(func.count()).select_from(Recommendation)) == 0


def test_missing_audit_404(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    assert client.post(f"/api/v1/audits/{uuid4()}/calculate-recommendations").status_code == 404
    assert client.get(f"/api/v1/audits/{uuid4()}/recommendations").status_code == 404
