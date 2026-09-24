"""API tests for AI Visibility endpoints."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.enums import AiQueryCategory

USER_A = {
    "email": "vis-owner-a@example.com",
    "password": "password123",
    "full_name": "Vis Owner A",
}
USER_B = {
    "email": "vis-owner-b@example.com",
    "password": "password123",
    "full_name": "Vis Owner B",
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


def _seed_query_response(
    db: Session,
    audit_id: str | UUID,
    *,
    mentioned: bool = True,
    position: int | None = 1,
    citation: bool = True,
    query_text: str = "What is Acme Analytics known for?",
    response_text: str = (
        "Acme Analytics is known for marketing analytics. See https://example.com"
    ),
) -> None:
    query = AiQuery(
        audit_id=audit_id if isinstance(audit_id, UUID) else UUID(str(audit_id)),
        query_text=query_text,
        category=AiQueryCategory.BRAND,
    )
    db.add(query)
    db.flush()
    db.add(
        AiResponse(
            query_id=query.id,
            provider="mock",
            model="mock-deterministic-v1",
            response_text=response_text,
            brand_mentioned=mentioned,
            brand_position=position,
            citation_found=citation,
            semantic_alignment=None,
            latency_ms=5,
        )
    )
    db.commit()


def test_calculate_visibility_unauthenticated(client: TestClient) -> None:
    assert client.post(f"/api/v1/audits/{uuid4()}/calculate-ai-visibility").status_code == 401


def test_get_visibility_unauthenticated(client: TestClient) -> None:
    assert client.get(f"/api/v1/audits/{uuid4()}/ai-visibility").status_code == 401


def test_calculate_and_get_visibility(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    audit_row = db.get(Audit, UUID(audit["id"]))
    assert audit_row is not None
    audit_row.overall_score = Decimal("80.0")
    audit_row.website_score = Decimal("90.0")
    audit_row.seo_score = Decimal("70.0")
    db.commit()

    _seed_query_response(db, audit["id"])
    _seed_query_response(
        db,
        audit["id"],
        mentioned=False,
        position=None,
        citation=False,
        query_text="What companies compete with Acme Analytics?",
        response_text="Several firms compete in marketing analytics.",
    )

    first = client.post(f"/api/v1/audits/{audit['id']}/calculate-ai-visibility")
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "AVAILABLE"
    assert body["overall_score"] is not None
    assert body["total_queries"] == 2
    assert body["successful_responses"] == 2
    assert body["failed_responses"] == 0
    assert body["metrics"]["mention_rate"] == "0.5000" or float(body["metrics"]["mention_rate"]) == 0.5
    assert float(body["components"]["mention"]) == 50.0

    db.refresh(audit_row)
    assert audit_row.ai_visibility_score == Decimal(str(body["overall_score"]))
    assert audit_row.semantic_score is not None
    assert audit_row.overall_score == Decimal("80.0")
    assert audit_row.website_score == Decimal("90.0")
    assert audit_row.seo_score == Decimal("70.0")

    response_row = db.scalars(select(AiResponse)).first()
    assert response_row is not None
    assert response_row.semantic_alignment is not None

    second = client.post(f"/api/v1/audits/{audit['id']}/calculate-ai-visibility")
    assert second.status_code == 200
    assert second.json()["overall_score"] == body["overall_score"]

    gotten = client.get(f"/api/v1/audits/{audit['id']}/ai-visibility")
    assert gotten.status_code == 200
    assert gotten.json()["overall_score"] == body["overall_score"]
    assert gotten.json()["status"] == "AVAILABLE"


def test_unavailable_without_responses(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    db.add(
        AiQuery(
            audit_id=UUID(audit["id"]),
            query_text="What is Acme Analytics?",
            category=AiQueryCategory.BRAND,
        )
    )
    db.commit()

    response = client.post(f"/api/v1/audits/{audit['id']}/calculate-ai-visibility")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNAVAILABLE"
    assert body["overall_score"] is None
    assert body["successful_responses"] == 0


def test_provisional_partial_responses(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _seed_query_response(db, audit["id"])
    db.add(
        AiQuery(
            audit_id=UUID(audit["id"]),
            query_text="Who are alternatives to Acme Analytics?",
            category=AiQueryCategory.COMPETITOR,
        )
    )
    db.commit()

    response = client.post(f"/api/v1/audits/{audit['id']}/calculate-ai-visibility")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PROVISIONAL"
    assert body["successful_responses"] == 1
    assert body["failed_responses"] == 1
    assert body["overall_score"] is not None


def test_get_before_calculate_is_unavailable(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _seed_query_response(db, audit["id"])

    response = client.get(f"/api/v1/audits/{audit['id']}/ai-visibility")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNAVAILABLE"
    assert body["overall_score"] is None
    assert body["successful_responses"] == 1


def test_phase11_rerun_clears_visibility(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    assert client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run").status_code == 200
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-ai-visibility").status_code == 200

    audit_row = db.get(Audit, UUID(audit["id"]))
    assert audit_row is not None
    assert audit_row.ai_visibility_score is not None
    prior_overall = audit_row.overall_score
    prior_website = audit_row.website_score
    prior_seo = audit_row.seo_score

    assert client.post(f"/api/v1/audits/{audit['id']}/ai-queries/run").status_code == 200
    db.refresh(audit_row)
    assert audit_row.ai_visibility_score is None
    assert audit_row.semantic_score is None
    assert audit_row.overall_score == prior_overall
    assert audit_row.website_score == prior_website
    assert audit_row.seo_score == prior_seo


def test_cross_user_visibility_404(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _create_audit(client, brand["id"])
    _seed_query_response(db, audit["id"])
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-ai-visibility").status_code == 200
    client.post("/api/v1/auth/logout")

    _register_and_login(client, USER_B)
    assert client.post(f"/api/v1/audits/{audit['id']}/calculate-ai-visibility").status_code == 404
    assert client.get(f"/api/v1/audits/{audit['id']}/ai-visibility").status_code == 404
