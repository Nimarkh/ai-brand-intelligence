"""Phase 22 production configuration validation tests.

Uses Settings() directly (Phase 21 rules). Does not print secret values.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_STRONG_SECRET = "a" * 32
_PROD_DB = "postgresql://brand_app:placeholder@postgres:5432/brand_intelligence"
_PROD_CORS = "https://app.example.com"


def _production_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ENVIRONMENT": "production",
        "JWT_SECRET": _STRONG_SECRET,
        "COOKIE_SECURE": True,
        "COOKIE_SAMESITE": "lax",
        "CORS_ORIGINS": _PROD_CORS,
        "DATABASE_URL": _PROD_DB,
    }
    base.update(overrides)
    return base


def test_valid_production_config_passes() -> None:
    cfg = Settings(**_production_kwargs())
    assert cfg.is_production
    assert cfg.COOKIE_SECURE is True
    assert cfg.COOKIE_SAMESITE == "lax"
    assert "*" not in cfg.cors_origin_list


def test_weak_known_jwt_secret_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(JWT_SECRET="change-me-in-development-only!!!"))


def test_short_jwt_secret_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(JWT_SECRET="short-but-not-default"))


def test_cookie_secure_false_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(COOKIE_SECURE=False))


def test_wildcard_cors_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(CORS_ORIGINS="*"))


def test_empty_cors_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(CORS_ORIGINS="  ,  "))


def test_missing_database_url_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(DATABASE_URL=""))


def test_sqlite_database_fails_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(DATABASE_URL="sqlite:///./prod.db"))


def test_invalid_database_scheme_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(DATABASE_URL="mysql://user:pass@db:3306/app"))


def test_invalid_samesite_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(COOKIE_SAMESITE="invalid"))


def test_invalid_environment_values_fail() -> None:
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(AI_PROVIDER=""))
    with pytest.raises(ValidationError):
        Settings(**_production_kwargs(CRAWLER_USER_AGENT="   "))
