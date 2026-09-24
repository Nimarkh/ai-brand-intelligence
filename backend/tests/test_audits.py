from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.audits import get_crawler
from app.main import app
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.enums import AuditStatus
from app.services.crawler import WebsiteCrawler
from tests.test_crawler import _crawler, _html, _page

USER_A = {
    "email": "owner-a@example.com",
    "password": "password123",
    "full_name": "Owner A",
}
USER_B = {
    "email": "owner-b@example.com",
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
SCORE_FIELDS = (
    "overall_score",
    "website_score",
    "seo_score",
    "ai_visibility_score",
    "entity_score",
    "semantic_score",
)


def _register_and_login(client: TestClient, user: dict[str, str]) -> None:
    registered = client.post("/api/v1/auth/register", json=user)
    assert registered.status_code == 201
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert logged_in.status_code == 200


def _create_brand(client: TestClient, payload: dict[str, str] | None = None) -> dict:
    response = client.post("/api/v1/brands", json=payload or BRAND_A)
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body, dict)
    return body


def _northwind_crawler() -> WebsiteCrawler:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "cookie" not in {name.lower() for name in request.headers}
        if request.url.host != "northwind.example":
            raise AssertionError(request.url.host)
        if request.url.path == "/robots.txt":
            return httpx.Response(404, text="missing")
        return _html(_page("Home"))

    return _crawler(handler, max_pages=5, max_depth=1)


@pytest.fixture()
def mocked_crawler():
    def override():
        crawler = _northwind_crawler()
        try:
            yield crawler
        finally:
            crawler.close()

    app.dependency_overrides[get_crawler] = override
    yield
    app.dependency_overrides.pop(get_crawler, None)


def test_unauthenticated_audit_requests_are_rejected(client: TestClient) -> None:
    brand_id = "11111111-1111-4111-8111-111111111111"
    audit_id = "22222222-2222-4222-8222-222222222222"
    responses = (
        client.post(f"/api/v1/brands/{brand_id}/audits"),
        client.get(f"/api/v1/brands/{brand_id}/audits"),
        client.get(f"/api/v1/audits/{audit_id}"),
        client.post(f"/api/v1/audits/{audit_id}/crawl"),
        client.post(f"/api/v1/audits/{audit_id}/analyze-seo"),
        client.get(f"/api/v1/audits/{audit_id}/seo-findings"),
        client.post(f"/api/v1/audits/{audit_id}/calculate-score"),
        client.get(f"/api/v1/audits/{audit_id}/score"),
    )
    assert [response.status_code for response in responses] == [401, 401, 401, 401, 401, 401, 401, 401]


def test_owner_can_create_an_audit_without_scores(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    created = client.post(f"/api/v1/brands/{brand['id']}/audits")
    assert created.status_code == 201
    body = created.json()
    assert body["brand_id"] == brand["id"]
    assert body["status"] == "PENDING"
    assert body["pages_crawled"] == 0
    assert body["started_at"] is None
    assert body["completed_at"] is None
    for field in SCORE_FIELDS:
        assert body[field] is None

    listed = client.get(f"/api/v1/brands/{brand['id']}/audits")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == body["id"]

    fetched = client.get(f"/api/v1/audits/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "PENDING"


def test_non_owner_audit_access_is_not_found(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    created = client.post(f"/api/v1/brands/{brand['id']}/audits")
    audit_id = created.json()["id"]

    client.post("/api/v1/auth/logout")
    _register_and_login(client, USER_B)

    assert client.post(f"/api/v1/brands/{brand['id']}/audits").status_code == 404
    assert client.get(f"/api/v1/brands/{brand['id']}/audits").status_code == 404
    assert client.get(f"/api/v1/audits/{audit_id}").status_code == 404
    hidden = client.post(f"/api/v1/audits/{audit_id}/crawl")
    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "Not found."
    assert "Northwind" not in hidden.text


def test_missing_audit_is_not_found(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    missing = "33333333-3333-4333-8333-333333333333"
    assert client.get(f"/api/v1/audits/{missing}").status_code == 404
    assert client.post(f"/api/v1/audits/{missing}/crawl").status_code == 404


def test_owner_crawl_completes_and_leaves_scores_null(client: TestClient, mocked_crawler: None, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    created = client.post(f"/api/v1/brands/{brand['id']}/audits")
    audit_id = created.json()["id"]

    crawled = client.post(f"/api/v1/audits/{audit_id}/crawl")
    assert crawled.status_code == 200
    body = crawled.json()
    assert set(body) == {"audit_id", "status", "pages_crawled"}
    assert body["audit_id"] == audit_id
    assert body["status"] == "COMPLETED"
    assert body["pages_crawled"] == 1

    fetched = client.get(f"/api/v1/audits/{audit_id}")
    assert fetched.status_code == 200
    snapshot = fetched.json()
    assert snapshot["status"] == "COMPLETED"
    assert snapshot["pages_crawled"] == 1
    assert snapshot["started_at"] is not None
    assert snapshot["completed_at"] is not None
    for field in SCORE_FIELDS:
        assert snapshot[field] is None

    audit = db.get(Audit, UUID(audit_id))
    assert audit is not None
    assert audit.overall_score is None
    assert audit.website_score is None
    assert audit.seo_score is None
    assert audit.ai_visibility_score is None
    assert audit.entity_score is None
    assert audit.semantic_score is None


def test_crawl_failure_response_hides_internal_errors(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client, {**BRAND_A, "website_url": "http://127.0.0.1"})
    created = client.post(f"/api/v1/brands/{brand['id']}/audits")
    audit_id = created.json()["id"]

    failed = client.post(f"/api/v1/audits/{audit_id}/crawl")
    assert failed.status_code == 500
    assert failed.json() == {"detail": "Website crawl failed. Please try again."}
    assert "Traceback" not in failed.text
    assert "127.0.0.1" not in failed.text

    fetched = client.get(f"/api/v1/audits/{audit_id}")
    assert fetched.json()["status"] == "FAILED"
    for field in SCORE_FIELDS:
        assert fetched.json()[field] is None

    stored = db.get(Brand, UUID(brand["id"]))
    assert stored is not None
    audit = db.get(Audit, UUID(audit_id))
    assert audit is not None
    assert audit.status == AuditStatus.FAILED


def test_missing_website_does_not_start_a_crawl(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    created = client.post(f"/api/v1/brands/{brand['id']}/audits")
    audit_id = created.json()["id"]
    stored = db.get(Brand, UUID(brand["id"]))
    assert stored is not None
    stored.website_url = None
    db.commit()

    response = client.post(f"/api/v1/audits/{audit_id}/crawl")
    assert response.status_code == 422
    audit = db.get(Audit, UUID(audit_id))
    assert audit is not None
    assert audit.status == AuditStatus.PENDING


def test_running_audit_cannot_be_crawled_again(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    created = client.post(f"/api/v1/brands/{brand['id']}/audits")
    audit_id = created.json()["id"]
    audit = db.get(Audit, UUID(audit_id))
    assert audit is not None
    audit.status = AuditStatus.RUNNING
    db.commit()

    response = client.post(f"/api/v1/audits/{audit_id}/crawl")
    assert response.status_code == 409
