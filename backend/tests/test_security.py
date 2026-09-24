"""Phase 21 — security hardening regression suite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.middleware import MAX_REQUEST_BODY_BYTES, reset_auth_rate_limits
from app.core.security import decode_access_token
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.enums import AuditStatus
from app.models.user import User
from app.services.intelligence.context import build_audit_context, context_for_prompt
from app.services.intelligence.models import QuestionIntent
from app.services.intelligence.safety import redact_sensitive
from app.services.reports.security import UnsafeReportPath, _contained

USER = {
    "email": "security@example.com",
    "password": "password123",
    "full_name": "Security User",
}
BRAND = {
    "name": "Secure Brand",
    "website_url": "https://secure.example",
    "industry": "Software",
    "country": "United States",
    "target_market": "North America",
    "description": "Owned brand",
}
ALLOWED_ORIGIN = "http://localhost:4200"
FORBIDDEN_ORIGIN = "https://evil.example"


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    reset_auth_rate_limits()


def _register_login(client: TestClient) -> None:
    assert client.post("/api/v1/auth/register", json=USER).status_code == 201
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": USER["email"], "password": USER["password"]},
        ).status_code
        == 200
    )


# --- Authentication / cookies / JWT ---


def test_cookie_security_flags_in_development(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=USER)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": USER["email"], "password": USER["password"]},
    )
    cookie = response.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie
    assert "Path=/" in cookie
    assert f"Max-Age={settings.JWT_EXPIRE_MINUTES * 60}" in cookie
    assert "samesite=lax" in cookie.lower() or "SameSite=lax" in cookie
    assert "Secure" not in cookie  # development default


def test_cookie_secure_required_shape_when_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    client.post("/api/v1/auth/register", json={**USER, "email": "secure-cookie@example.com"})
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "secure-cookie@example.com", "password": USER["password"]},
    )
    assert "Secure" in response.headers.get("set-cookie", "")


def test_logout_invalidates_session_cookie(client: TestClient) -> None:
    _register_login(client)
    assert client.get("/api/v1/auth/me").status_code == 200
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert settings.COOKIE_NAME in logout.headers.get("set-cookie", "")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_jwt_expiration_and_invalid_tokens_fail_safe(client: TestClient) -> None:
    _register_login(client)
    me = client.get("/api/v1/auth/me")
    user_id = me.json()["id"]

    expired = jwt.encode(
        {"sub": user_id, "exp": datetime(2000, 1, 1, tzinfo=timezone.utc)},
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    client.cookies.set(settings.COOKIE_NAME, expired)
    assert client.get("/api/v1/auth/me").status_code == 401

    client.cookies.set(settings.COOKIE_NAME, "not-a-jwt")
    assert client.get("/api/v1/auth/me").status_code == 401

    forged = jwt.encode(
        {"sub": user_id, "exp": datetime(2099, 1, 1, tzinfo=timezone.utc)},
        "wrong-secret-value-xxxxxxxxxxxxxxxx",
        algorithm="HS256",
    )
    client.cookies.set(settings.COOKIE_NAME, forged)
    assert client.get("/api/v1/auth/me").status_code == 401

    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": USER["email"], "password": USER["password"]},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me").status_code == 200


def test_jwt_subject_must_be_uuid() -> None:
    bad = jwt.encode(
        {"sub": "not-a-uuid", "exp": datetime(2099, 1, 1, tzinfo=timezone.utc)},
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises((jwt.InvalidTokenError, ValueError)):
        decode_access_token(bad)


def test_passwords_never_returned_or_logged_shape(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=USER)
    body = response.json()
    assert "password" not in body
    assert "password_hash" not in body
    assert USER["password"] not in response.text


def test_mass_assignment_rejected_on_auth(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            **USER,
            "email": "mass@example.com",
            "is_active": False,
            "password_hash": "x",
            "id": str(uuid4()),
        },
    )
    assert response.status_code == 422


def test_mass_assignment_rejected_on_brands(client: TestClient) -> None:
    _register_login(client)
    response = client.post(
        "/api/v1/brands",
        json={
            **BRAND,
            "owner_id": str(uuid4()),
            "id": str(uuid4()),
            "created_at": "2020-01-01T00:00:00Z",
        },
    )
    assert response.status_code == 422


# --- Production JWT / cookie configuration ---


def test_production_rejects_weak_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="change-me-in-development",
            COOKIE_SECURE=True,
            CORS_ORIGINS="https://app.example",
        )


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="short-but-not-default",
            COOKIE_SECURE=True,
            CORS_ORIGINS="https://app.example",
        )


def test_production_rejects_insecure_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="a" * 32,
            COOKIE_SECURE=False,
            CORS_ORIGINS="https://app.example",
        )


def test_production_accepts_strong_configuration() -> None:
    cfg = Settings(
        ENVIRONMENT="production",
        JWT_SECRET="a" * 32,
        COOKIE_SECURE=True,
        CORS_ORIGINS="https://app.example",
        COOKIE_SAMESITE="lax",
        DATABASE_URL="postgresql://brand_app:placeholder@postgres:5432/brand_intelligence",
    )
    assert cfg.is_production
    assert cfg.COOKIE_SECURE is True


def test_cors_rejects_wildcard() -> None:
    with pytest.raises(ValidationError):
        Settings(CORS_ORIGINS="*")


def test_samesite_none_requires_secure() -> None:
    with pytest.raises(ValidationError):
        Settings(COOKIE_SAMESITE="none", COOKIE_SECURE=False)


# --- CSRF / CORS ---


def test_csrf_rejects_foreign_origin_on_state_change(client: TestClient) -> None:
    _register_login(client)
    response = client.post(
        "/api/v1/brands",
        json=BRAND,
        headers={"Origin": FORBIDDEN_ORIGIN},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden."


def test_csrf_allows_configured_origin(client: TestClient) -> None:
    _register_login(client)
    response = client.post(
        "/api/v1/brands",
        json=BRAND,
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert response.status_code == 201


def test_csrf_rejects_foreign_referer(client: TestClient) -> None:
    _register_login(client)
    response = client.post(
        "/api/v1/brands",
        json={**BRAND, "name": "Referer Brand"},
        headers={"Referer": f"{FORBIDDEN_ORIGIN}/attack"},
    )
    assert response.status_code == 403


def test_cors_preflight_allows_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/brands",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_rejects_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/brands",
        headers={
            "Origin": FORBIDDEN_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") != FORBIDDEN_ORIGIN


# --- Security headers / errors / body limits ---


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "default-src 'none'" in response.headers.get("content-security-policy", "")


def test_request_body_size_limit(client: TestClient) -> None:
    _register_login(client)
    oversized = "x" * (MAX_REQUEST_BODY_BYTES + 10)
    response = client.post(
        "/api/v1/brands",
        content=json.dumps({**BRAND, "description": oversized}),
        headers={"Content-Type": "application/json", "Content-Length": str(MAX_REQUEST_BODY_BYTES + 100)},
    )
    assert response.status_code == 413


def test_database_error_response_is_safe(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    from app.services import brand_service

    _register_login(client)

    def boom(*_args, **_kwargs):  # noqa: ANN001
        raise SQLAlchemyError(
            "dsn=postgresql://user:hunter2@db/brand SELECT * FROM pg_shadow path=/tmp/hidden"
        )

    monkeypatch.setattr(brand_service, "list_user_brands", boom)
    response = client.get("/api/v1/brands")
    assert response.status_code == 500
    assert response.json() == {"detail": "An internal error occurred."}
    assert "hunter2" not in response.text
    assert "pg_shadow" not in response.text
    assert "/tmp/" not in response.text


# --- SQL injection / path traversal / AI secrets ---


def test_sql_injection_search_values_are_literal(client: TestClient, db: Session) -> None:
    from uuid import UUID

    _register_login(client)
    brand = client.post("/api/v1/brands", json=BRAND).json()
    audit = Audit(
        brand_id=UUID(brand["id"]),
        status=AuditStatus.COMPLETED,
        created_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
        completed_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
    )
    db.add(audit)
    db.commit()
    for payload in ("'", '"', "' OR 1=1 --", "%", "_", "'; DROP TABLE users; --"):
        response = client.get(
            "/api/v1/query-explorer",
            params={"audit_id": str(audit.id), "search": payload},
        )
        assert response.status_code == 200, payload
        assert "password_hash" not in response.text


def test_report_path_traversal_rejected() -> None:
    for name in (
        "../secret.pdf",
        "..\\..\\secret.pdf",
        "/etc/passwd.pdf",
        "....//secret.pdf",
        "not-a-uuid.pdf",
    ):
        with pytest.raises(UnsafeReportPath):
            _contained(name)


def test_ai_context_excludes_secrets_and_config(db: Session) -> None:
    user = User(
        email="ai-context@example.com",
        password_hash="argon2-hash-value",
        full_name="AI Context",
        is_active=True,
    )
    db.add(user)
    db.flush()
    brand = Brand(
        owner_id=user.id,
        name="Context Brand",
        website_url="https://context.example",
        industry="Software",
        country="United States",
        target_market="North America",
        description="Public description only",
    )
    db.add(brand)
    db.flush()
    audit = Audit(brand_id=brand.id, status=AuditStatus.COMPLETED, overall_score=Decimal("50.00"))
    db.add(audit)
    db.commit()

    context = build_audit_context(db, audit)
    payload = context_for_prompt(context, QuestionIntent.GENERAL)
    encoded = json.dumps(payload, default=str)

    forbidden = (
        "JWT_SECRET",
        "OPENAI_API_KEY",
        "DATABASE_URL",
        "password_hash",
        "argon2-hash-value",
        settings.JWT_SECRET,
        "change-me-in-development-only!!!",
    )
    for item in forbidden:
        assert item not in encoded


def test_redact_sensitive_covers_jwt_and_db_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-live-abcdef123456")
    monkeypatch.setattr(settings, "JWT_SECRET", "super-secret-jwt-value-xxxxxx")
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://app:db-pass-secret@postgres:5432/brand_intelligence",
    )
    text = redact_sensitive(
        "key=sk-live-abcdef123456 jwt=super-secret-jwt-value-xxxxxx pwd=db-pass-secret"
    )
    assert "sk-live-abcdef123456" not in text
    assert "super-secret-jwt-value-xxxxxx" not in text
    assert "db-pass-secret" not in text
    assert "[redacted]" in text


def test_swagger_does_not_embed_runtime_secrets(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.text
    assert settings.JWT_SECRET not in body
    if settings.OPENAI_API_KEY:
        assert settings.OPENAI_API_KEY not in body


def test_pdf_report_does_not_embed_known_secrets(
    client: TestClient,
    db: Session,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import UUID

    from app.models.enums import ReportStatus
    from app.services.reports import service as report_service

    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-pdf-secret-value-xyz")
    monkeypatch.setattr(settings, "JWT_SECRET", "jwt-pdf-secret-value-abcdefgh")

    _register_login(client)
    brand = client.post("/api/v1/brands", json=BRAND).json()
    audit = Audit(
        brand_id=UUID(brand["id"]),
        status=AuditStatus.COMPLETED,
        overall_score=Decimal("70.00"),
        website_score=Decimal("70.00"),
        seo_score=Decimal("70.00"),
        created_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
        completed_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
    )
    db.add(audit)
    db.commit()

    me = client.get("/api/v1/auth/me").json()
    user = db.get(User, UUID(me["id"]))
    assert user is not None
    report, _message = report_service.create_report(db, user, audit.id)
    assert report.status == ReportStatus.READY
    path, _filename = report_service.download_report(db, user, report.id)
    pdf_bytes = path.read_bytes()
    assert b"sk-pdf-secret-value-xyz" not in pdf_bytes
    assert b"jwt-pdf-secret-value-abcdefgh" not in pdf_bytes
    assert b"OPENAI_API_KEY" not in pdf_bytes
    assert b"JWT_SECRET" not in pdf_bytes
    assert b"Traceback" not in pdf_bytes
