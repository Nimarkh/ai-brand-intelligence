"""API tests for Entity Intelligence endpoints."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.enums import AiQueryCategory
from app.models.website import WebsitePage

USER_A = {
    "email": "ent-owner-a@example.com",
    "password": "password123",
    "full_name": "Ent Owner A",
}
USER_B = {
    "email": "ent-owner-b@example.com",
    "password": "password123",
    "full_name": "Ent Owner B",
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


def _seed_page(db: Session, audit_id: str | UUID, **overrides) -> None:
    values = {
        "audit_id": audit_id if isinstance(audit_id, UUID) else UUID(str(audit_id)),
        "url": "https://acme.example/",
        "status_code": 200,
        "title": "Acme Analytics Home",
        "meta_description": "Acme Analytics platform",
        "canonical_url": "https://acme.example/",
        "word_count": 400,
        "h1_count": 1,
        "h2_count": 2,
        "has_schema": True,
        "schema_types": ["Organization"],
        "load_time_ms": 200,
    }
    values.update(overrides)
    db.add(WebsitePage(**values))
    db.commit()


def _seed_ai(db: Session, audit_id: str | UUID, *, mentioned: bool = True) -> None:
    query = AiQuery(
        audit_id=audit_id if isinstance(audit_id, UUID) else UUID(str(audit_id)),
        query_text="What is Acme Analytics?",
        category=AiQueryCategory.BRAND,
    )
    db.add(query)
    db.flush()
    db.add(
        AiResponse(
            query_id=query.id,
            provider="mock",
            model="mock-deterministic-v1",
            response_text="Acme Analytics is a marketing platform.",
            brand_mentioned=mentioned,
            brand_position=1 if mentioned else None,
            citation_found=False,
            semantic_alignment=None,
            latency_ms=5,
        )
    )
    db.commit()


def test_calculate_entity_unauthenticated(client: TestClient) -> None:
    assert client.post(f"/api/v1/audits/{uuid4()}/calculate-entity").status_code == 401


def test_get_entity_unauthenticated(client: TestClient) -> None:
    assert client.get(f"/api/v1/audits/{uuid4()}/entity").status_code == 401


def test_calculate_and_get_entity(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    audit_row = db.get(Audit, UUID(audit["id"]))
    assert audit_row is not None
    audit_row.overall_score = Decimal("80.0")
    audit_row.website_score = Decimal("90.0")
    audit_row.seo_score = Decimal("70.0")
    audit_row.ai_visibility_score = Decimal("65.0")
    db.commit()

    _seed_page(db, audit["id"])
    _seed_ai(db, audit["id"])

    first = client.post(f"/api/v1/audits/{audit['id']}/calculate-entity")
    assert first.status_code == 200
    body = first.json()
    assert body["status"] in {"AVAILABLE", "PROVISIONAL"}
    assert body["overall_score"] is not None
    assert body["evidence"]["analyzable_pages"] == 1
    assert body["evidence"]["pages_with_brand_in_title"] == 1
    assert body["components"]["presence"] is not None
    assert any("Knowledge Graph" in note for note in body["notes"])

    db.refresh(audit_row)
    assert audit_row.entity_score == Decimal(str(body["overall_score"]))
    assert audit_row.overall_score == Decimal("80.0")
    assert audit_row.website_score == Decimal("90.0")
    assert audit_row.seo_score == Decimal("70.0")
    assert audit_row.ai_visibility_score == Decimal("65.0")

    second = client.post(f"/api/v1/audits/{audit['id']}/calculate-entity")
    assert second.status_code == 200
    assert second.json()["overall_score"] == body["overall_score"]

    gotten = client.get(f"/api/v1/audits/{audit['id']}/entity")
    assert gotten.status_code == 200
    assert gotten.json()["overall_score"] == body["overall_score"]


def test_get_before_calculate_unavailable(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _seed_page(db, audit["id"])

    response = client.get(f"/api/v1/audits/{audit['id']}/entity")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNAVAILABLE"
    assert body["overall_score"] is None
    assert body["evidence"]["analyzable_pages"] == 1


def test_missing_audit_404(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    assert client.post(f"/api/v1/audits/{uuid4()}/calculate-entity").status_code == 404
    assert client.get(f"/api/v1/audits/{uuid4()}/entity").status_code == 404


def test_cross_user_404(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _seed_page(db, audit["id"])
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-entity").status_code == 200
    client.post("/api/v1/auth/logout")

    _register_and_login(client, USER_B)
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-entity").status_code == 404
    assert client.get(f"/api/v1/audits/{audit['id']}/entity").status_code == 404


def test_ai_query_rerun_clears_entity(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _seed_page(db, audit["id"])
    assert client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run").status_code == 200
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-entity").status_code == 200

    audit_row = db.get(Audit, UUID(audit["id"]))
    assert audit_row is not None
    assert audit_row.entity_score is not None
    prior_overall = audit_row.overall_score
    prior_website = audit_row.website_score
    prior_seo = audit_row.seo_score

    assert client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run").status_code == 200
    db.refresh(audit_row)
    assert audit_row.entity_score is None
    assert audit_row.overall_score == prior_overall
    assert audit_row.website_score == prior_website
    assert audit_row.seo_score == prior_seo


def test_crawl_rerun_clears_entity(client: TestClient, db: Session) -> None:
    from app.api.audits import get_crawler
    from app.main import app
    from tests.test_crawler import _crawler, _html, _page, _site

    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _seed_page(db, audit["id"])
    _seed_ai(db, audit["id"])
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-entity").status_code == 200

    audit_row = db.get(Audit, UUID(audit["id"]))
    assert audit_row is not None
    assert audit_row.entity_score is not None
    prior_overall = audit_row.overall_score
    prior_visibility = audit_row.ai_visibility_score

    handler, _seen = _site({"/": _html(_page("Acme Analytics Home"))})
    crawler = _crawler(handler)

    def override():
        yield crawler

    app.dependency_overrides[get_crawler] = override
    try:
        response = client.post(f"/api/v1/audits/{audit['id']}/crawl")
    finally:
        app.dependency_overrides.pop(get_crawler, None)
        crawler.close()

    assert response.status_code == 200
    db.refresh(audit_row)
    assert audit_row.entity_score is None
    assert audit_row.overall_score == prior_overall
    assert audit_row.ai_visibility_score == prior_visibility
