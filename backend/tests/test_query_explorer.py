"""Phase 16 — Query Explorer API tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.enums import AiQueryCategory, AuditStatus

USER_A = {
    "email": "explorer-a@example.com",
    "password": "password123",
    "full_name": "Owner A",
}
USER_B = {
    "email": "explorer-b@example.com",
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

VIEW_KEYS = {"audit", "audits", "summary", "items", "pagination"}
MOMENT = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


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
    created_at: datetime,
    completed_at: datetime | None = None,
) -> Audit:
    audit = Audit(
        brand_id=UUID(brand_id),
        status=status,
        created_at=created_at,
        completed_at=completed_at,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def _add_query(
    db: Session,
    audit_id: UUID,
    *,
    text: str,
    category: AiQueryCategory,
    created_at: datetime,
    response: dict | None = None,
) -> AiQuery:
    query = AiQuery(
        audit_id=audit_id,
        query_text=text,
        category=category,
        created_at=created_at,
    )
    db.add(query)
    db.flush()
    if response is not None:
        db.add(
            AiResponse(
                query_id=query.id,
                provider=response.get("provider", "mock"),
                model=response.get("model", "mock-model"),
                response_text=response.get("text", "Answer"),
                brand_mentioned=response.get("brand_mentioned"),
                brand_position=response.get("brand_position"),
                citation_found=response.get("citation_found"),
                semantic_alignment=response.get("semantic_alignment"),
                latency_ms=response.get("latency_ms"),
                created_at=response.get("created_at", created_at),
            )
        )
    db.commit()
    db.refresh(query)
    return query


def _explorer(client: TestClient, **params) -> dict:
    response = client.get("/api/v1/query-explorer", params=params or None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == VIEW_KEYS
    encoded = json.dumps(body)
    assert "owner_id" not in encoded
    assert "password" not in encoded
    return body


def test_unauthenticated_query_explorer_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/query-explorer")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_no_audit_state(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    body = _explorer(client)

    assert body["audit"] is None
    assert body["audits"] == []
    assert body["summary"] is None
    assert body["items"] == []
    assert body["pagination"] == {"page": 1, "page_size": 20, "total": 0, "pages": 0}


def test_latest_completed_audit_is_selected(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    older = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    newer_pending = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.PENDING,
        created_at=MOMENT + timedelta(days=3),
    )
    newer_completed = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT + timedelta(days=1),
        completed_at=MOMENT + timedelta(days=2),
    )
    _add_query(
        db,
        newer_completed.id,
        text="Who is Northwind?",
        category=AiQueryCategory.BRAND,
        created_at=MOMENT,
        response={"text": "Northwind is a retailer.", "brand_mentioned": True},
    )

    body = _explorer(client)
    assert body["audit"]["id"] == str(newer_completed.id)
    assert body["audit"]["id"] != str(older.id)
    assert body["audit"]["id"] != str(newer_pending.id)
    assert body["audit"]["brand_name"] == "Northwind"
    assert body["audit"]["status"] == "COMPLETED"
    assert [item["id"] for item in body["audits"]][0] == str(newer_completed.id)


def test_latest_owned_audit_when_none_completed(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    _add_audit(
        db,
        brand["id"],
        status=AuditStatus.FAILED,
        created_at=MOMENT,
    )
    latest = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.RUNNING,
        created_at=MOMENT + timedelta(hours=4),
    )

    body = _explorer(client)
    assert body["audit"]["id"] == str(latest.id)
    assert body["audit"]["status"] == "RUNNING"
    assert body["summary"]["total_queries"] == 0
    assert body["summary"]["mention_rate"] is None
    assert body["summary"]["citation_rate"] is None


def test_explicit_audit_selection(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    older = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT + timedelta(days=2),
        completed_at=MOMENT + timedelta(days=2),
    )
    _add_query(
        db,
        older.id,
        text="Older audit query",
        category=AiQueryCategory.INDUSTRY,
        created_at=MOMENT,
    )

    body = _explorer(client, audit_id=str(older.id))
    assert body["audit"]["id"] == str(older.id)
    assert body["items"][0]["query_text"] == "Older audit query"
    assert body["items"][0]["has_response"] is False
    assert body["items"][0]["response"] is None


def test_foreign_audit_returns_404(client: TestClient, db: Session) -> None:
    from fastapi.testclient import TestClient as Client

    from app.main import app

    _register_and_login(client, USER_A)
    brand_a = _create_brand(client, BRAND_A)
    audit_a = _add_audit(
        db,
        brand_a["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    _add_query(
        db,
        audit_a.id,
        text="Secret Northwind prompt",
        category=AiQueryCategory.BRAND,
        created_at=MOMENT,
        response={"text": "Private answer about Northwind", "brand_mentioned": True},
    )

    with Client(app) as other:
        _register_and_login(other, USER_B)
        brand_b = _create_brand(other, BRAND_B)
        audit_b = _add_audit(
            db,
            brand_b["id"],
            status=AuditStatus.COMPLETED,
            created_at=MOMENT,
            completed_at=MOMENT,
        )
        foreign = other.get("/api/v1/query-explorer", params={"audit_id": str(audit_a.id)})
        missing = other.get("/api/v1/query-explorer", params={"audit_id": str(uuid4())})
        own = _explorer(other, audit_id=str(audit_b.id))

    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "Not found."
    assert "Northwind" not in foreign.text
    assert "Secret" not in foreign.text
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Not found."
    assert own["audit"]["brand_name"] == "Contoso"
    assert own["items"] == []
    encoded = json.dumps(own)
    assert "Northwind" not in encoded
    assert "Secret" not in encoded


def test_category_filter_and_invalid_category(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    _add_query(
        db,
        audit.id,
        text="Brand question",
        category=AiQueryCategory.BRAND,
        created_at=MOMENT,
    )
    _add_query(
        db,
        audit.id,
        text="Industry question",
        category=AiQueryCategory.INDUSTRY,
        created_at=MOMENT + timedelta(seconds=1),
    )

    body = _explorer(client, category="INDUSTRY")
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["category"] == "INDUSTRY"
    assert body["summary"]["total_queries"] == 2

    invalid = client.get("/api/v1/query-explorer", params={"category": "NOT_A_CATEGORY"})
    assert invalid.status_code == 422


def test_search_filter_is_case_insensitive_and_safe(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    _add_query(
        db,
        audit.id,
        text="Best Northwind shoes",
        category=AiQueryCategory.PRODUCT,
        created_at=MOMENT,
        response={"text": "A long answer that should not be searched"},
    )
    _add_query(
        db,
        audit.id,
        text="100% organic cotton",
        category=AiQueryCategory.PRODUCT,
        created_at=MOMENT + timedelta(seconds=1),
    )
    _add_query(
        db,
        audit.id,
        text="Competitor landscape",
        category=AiQueryCategory.COMPETITOR,
        created_at=MOMENT + timedelta(seconds=2),
    )

    body = _explorer(client, search="  northWIND  ")
    assert [item["query_text"] for item in body["items"]] == ["Best Northwind shoes"]

    literal = _explorer(client, search="%")
    assert [item["query_text"] for item in literal["items"]] == ["100% organic cotton"]

    injected = _explorer(client, search="%' OR 1=1 --")
    assert injected["items"] == []
    assert injected["pagination"]["total"] == 0


def test_has_response_brand_mentioned_and_citation_filters(
    client: TestClient, db: Session
) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    _add_query(
        db,
        audit.id,
        text="Mentioned and cited",
        category=AiQueryCategory.BRAND,
        created_at=MOMENT,
        response={
            "text": "Northwind leads.",
            "brand_mentioned": True,
            "brand_position": 1,
            "citation_found": True,
            "semantic_alignment": Decimal("0.72"),
            "latency_ms": 431,
        },
    )
    _add_query(
        db,
        audit.id,
        text="Response without mention",
        category=AiQueryCategory.COMMERCIAL,
        created_at=MOMENT + timedelta(seconds=1),
        response={
            "text": "Other brands.",
            "brand_mentioned": False,
            "citation_found": False,
        },
    )
    _add_query(
        db,
        audit.id,
        text="Generated only",
        category=AiQueryCategory.INFORMATIONAL,
        created_at=MOMENT + timedelta(seconds=2),
    )

    responded = _explorer(client, has_response=True)
    assert {item["query_text"] for item in responded["items"]} == {
        "Mentioned and cited",
        "Response without mention",
    }

    missing = _explorer(client, has_response=False)
    assert [item["query_text"] for item in missing["items"]] == ["Generated only"]
    assert missing["items"][0]["response"] is None

    mentioned = _explorer(client, brand_mentioned=True)
    assert [item["query_text"] for item in mentioned["items"]] == ["Mentioned and cited"]

    not_mentioned = _explorer(client, brand_mentioned=False)
    assert [item["query_text"] for item in not_mentioned["items"]] == ["Response without mention"]

    cited = _explorer(client, citation_found=True)
    assert [item["query_text"] for item in cited["items"]] == ["Mentioned and cited"]

    not_cited = _explorer(client, citation_found=False)
    assert [item["query_text"] for item in not_cited["items"]] == ["Response without mention"]


def test_pagination_and_page_size_validation(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    for index in range(25):
        _add_query(
            db,
            audit.id,
            text=f"Query {index:02d}",
            category=AiQueryCategory.BRAND,
            created_at=MOMENT + timedelta(seconds=index),
        )

    first = _explorer(client, page=1, page_size=10)
    second = _explorer(client, page=2, page_size=10)
    last = _explorer(client, page=3, page_size=10)

    assert first["pagination"] == {"page": 1, "page_size": 10, "total": 25, "pages": 3}
    assert len(first["items"]) == 10
    assert first["items"][0]["query_text"] == "Query 00"
    assert second["items"][0]["query_text"] == "Query 10"
    assert len(last["items"]) == 5
    assert last["items"][-1]["query_text"] == "Query 24"
    assert _explorer(client)["pagination"]["page_size"] == 20

    for page_size in (0, 15, 101, 1000):
        response = client.get("/api/v1/query-explorer", params={"page_size": page_size})
        assert response.status_code == 422

    allowed = client.get("/api/v1/query-explorer", params={"page_size": 100})
    assert allowed.status_code == 200
    assert allowed.json()["pagination"]["page_size"] == 100
    assert len(allowed.json()["items"]) == 25


def test_summary_metrics_and_null_rates_without_responses(
    client: TestClient, db: Session
) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    empty = _explorer(client)
    assert empty["summary"] == {
        "total_queries": 0,
        "responses": 0,
        "failed": 0,
        "mention_rate": None,
        "citation_rate": None,
    }

    _add_query(
        db,
        audit.id,
        text="No answer yet",
        category=AiQueryCategory.BRAND,
        created_at=MOMENT,
    )
    _add_query(
        db,
        audit.id,
        text="Also unanswered",
        category=AiQueryCategory.PRODUCT,
        created_at=MOMENT + timedelta(seconds=1),
    )
    unanswered = _explorer(client)
    assert unanswered["summary"]["total_queries"] == 2
    assert unanswered["summary"]["responses"] == 0
    assert unanswered["summary"]["failed"] == 2
    assert unanswered["summary"]["mention_rate"] is None
    assert unanswered["summary"]["citation_rate"] is None

    _add_query(
        db,
        audit.id,
        text="Mentioned",
        category=AiQueryCategory.BRAND,
        created_at=MOMENT + timedelta(seconds=2),
        response={"brand_mentioned": True, "citation_found": True, "text": "Yes"},
    )
    _add_query(
        db,
        audit.id,
        text="Silent",
        category=AiQueryCategory.BRAND,
        created_at=MOMENT + timedelta(seconds=3),
        response={"brand_mentioned": False, "citation_found": False, "text": "No"},
    )
    scored = _explorer(client)
    assert scored["summary"]["total_queries"] == 4
    assert scored["summary"]["responses"] == 2
    assert scored["summary"]["failed"] == 2
    assert scored["summary"]["mention_rate"] == 0.5
    assert scored["summary"]["citation_rate"] == 0.5


def test_deterministic_ordering(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    same_time = MOMENT + timedelta(minutes=5)
    _add_query(
        db,
        audit.id,
        text="zeta",
        category=AiQueryCategory.PRODUCT,
        created_at=same_time,
    )
    _add_query(
        db,
        audit.id,
        text="beta",
        category=AiQueryCategory.BRAND,
        created_at=same_time,
    )
    _add_query(
        db,
        audit.id,
        text="alpha",
        category=AiQueryCategory.BRAND,
        created_at=same_time,
    )
    _add_query(
        db,
        audit.id,
        text="earlier industry",
        category=AiQueryCategory.INDUSTRY,
        created_at=MOMENT,
    )

    body = _explorer(client)
    assert [item["query_text"] for item in body["items"]] == [
        "earlier industry",
        "alpha",
        "beta",
        "zeta",
    ]


def test_response_serialization_and_first_response_only(
    client: TestClient, db: Session
) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    query = _add_query(
        db,
        audit.id,
        text="Full body",
        category=AiQueryCategory.BRAND,
        created_at=MOMENT,
        response={
            "text": "Line one\n<script>alert(1)</script>\nLine three",
            "provider": "mock",
            "model": "mock-model",
            "brand_mentioned": True,
            "brand_position": 1,
            "citation_found": True,
            "semantic_alignment": Decimal("0.72"),
            "latency_ms": 431,
            "created_at": MOMENT,
        },
    )
    db.add(
        AiResponse(
            query_id=query.id,
            provider="later",
            model="later-model",
            response_text="This later response must not replace the first one.",
            brand_mentioned=False,
            brand_position=4,
            citation_found=False,
            semantic_alignment=Decimal("0.10"),
            latency_ms=20,
            created_at=MOMENT + timedelta(minutes=10),
        )
    )
    db.commit()

    body = _explorer(client)
    item = body["items"][0]
    assert item["has_response"] is True
    assert set(item.keys()) == {
        "query_id",
        "query_text",
        "category",
        "created_at",
        "has_response",
        "response",
    }
    response = item["response"]
    assert response["text"] == "Line one\n<script>alert(1)</script>\nLine three"
    assert response["provider"] == "mock"
    assert response["model"] == "mock-model"
    assert response["brand_mentioned"] is True
    assert response["brand_position"] == 1
    assert response["citation_found"] is True
    assert response["semantic_alignment"] == 0.72
    assert response["latency_ms"] == 431
    assert "id" not in response
    assert body["summary"]["responses"] == 2
    assert body["summary"]["mention_rate"] == 0.5
    assert body["summary"]["citation_rate"] == 0.5


def test_missing_response_is_not_an_error(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    _add_query(
        db,
        audit.id,
        text="Waiting",
        category=AiQueryCategory.COMMERCIAL,
        created_at=MOMENT,
    )

    response = client.get("/api/v1/query-explorer")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["has_response"] is False
    assert item["response"] is None


def test_explorer_does_not_call_ai_provider(
    client: TestClient, db: Session, monkeypatch
) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("AI provider should not be called")

    monkeypatch.setattr("app.services.ai.get_ai_provider", boom)
    _register_and_login(client, USER_A)
    brand = _create_brand(client, BRAND_A)
    audit = _add_audit(
        db,
        brand["id"],
        status=AuditStatus.COMPLETED,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    _add_query(
        db,
        audit.id,
        text="Persisted only",
        category=AiQueryCategory.BRAND,
        created_at=MOMENT,
        response={"text": "Stored earlier", "brand_mentioned": True, "citation_found": False},
    )

    body = _explorer(client)
    assert body["items"][0]["response"]["text"] == "Stored earlier"


def test_invalid_boolean_filter_is_rejected(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    response = client.get("/api/v1/query-explorer", params={"has_response": "maybe"})
    assert response.status_code == 422
