from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User

REGISTER_PAYLOAD = {
    "email": "user@example.com",
    "password": "password123",
    "full_name": "Example User",
}


def _assert_safe_user(body: object) -> dict:
    assert isinstance(body, dict)
    assert "password_hash" not in body
    assert set(body.keys()) == {"id", "email", "full_name"}
    return body


def test_register_success(client: TestClient, db: Session) -> None:
    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 201
    body = _assert_safe_user(response.json())
    assert body["email"] == "user@example.com"
    assert body["full_name"] == "Example User"

    stored = db.get(User, UUID(body["id"]))
    assert stored is not None
    assert stored.password_hash != REGISTER_PAYLOAD["password"]
    assert stored.password_hash.startswith("$argon2")


def test_register_normalizes_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "  User@Example.COM ",
            "password": "password123",
            "full_name": "  Example User  ",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "user@example.com"
    assert response.json()["full_name"] == "Example User"


def test_duplicate_email(client: TestClient) -> None:
    first = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    second = client.post(
        "/api/v1/auth/register",
        json={
            "email": "USER@example.com",
            "password": "password456",
            "full_name": "Another User",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert "password_hash" not in second.json()


def test_invalid_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "password123",
            "full_name": "Example User",
        },
    )

    assert response.status_code == 422


def test_short_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "short",
            "full_name": "Example User",
        },
    )

    assert response.status_code == 422


def test_login_success_sets_httponly_cookie(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    body = _assert_safe_user(response.json())
    assert body["email"] == "user@example.com"

    set_cookie = response.headers.get("set-cookie", "")
    assert settings.COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/" in set_cookie
    assert f"Max-Age={settings.JWT_EXPIRE_MINUTES * 60}" in set_cookie
    assert "Secure" not in set_cookie
    assert f"SameSite={settings.COOKIE_SAMESITE}" in set_cookie or f"samesite={settings.COOKIE_SAMESITE}" in set_cookie.lower()


def test_auth_cookie_is_not_readable_as_document_cookie_name_in_json(client: TestClient) -> None:
    """API JSON must never echo the JWT cookie value or password hash."""
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    token = login.cookies.get(settings.COOKIE_NAME)
    assert token

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    encoded = me.text
    assert token not in encoded
    assert "password_hash" not in encoded
    assert settings.COOKIE_NAME not in encoded


def test_invalid_credentials(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    missing_user = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "password123"},
    )
    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert missing_user.status_code == 401
    assert missing_user.json() == {"detail": "Invalid email or password."}
    assert wrong_password.status_code == 401
    assert wrong_password.json() == {"detail": "Invalid email or password."}
    assert "password_hash" not in missing_user.json()


def test_logout_clears_cookie(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )

    logout = client.post("/api/v1/auth/logout")
    me = client.get("/api/v1/auth/me")
    brands = client.get("/api/v1/brands")

    assert logout.status_code == 200
    assert logout.json() == {"status": "ok"}
    assert settings.COOKIE_NAME in logout.headers.get("set-cookie", "")
    assert me.status_code == 401
    assert brands.status_code == 401


def test_logout_is_safe_when_already_logged_out(client: TestClient) -> None:
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_authenticated_me(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    body = _assert_safe_user(response.json())
    assert body["email"] == "user@example.com"
    assert body["full_name"] == "Example User"


def test_unauthenticated_me(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert "password_hash" not in response.json()


def test_inactive_user_rejection(client: TestClient, db: Session) -> None:
    inactive = User(
        email="inactive@example.com",
        password_hash=hash_password("password123"),
        full_name="Inactive User",
        is_active=False,
    )
    db.add(inactive)
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "password123"},
    )
    me = client.get("/api/v1/auth/me")

    assert login.status_code == 401
    assert login.json() == {"detail": "Invalid email or password."}
    assert me.status_code == 401


def test_secure_cookie_flag_follows_settings(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    client.post("/api/v1/auth/register", json={**REGISTER_PAYLOAD, "email": "secure@example.com"})
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "secure@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "Secure" in set_cookie
