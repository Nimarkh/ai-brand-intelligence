"""Phase 15 — Main Intelligence Dashboard API tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.enums import (
    AiQueryCategory,
    AuditStatus,
    FindingSeverity,
    RecommendationPriority,
)
from app.models.recommendation import Recommendation
from app.models.website import SeoFinding, WebsitePage

USER_A = {
    "email": "dash-a@example.com",
    "password": "password123",
    "full_name": "Owner A",
}
USER_B = {
    "email": "dash-b@example.com",
    "password": "password123",
    "full_name": "Owner B",
}

BRAND_A = {
    "name": "Northwind",
    "website_url": "https://northwind.example",
    "industry": "Retail",
    "country": "United States",
    "target_market": "North America",
    "description": "Outdoor goods",
}
BRAND_B = {
    "name": "Contoso",
    "website_url": "https://contoso.example",
    "industry": "Software",
    "country": "Germany",
    "target_market": "Europe",
}

OVERVIEW_TOP_KEYS = {
    "workspace",
    "selected_audit",
    "scores",
    "snapshot",
    "insights",
    "recommendations",
    "freshness",
    "brands",
    "selection_rule",
}
SCORE_KEYS = {"overall", "website", "seo", "ai_visibility", "entity"}


def _register_and_login(client: TestClient, user: dict[str, str]) -> None:
    assert client.post("/api/v1/auth/register", json=user).status_code == 201
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": user["email"], "password": user["password"]},
        ).status_code
        == 200
    )


def _create_brand(client: TestClient, payload: dict[str, str]) -> dict:
    response = client.post("/api/v1/brands", json=payload)
    assert response.status_code == 201
    return response.json()


def _add_audit(
    db: Session,
    brand_id: str,
    *,
    status: AuditStatus,
    overall: Decimal | None = None,
    website: Decimal | None = None,
    seo: Decimal | None = None,
    visibility: Decimal | None = None,
    entity: Decimal | None = None,
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> Audit:
    audit = Audit(
        brand_id=UUID(brand_id),
        status=status,
        overall_score=overall,
        website_score=website,
        seo_score=seo,
        ai_visibility_score=visibility,
        entity_score=entity,
        created_at=created_at or datetime.now(timezone.utc),
        completed_at=completed_at,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def _overview(client: TestClient, **params) -> dict:
    response = client.get("/api/v1/dashboard/overview", params=params or None)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == OVERVIEW_TOP_KEYS
    encoded = json.dumps(body)
    assert "owner_id" not in encoded
    assert "password" not in encoded
    assert set(body["scores"].keys()) == SCORE_KEYS
    return body


def test_unauthenticated_dashboard_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_empty_workspace(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    body = _overview(client)

    assert body["workspace"] == {
        "brand_count": 0,
        "audit_count": 0,
        "completed_audit_count": 0,
    }
    assert body["selected_audit"] is None
    assert body["scores"]["overall"]["score"] is None
    assert body["scores"]["overall"]["status"] == "UNAVAILABLE"
    assert body["scores"]["website"]["score"] is None
    assert body["scores"]["website"]["status"] == "UNAVAILABLE"
    assert body["scores"]["website"]["explanation"] == "Not calculated yet"
    assert body["scores"]["ai_visibility"]["score"] is None
    assert body["scores"]["entity"]["score"] is None
    assert body["insights"] == []
    assert body["recommendations"] == []
    assert body["brands"] == []


def test_brands_without_audits(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    body = _overview(client)

    assert body["workspace"]["brand_count"] == 1
    assert body["workspace"]["audit_count"] == 0
    assert body["selected_audit"] is None
    assert body["scores"]["overall"]["status"] == "UNAVAILABLE"
    assert body["brands"] == [{"id": brand["id"], "name": "Northwind"}]
    assert all(card["score"] is None for card in body["scores"].values())


def test_latest_completed_audit_wins(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    moment = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

    older = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        overall=Decimal("50.00"),
        website=Decimal("55.00"),
        seo=Decimal("45.00"),
        created_at=moment,
        completed_at=moment,
    )
    newer = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        overall=Decimal("80.00"),
        website=Decimal("82.00"),
        seo=Decimal("78.00"),
        created_at=moment + timedelta(days=2),
        completed_at=moment + timedelta(days=2),
    )
    _add_audit(
        db,
        brand["id"],
        status=AuditStatus.PENDING,
        overall=Decimal("99.00"),
        website=Decimal("99.00"),
        seo=Decimal("99.00"),
        created_at=moment + timedelta(days=3),
    )

    body = _overview(client)
    assert body["selected_audit"]["id"] == str(newer.id)
    assert body["selected_audit"]["id"] != str(older.id)
    assert body["scores"]["overall"]["score"] == 80.0
    assert body["scores"]["website"]["score"] == 82.0
    assert body["scores"]["seo"]["score"] == 78.0
    assert body["scores"]["overall"]["status"] == "PROVISIONAL"


def test_fallback_to_newest_incomplete_audit(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    moment = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)

    _add_audit(
        db,
        brand["id"],
        status=AuditStatus.FAILED,
        created_at=moment,
    )
    newest = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.RUNNING,
        created_at=moment + timedelta(hours=2),
    )

    body = _overview(client)
    assert body["selected_audit"]["id"] == str(newest.id)
    assert body["selected_audit"]["status"] == "RUNNING"
    assert body["scores"]["overall"]["status"] == "UNAVAILABLE"
    assert body["scores"]["website"]["score"] is None


def test_partial_audit_scores_and_provisional_overall(
    client: TestClient, db: Session
) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    moment = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        overall=Decimal("70.00"),
        website=Decimal("72.00"),
        seo=Decimal("68.00"),
        visibility=None,
        entity=None,
        created_at=moment,
        completed_at=moment,
    )
    db.add(
        WebsitePage(
            audit_id=audit.id,
            url="https://northwind.example/",
            status_code=200,
            title="Home",
            meta_description=None,
            has_schema=False,
        )
    )
    db.commit()

    body = _overview(client)
    scores = body["scores"]
    assert scores["website"]["status"] == "AVAILABLE"
    assert scores["website"]["score"] == 72.0
    assert scores["seo"]["status"] == "AVAILABLE"
    assert scores["ai_visibility"]["status"] == "UNAVAILABLE"
    assert scores["ai_visibility"]["score"] is None
    assert scores["ai_visibility"]["explanation"] == "Not calculated yet"
    assert scores["entity"]["status"] == "UNAVAILABLE"
    assert scores["entity"]["score"] is None
    assert scores["overall"]["status"] == "PROVISIONAL"
    assert scores["overall"]["score"] == 70.0
    assert "AI Visibility and Entity Strength" in scores["overall"]["explanation"]
    assert body["snapshot"]["pages_crawled"] == 1


def test_ai_available_entity_unavailable_stays_provisional(
    client: TestClient, db: Session
) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    moment = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        overall=Decimal("71.00"),
        website=Decimal("70.00"),
        seo=Decimal("72.00"),
        visibility=Decimal("64.50"),
        entity=None,
        created_at=moment,
        completed_at=moment,
    )

    body = _overview(client)
    assert body["scores"]["ai_visibility"]["score"] == 64.5
    assert body["scores"]["ai_visibility"]["status"] == "AVAILABLE"
    assert body["scores"]["entity"]["score"] is None
    assert body["scores"]["overall"]["status"] == "PROVISIONAL"


def test_all_layers_available_overall_status(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    moment = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        overall=Decimal("68.40"),
        website=Decimal("72.10"),
        seo=Decimal("69.20"),
        visibility=Decimal("64.50"),
        entity=Decimal("58.00"),
        created_at=moment,
        completed_at=moment,
    )

    body = _overview(client)
    assert body["selected_audit"]["id"] == str(audit.id)
    assert body["scores"]["overall"]["score"] == 68.4
    assert body["scores"]["overall"]["status"] == "AVAILABLE"
    assert body["scores"]["entity"]["score"] == 58.0
    # Stored overall is not recalculated even when all layers exist.
    assert body["scores"]["overall"]["score"] == float(audit.overall_score)


def test_null_scores_never_become_zero(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    moment = datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc)
    _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=moment,
        completed_at=moment,
    )

    body = _overview(client)
    for key in SCORE_KEYS:
        assert body["scores"][key]["score"] is None
        assert body["scores"][key]["score"] != 0
        assert body["scores"][key]["status"] in {"UNAVAILABLE", "PROVISIONAL"}


def test_insights_and_recommendation_preview(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    moment = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        overall=Decimal("70.00"),
        website=Decimal("70.00"),
        seo=Decimal("70.00"),
        visibility=Decimal("50.00"),
        created_at=moment,
        completed_at=moment,
    )

    for index in range(3):
        page = WebsitePage(
            audit_id=audit.id,
            url=f"https://northwind.example/p{index}",
            status_code=200,
            title=f"Page {index}",
            has_schema=index == 0,
        )
        db.add(page)
        db.flush()
        if index < 2:
            db.add(
                SeoFinding(
                    audit_id=audit.id,
                    page_id=page.id,
                    category="META_DESCRIPTION",
                    severity=FindingSeverity.HIGH,
                    title="Missing meta description",
                    description="Missing",
                )
            )

    queries = []
    for index in range(3):
        query = AiQuery(
            audit_id=audit.id,
            query_text=f"Query {index}",
            category=AiQueryCategory.BRAND,
        )
        db.add(query)
        db.flush()
        queries.append(query)
        db.add(
            AiResponse(
                query_id=query.id,
                provider="mock",
                model="mock",
                response_text=f"Response {index}",
                brand_mentioned=index < 2,
            )
        )

    db.add_all(
        [
            Recommendation(
                audit_id=audit.id,
                title="Fix meta descriptions",
                description="Add meta",
                category="SEO",
                priority=RecommendationPriority.HIGH,
                impact_score=Decimal("90.00"),
                effort_score=Decimal("20.00"),
            ),
            Recommendation(
                audit_id=audit.id,
                title="Improve AI mentions",
                description="Content",
                category="AI_VISIBILITY",
                priority=RecommendationPriority.HIGH,
                impact_score=Decimal("80.00"),
                effort_score=Decimal("40.00"),
            ),
            Recommendation(
                audit_id=audit.id,
                title="Add schema",
                description="JSON-LD",
                category="STRUCTURED_DATA",
                priority=RecommendationPriority.MEDIUM,
                impact_score=Decimal("70.00"),
                effort_score=Decimal("30.00"),
            ),
            Recommendation(
                audit_id=audit.id,
                title="Low item",
                description="Later",
                category="CONTENT",
                priority=RecommendationPriority.LOW,
                impact_score=Decimal("10.00"),
                effort_score=Decimal("10.00"),
            ),
        ]
    )
    db.commit()

    body = _overview(client)
    assert body["snapshot"]["pages_crawled"] == 3
    assert body["snapshot"]["seo_findings"] == 2
    assert body["snapshot"]["high_severity_findings"] == 2
    assert body["snapshot"]["ai_queries"] == 3
    assert body["snapshot"]["ai_successful_responses"] == 3
    assert body["snapshot"]["ai_response_coverage"] == 1.0
    assert body["snapshot"]["recommendations_total"] == 4
    assert body["snapshot"]["recommendations_high"] == 2

    texts = [item["text"] for item in body["insights"]]
    assert any("2 of 3 analyzed AI responses mentioned the brand." in text for text in texts)
    assert any("high-severity" in text for text in texts)
    assert any("Structured identity signals are present on 1 of 3" in text for text in texts)
    assert any("2 high-priority recommendations are available." in text for text in texts)
    assert 2 <= len(body["insights"]) <= 4

    recs = body["recommendations"]
    assert len(recs) == 4
    assert recs[0]["title"] == "Fix meta descriptions"
    assert recs[0]["priority"] == "HIGH"
    assert recs[1]["title"] == "Improve AI mentions"
    assert recs[2]["priority"] == "MEDIUM"
    assert body["freshness"]["last_website_crawl"] is not None
    assert body["freshness"]["last_seo_analysis"] is not None
    assert body["freshness"]["last_ai_analysis"] is not None
    assert body["freshness"]["last_recommendations_calculation"] is not None


def test_recommendation_preview_limited_to_five(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    moment = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        overall=Decimal("60.00"),
        website=Decimal("60.00"),
        seo=Decimal("60.00"),
        created_at=moment,
        completed_at=moment,
    )
    for index in range(7):
        db.add(
            Recommendation(
                audit_id=audit.id,
                title=f"Rec {index}",
                description="x",
                category="SEO",
                priority=RecommendationPriority.MEDIUM,
                impact_score=Decimal(str(90 - index)),
                effort_score=Decimal("10.00"),
            )
        )
    db.commit()

    body = _overview(client)
    assert len(body["recommendations"]) == 5
    assert body["snapshot"]["recommendations_total"] == 7
    assert [item["title"] for item in body["recommendations"]] == [
        "Rec 0",
        "Rec 1",
        "Rec 2",
        "Rec 3",
        "Rec 4",
    ]


def test_ownership_isolation(client: TestClient, db: Session) -> None:
    from fastapi.testclient import TestClient as Client
    from app.main import app

    _register_and_login(client, USER_A)
    brand_a = _create_brand(client, BRAND_A)
    moment = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)
    audit_a = _add_audit(
        db,
        brand_a["id"],
        status=AuditStatus.COMPLETED,
        overall=Decimal("80.00"),
        website=Decimal("80.00"),
        seo=Decimal("80.00"),
        visibility=Decimal("70.00"),
        created_at=moment,
        completed_at=moment,
    )

    with Client(app) as other:
        _register_and_login(other, USER_B)
        brand_b = _create_brand(other, BRAND_B)
        audit_b = _add_audit(
            db,
            brand_b["id"],
            status=AuditStatus.COMPLETED,
            overall=Decimal("20.00"),
            website=Decimal("20.00"),
            seo=Decimal("20.00"),
            visibility=Decimal("15.00"),
            created_at=moment + timedelta(hours=1),
            completed_at=moment + timedelta(hours=1),
        )
        other_body = _overview(other)
        leaked = other.get(
            "/api/v1/dashboard/overview",
            params={"brand_id": brand_a["id"], "user_id": brand_a["id"]},
        )

    body = _overview(client)
    assert body["selected_audit"]["id"] == str(audit_a.id)
    assert body["scores"]["overall"]["score"] == 80.0
    assert body["brands"][0]["name"] == "Northwind"
    assert other_body["selected_audit"]["id"] == str(audit_b.id)
    assert other_body["scores"]["overall"]["score"] == 20.0
    assert leaked.status_code == 200
    leaked_body = leaked.json()
    assert leaked_body["selected_audit"]["id"] == str(audit_b.id)
    assert leaked_body["scores"]["overall"]["score"] == 20.0


def test_brand_filter_uses_owned_brand_only(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    first = _create_brand(client, BRAND_A)
    second = _create_brand(
        client, {**BRAND_A, "name": "Harbor", "website_url": "https://harbor.example"}
    )
    moment = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
    audit_first = _add_audit(
        db,
        first["id"],
        status=AuditStatus.COMPLETED,
        overall=Decimal("40.00"),
        website=Decimal("40.00"),
        seo=Decimal("40.00"),
        created_at=moment,
        completed_at=moment,
    )
    audit_second = _add_audit(
        db,
        second["id"],
        status=AuditStatus.COMPLETED,
        overall=Decimal("90.00"),
        website=Decimal("90.00"),
        seo=Decimal("90.00"),
        created_at=moment + timedelta(days=1),
        completed_at=moment + timedelta(days=1),
    )

    all_brands = _overview(client)
    assert all_brands["selected_audit"]["id"] == str(audit_second.id)

    filtered = _overview(client, brand_id=first["id"])
    assert filtered["selected_audit"]["id"] == str(audit_first.id)
    assert filtered["workspace"]["brand_count"] == 1
    assert filtered["workspace"]["audit_count"] == 1


def test_openapi_documents_dashboard_overview(client: TestClient) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    body = schema.json()
    assert "get" in body["paths"]["/api/v1/dashboard/overview"]
    models = body["components"]["schemas"]
    for name in (
        "DashboardOverview",
        "DashboardWorkspace",
        "DashboardScores",
        "DashboardScoreCard",
        "DashboardInsight",
        "DashboardRecommendationPreview",
    ):
        assert name in models
        assert "owner_id" not in models[name].get("properties", {})
        assert "password_hash" not in models[name].get("properties", {})
