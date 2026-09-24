"""Phase 18 — Reports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.enums import (
    AiQueryCategory,
    AuditStatus,
    FindingSeverity,
    RecommendationPriority,
    ReportStatus,
)
from app.models.recommendation import Recommendation
from app.models.report import Report
from app.models.website import SeoFinding, WebsitePage
from app.services.reports.data import build_snapshot
from app.services.reports.renderer import render_pdf
from app.services.reports.security import download_filename, pdf_path, report_title

USER_A = {
    "email": "reports-a@example.com",
    "password": "password123",
    "full_name": "Report Owner",
}
USER_B = {
    "email": "reports-b@example.com",
    "password": "password123",
    "full_name": "Other Owner",
}
BRAND_A = {
    "name": "Acme",
    "website_url": "https://acme.example",
    "industry": "Outdoor",
    "country": "United States",
    "target_market": "North America",
    "description": "Trail equipment for independent retailers.",
}
MOMENT = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def reports_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    folder = tmp_path / "reports"
    monkeypatch.setattr(settings, "REPORTS_DIR", str(folder))
    return folder


def _login(client: TestClient, user: dict[str, str]) -> None:
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": user["email"], "password": user["password"]},
        ).status_code
        == 200
    )


def _register_and_login(client: TestClient, user: dict[str, str]) -> None:
    assert client.post("/api/v1/auth/register", json=user).status_code == 201
    _login(client, user)


def _create_brand(client: TestClient, payload: dict[str, str] | None = None) -> dict:
    response = client.post("/api/v1/brands", json=payload or BRAND_A)
    assert response.status_code == 201
    return response.json()


def _add_audit(
    db: Session,
    brand_id: str,
    *,
    status: AuditStatus = AuditStatus.COMPLETED,
    created_at: datetime = MOMENT,
    completed_at: datetime | None = MOMENT,
    overall: Decimal | None = Decimal("72.00"),
    website: Decimal | None = Decimal("80.00"),
    seo: Decimal | None = Decimal("64.00"),
    visibility: Decimal | None = None,
    entity: Decimal | None = None,
    semantic: Decimal | None = None,
) -> Audit:
    audit = Audit(
        brand_id=UUID(brand_id),
        status=status,
        created_at=created_at,
        completed_at=completed_at,
        overall_score=overall,
        website_score=website,
        seo_score=seo,
        ai_visibility_score=visibility,
        entity_score=entity,
        semantic_score=semantic,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def _seed_evidence(db: Session, audit: Audit) -> None:
    home = WebsitePage(
        audit_id=audit.id,
        url="https://acme.example/",
        status_code=200,
        title="Acme trail equipment",
        meta_description="Acme gear",
        has_schema=True,
        schema_types=["Organization"],
        load_time_ms=120,
        created_at=MOMENT,
    )
    missing = WebsitePage(
        audit_id=audit.id,
        url="https://acme.example/missing",
        status_code=404,
        title="Missing",
        has_schema=False,
        load_time_ms=480,
        created_at=MOMENT + timedelta(minutes=1),
    )
    broken = WebsitePage(
        audit_id=audit.id,
        url="https://acme.example/error",
        status_code=500,
        title="Error",
        has_schema=False,
        load_time_ms=900,
        created_at=MOMENT + timedelta(minutes=2),
    )
    db.add_all([home, missing, broken])
    db.flush()
    db.add_all(
        [
            SeoFinding(
                audit_id=audit.id,
                page_id=home.id,
                category="Metadata",
                severity=FindingSeverity.HIGH,
                title="Missing meta description",
                description="7 pages have missing meta descriptions.",
                created_at=MOMENT,
            ),
            SeoFinding(
                audit_id=audit.id,
                page_id=missing.id,
                category="Metadata",
                severity=FindingSeverity.MEDIUM,
                title="Title is short",
                description="The stored title is shorter than the minimum.",
                created_at=MOMENT,
            ),
            SeoFinding(
                audit_id=audit.id,
                page_id=None,
                category="Performance",
                severity=FindingSeverity.LOW,
                title="Slow response",
                description="A stored page was slow.",
                created_at=MOMENT,
            ),
        ]
    )
    mentioned = AiQuery(
        audit_id=audit.id,
        query_text="Who makes trail equipment?",
        category=AiQueryCategory.BRAND,
        created_at=MOMENT,
    )
    silent = AiQuery(
        audit_id=audit.id,
        query_text="Best tents this year",
        category=AiQueryCategory.COMMERCIAL,
        created_at=MOMENT + timedelta(minutes=1),
    )
    db.add_all([mentioned, silent])
    db.flush()
    db.add_all(
        [
            AiResponse(
                query_id=mentioned.id,
                provider="mock",
                model="mock",
                response_text="Acme is often mentioned for trail equipment.",
                brand_mentioned=True,
                brand_position=1,
                citation_found=True,
                semantic_alignment=Decimal("0.80"),
                created_at=MOMENT,
            ),
            AiResponse(
                query_id=silent.id,
                provider="mock",
                model="mock",
                response_text="Several outdoor brands sell tents.",
                brand_mentioned=False,
                brand_position=None,
                citation_found=False,
                semantic_alignment=Decimal("0.10"),
                created_at=MOMENT,
            ),
        ]
    )
    db.add_all(
        [
            Recommendation(
                audit_id=audit.id,
                title="Improve metadata coverage",
                description="7 pages have missing meta descriptions.",
                category="SEO",
                priority=RecommendationPriority.HIGH,
                impact_score=Decimal("90.00"),
                effort_score=Decimal("20.00"),
                created_at=MOMENT,
            ),
            Recommendation(
                audit_id=audit.id,
                title="Review slow pages",
                description="Stored pages include a slow response.",
                category="Website",
                priority=RecommendationPriority.LOW,
                impact_score=Decimal("30.00"),
                effort_score=Decimal("40.00"),
                created_at=MOMENT,
            ),
        ]
    )
    db.commit()


def _forbid_recalculation(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("report generation must not recalculate or crawl")

    monkeypatch.setattr("app.services.score_service.run_score_calculation", boom)
    monkeypatch.setattr("app.services.ai_visibility_service.run_visibility_calculation", boom)
    monkeypatch.setattr("app.services.entity_service.run_entity_calculation", boom)
    monkeypatch.setattr("app.services.recommendation_service.run_recommendation_calculation", boom)
    monkeypatch.setattr("app.services.seo_analysis_service.run_seo_analysis", boom)
    monkeypatch.setattr("app.services.crawl_service.run_crawl", boom)
    monkeypatch.setattr("app.services.ai.factory.get_ai_provider", boom)


def test_unauthenticated_report_endpoints_are_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/reports").status_code == 401
    assert client.post("/api/v1/reports", json={"audit_id": str(uuid4())}).status_code == 401
    assert client.get(f"/api/v1/reports/{uuid4()}").status_code == 401
    download = client.get(f"/api/v1/reports/{uuid4()}/download")
    assert download.status_code == 401
    assert download.json()["detail"] == "Not authenticated"


def test_foreign_audit_is_not_found(client: TestClient, db: Session, reports_dir) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _add_audit(db, brand["id"])
    client.post("/api/v1/auth/logout")
    _register_and_login(client, USER_B)
    response = client.post("/api/v1/reports", json={"audit_id": str(audit.id)})
    assert response.status_code == 404
    assert response.json()["detail"] == "Not found."
    assert db.scalar(select(Report.id)) is None


def test_incomplete_audit_is_rejected(client: TestClient, db: Session, reports_dir) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _add_audit(db, brand["id"], status=AuditStatus.PENDING, completed_at=None, overall=None)
    response = client.post("/api/v1/reports", json={"audit_id": str(audit.id)})
    assert response.status_code == 422
    assert response.json()["detail"] == "Complete the audit before generating a report."
    assert db.scalar(select(Report.id)) is None


def test_create_ready_report_from_persisted_data(
    client: TestClient,
    db: Session,
    reports_dir,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forbid_recalculation(monkeypatch)
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _add_audit(db, brand["id"], visibility=Decimal("55.00"), entity=Decimal("61.00"))
    _seed_evidence(db, audit)
    before = (
        audit.overall_score,
        audit.website_score,
        audit.seo_score,
        audit.ai_visibility_score,
        audit.entity_score,
    )

    response = client.post("/api/v1/reports", json={"audit_id": str(audit.id)})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "READY"
    assert body["title"] == "Acme — Audit Intelligence Report"
    assert body["brand_name"] == "Acme"
    assert body["overall_status"] == "AVAILABLE"
    assert body["overall_score"] == 72.0
    assert body["message"] is None
    assert "Executive Summary" in body["sections"]
    assert "file_path" not in body
    assert str(reports_dir) not in response.text

    db.refresh(audit)
    assert (
        audit.overall_score,
        audit.website_score,
        audit.seo_score,
        audit.ai_visibility_score,
        audit.entity_score,
    ) == before
    stored = db.get(Report, UUID(body["id"]))
    assert stored is not None
    assert stored.status == ReportStatus.READY
    assert stored.file_path == f"{stored.id}.pdf"
    assert (reports_dir / f"{stored.id}.pdf").is_file()
    assert (reports_dir / f"{stored.id}.pdf").read_bytes().startswith(b"%PDF")


def test_list_orders_and_filters_owned_reports(client: TestClient, db: Session, reports_dir) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    older = _add_audit(db, brand["id"], created_at=MOMENT, completed_at=MOMENT)
    newer = _add_audit(
        db,
        brand["id"],
        created_at=MOMENT + timedelta(days=1),
        completed_at=MOMENT + timedelta(days=1),
    )
    first = client.post("/api/v1/reports", json={"audit_id": str(older.id)})
    second = client.post("/api/v1/reports", json={"audit_id": str(newer.id)})
    assert first.status_code == 201
    assert second.status_code == 201
    first_row = db.get(Report, UUID(first.json()["id"]))
    second_row = db.get(Report, UUID(second.json()["id"]))
    assert first_row is not None and second_row is not None
    first_row.created_at = MOMENT
    second_row.created_at = MOMENT + timedelta(days=1)
    db.commit()

    listed = client.get("/api/v1/reports")
    assert listed.status_code == 200
    payload = listed.json()
    assert [item["id"] for item in payload["items"]] == [str(second_row.id), str(first_row.id)]
    assert payload["items"][0]["brand_name"] == "Acme"
    assert payload["completed_audits"]
    filtered = client.get("/api/v1/reports", params={"audit_id": str(older.id)})
    assert [item["id"] for item in filtered.json()["items"]] == [str(first_row.id)]

    client.post("/api/v1/auth/logout")
    _register_and_login(client, USER_B)
    hidden = client.get("/api/v1/reports")
    assert hidden.json()["items"] == []
    foreign = client.get("/api/v1/reports", params={"audit_id": str(older.id)})
    assert foreign.status_code == 404


def test_detail_download_and_foreign_report(client: TestClient, db: Session, reports_dir) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _add_audit(db, brand["id"])
    created = client.post("/api/v1/reports", json={"audit_id": str(audit.id)})
    report_id = created.json()["id"]

    detail = client.get(f"/api/v1/reports/{report_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "READY"
    assert "file_path" not in detail.json()
    assert str(reports_dir) not in detail.text

    download = client.get(f"/api/v1/reports/{report_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/pdf")
    disposition = download.headers["content-disposition"]
    assert "Acme-audit-intelligence-report.pdf" in disposition
    assert str(reports_dir) not in disposition
    assert download.content.startswith(b"%PDF")
    assert b"Executive Summary" in download.content
    assert b"Website Health" in download.content
    assert b"SEO Analysis" in download.content
    assert b"AI Visibility" in download.content
    assert b"Entity Intelligence" in download.content
    assert b"Recommendations" in download.content
    assert b"AI Query Snapshot" in download.content
    assert b"Methodology" in download.content

    client.post("/api/v1/auth/logout")
    _register_and_login(client, USER_B)
    assert client.get(f"/api/v1/reports/{report_id}").status_code == 404
    foreign_download = client.get(f"/api/v1/reports/{report_id}/download")
    assert foreign_download.status_code == 404
    assert b"%PDF" not in foreign_download.content


def test_generating_and_failed_downloads(client: TestClient, db: Session, reports_dir) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _add_audit(db, brand["id"])
    generating = Report(
        audit_id=audit.id,
        title="Acme — Audit Intelligence Report",
        status=ReportStatus.GENERATING,
        file_path=None,
        created_at=MOMENT,
    )
    failed = Report(
        audit_id=audit.id,
        title="Acme — Audit Intelligence Report",
        status=ReportStatus.FAILED,
        file_path=None,
        created_at=MOMENT,
        completed_at=MOMENT,
    )
    db.add_all([generating, failed])
    db.commit()

    generating_download = client.get(f"/api/v1/reports/{generating.id}/download")
    assert generating_download.status_code == 409
    assert generating_download.json()["detail"] == "This report is still generating."
    failed_download = client.get(f"/api/v1/reports/{failed.id}/download")
    assert failed_download.status_code == 409
    assert failed_download.json()["detail"] == "This report failed and cannot be downloaded."


def test_generation_failure_is_safe(
    client: TestClient,
    db: Session,
    reports_dir,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(_snapshot, path):
        path.write_bytes(b"%PDF-partial secret-traceback")
        raise RuntimeError("secret-traceback /tmp/hidden")

    monkeypatch.setattr("app.services.reports.service.render_pdf", explode)
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _add_audit(db, brand["id"])
    response = client.post("/api/v1/reports", json={"audit_id": str(audit.id)})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["message"] == "The report could not be generated. Please try again."
    assert "secret-traceback" not in response.text
    assert "Traceback" not in response.text
    stored = db.get(Report, UUID(body["id"]))
    assert stored is not None
    assert stored.file_path is None
    assert list(reports_dir.glob("*")) == []


def test_ready_report_stays_immutable_when_audit_changes(
    client: TestClient,
    db: Session,
    reports_dir,
) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _add_audit(db, brand["id"])
    created = client.post("/api/v1/reports", json={"audit_id": str(audit.id)})
    report_id = created.json()["id"]
    original = (reports_dir / f"{report_id}.pdf").read_bytes()

    audit.overall_score = Decimal("10.00")
    db.commit()
    again = client.get(f"/api/v1/reports/{report_id}/download")
    assert again.content == original

    second = client.post("/api/v1/reports", json={"audit_id": str(audit.id)})
    assert second.status_code == 201
    assert second.json()["id"] != report_id
    assert (reports_dir / f"{report_id}.pdf").read_bytes() == original
    assert (reports_dir / f"{second.json()['id']}.pdf").is_file()


def test_snapshot_uses_persisted_values_and_keeps_nulls(db: Session, reports_dir) -> None:
    brand = _brand_row(db)
    audit = _add_audit(
        db,
        str(brand.id),
        overall=None,
        website=None,
        seo=None,
        visibility=None,
        entity=None,
    )
    _seed_evidence(db, audit)
    snapshot = build_snapshot(db, audit, brand, generated_at=MOMENT)

    assert snapshot.brand.name == "Acme"
    assert snapshot.brand.website == "https://acme.example"
    assert snapshot.brand.industry == "Outdoor"
    assert snapshot.audit.status == "COMPLETED"
    assert all(line.score is None for line in snapshot.scores)
    assert snapshot.overall.status == "UNAVAILABLE"
    assert snapshot.website.pages_crawled == 3
    assert snapshot.website.analyzable_pages == 1
    assert snapshot.website.successful_http == 1
    assert snapshot.website.client_errors == 1
    assert snapshot.website.server_errors == 1
    assert snapshot.website.average_load_ms == Decimal("500")
    assert snapshot.seo.total == 3
    assert snapshot.seo.high == 1
    assert snapshot.seo.medium == 1
    assert snapshot.seo.low == 1
    assert snapshot.seo.findings[0].title == "Missing meta description"
    assert snapshot.seo.findings[0].page_url == "https://acme.example/"
    assert snapshot.visibility.score is None
    assert snapshot.visibility.mention_rate is None
    assert snapshot.visibility.citation_rate is None
    assert snapshot.entity.score is None
    assert snapshot.entity.presence is None
    assert snapshot.entity.consistency is None
    assert snapshot.entity.structured_identity is None
    assert snapshot.entity.ai_recognition is None
    assert snapshot.recommendations[0].title == "Improve metadata coverage"
    assert snapshot.recommendations[0].description == "7 pages have missing meta descriptions."
    assert snapshot.recommendations[1].priority == "LOW"
    assert snapshot.queries.total_queries == 2
    assert snapshot.queries.successful_responses == 2
    assert snapshot.queries.brand_mentions == 1
    assert snapshot.queries.citations == 1
    assert snapshot.queries.examples[0].brand_mentioned is True
    assert "Acme is often mentioned" not in " ".join(item.text for item in snapshot.queries.examples)


def test_provisional_overall_and_available_breakdowns(db: Session, reports_dir) -> None:
    brand = _brand_row(db)
    provisional = _add_audit(db, str(brand.id))
    _seed_evidence(db, provisional)
    provisional_snapshot = build_snapshot(db, provisional, brand, generated_at=MOMENT)
    assert provisional_snapshot.overall.score == Decimal("72.00")
    assert provisional_snapshot.overall.status == "PROVISIONAL"
    assert "not yet included" in (provisional_snapshot.overall.note or "")
    assert provisional_snapshot.visibility.mention_rate is None

    complete = _add_audit(
        db,
        str(brand.id),
        visibility=Decimal("55.00"),
        entity=Decimal("61.00"),
        semantic=Decimal("40.00"),
        created_at=MOMENT + timedelta(days=1),
    )
    _seed_evidence(db, complete)
    complete_snapshot = build_snapshot(db, complete, brand, generated_at=MOMENT)
    assert complete_snapshot.overall.status == "AVAILABLE"
    assert complete_snapshot.visibility.score == Decimal("55.00")
    assert complete_snapshot.visibility.mention_rate is not None
    assert complete_snapshot.visibility.citation_rate is not None
    assert complete_snapshot.entity.score == Decimal("61.00")
    assert complete_snapshot.entity.presence is not None
    db.refresh(complete)
    assert complete.ai_visibility_score == Decimal("55.00")
    assert complete.entity_score == Decimal("61.00")
    assert complete.overall_score == Decimal("72.00")


def test_pdf_is_deterministic_and_explains_provisional_scores(db: Session, reports_dir, tmp_path) -> None:
    brand = _brand_row(db)
    audit = _add_audit(db, str(brand.id))
    _seed_evidence(db, audit)
    snapshot = build_snapshot(db, audit, brand, generated_at=MOMENT)
    first = tmp_path / "one.pdf"
    second = tmp_path / "two.pdf"
    render_pdf(snapshot, first)
    render_pdf(snapshot, second)
    assert first.read_bytes() == second.read_bytes()
    payload = first.read_bytes()
    text = _pdf_text(payload)
    assert payload.startswith(b"%PDF")
    assert "Overall Intelligence Score" in text
    assert "72 / 100" in text
    assert "Provisional" in text
    assert "not yet included in the overall" in text
    assert "Not available" in text
    for section in (
        "Executive Summary",
        "Website Health",
        "SEO Analysis",
        "AI Visibility",
        "Entity Intelligence",
        "Recommendations",
        "AI Query Snapshot",
        "Methodology",
    ):
        assert section in text


def test_download_ignores_stored_filesystem_paths(
    client: TestClient,
    db: Session,
    reports_dir,
    tmp_path,
) -> None:
    _register_and_login(client, USER_A)
    brand = _create_brand(client)
    audit = _add_audit(db, brand["id"])
    created = client.post("/api/v1/reports", json={"audit_id": str(audit.id)})
    report = db.get(Report, UUID(created.json()["id"]))
    assert report is not None
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET", encoding="utf-8")
    report.file_path = str(secret)
    db.commit()

    download = client.get(f"/api/v1/reports/{report.id}/download")
    assert download.status_code == 200
    assert b"TOP-SECRET" not in download.content
    assert download.content.startswith(b"%PDF")
    detail = client.get(f"/api/v1/reports/{report.id}")
    assert "secret.txt" not in detail.text
    assert "TOP-SECRET" not in detail.text
    assert str(secret) not in detail.text


def test_path_helpers_reject_user_controlled_names(reports_dir) -> None:
    report_id = uuid4()
    path = pdf_path(report_id)
    assert path.parent == reports_dir.resolve()
    assert path.name == f"{report_id}.pdf"
    assert ".." not in path.name
    assert download_filename("../../etc/passwd") == "etc-passwd-audit-intelligence-report.pdf"
    assert "/" not in download_filename("../../etc/passwd")
    assert download_filename("Acme") == "Acme-audit-intelligence-report.pdf"
    assert report_title("Acme") == "Acme — Audit Intelligence Report"


def test_invalid_report_id_does_not_touch_the_filesystem(client: TestClient, reports_dir) -> None:
    from app.services.reports.security import UnsafeReportPath
    from app.services.reports.security import _contained

    _register_and_login(client, USER_A)
    response = client.get("/api/v1/reports/not-a-uuid")
    assert response.status_code == 422
    escaped = client.get("/api/v1/reports/..%2F..%2Fetc%2Fpasswd")
    assert escaped.status_code in {404, 422}
    assert not any(reports_dir.glob("*"))
    with pytest.raises(UnsafeReportPath):
        _contained("../secret.pdf")
    with pytest.raises(UnsafeReportPath):
        _contained("..\\secret.pdf")


def test_secrets_are_not_copied_into_the_snapshot(db: Session, reports_dir, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-secret-value")
    brand = _brand_row(db)
    brand.description = "Notes sk-test-secret-value should stay on the server."
    db.commit()
    audit = _add_audit(db, str(brand.id), overall=None, website=None, seo=None)
    snapshot = build_snapshot(db, audit, brand, generated_at=MOMENT)
    assert snapshot.brand.description is not None
    assert "sk-test-secret-value" not in snapshot.brand.description
    assert "[redacted]" in snapshot.brand.description


def _pdf_text(data: bytes) -> str:
    import re

    parts = re.findall(rb"\((?:\\.|[^\\)])*\)", data)
    chunks = []
    for part in parts:
        raw = part[1:-1].replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
        chunks.append(raw.decode("latin-1", "ignore"))
    return "".join(chunks)


def _brand_row(db: Session):
    from app.models.brand import Brand
    from app.models.user import User

    user = User(
        email=f"snap-{uuid4()}@example.com",
        password_hash="hash",
        full_name="Snapshot",
    )
    db.add(user)
    db.flush()
    brand = Brand(
        owner_id=user.id,
        name="Acme",
        website_url="https://acme.example",
        industry="Outdoor",
        country="United States",
        target_market="North America",
        description="Trail equipment for independent retailers.",
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand
