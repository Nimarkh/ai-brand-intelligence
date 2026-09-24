from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, engine, get_db, sqlalchemy_database_url
from app.models import (
    AiQuery,
    AiResponse,
    Audit,
    Brand,
    Recommendation,
    Report,
    SeoFinding,
    User,
    WebsitePage,
)

EXPECTED_TABLES = {
    "users",
    "brands",
    "audits",
    "website_pages",
    "seo_findings",
    "ai_queries",
    "ai_responses",
    "recommendations",
    "reports",
}

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_models_can_be_imported() -> None:
    assert User.__tablename__ == "users"
    assert Brand.__tablename__ == "brands"
    assert Audit.__tablename__ == "audits"
    assert WebsitePage.__tablename__ == "website_pages"
    assert SeoFinding.__tablename__ == "seo_findings"
    assert AiQuery.__tablename__ == "ai_queries"
    assert AiResponse.__tablename__ == "ai_responses"
    assert Recommendation.__tablename__ == "recommendations"
    assert Report.__tablename__ == "reports"


def test_metadata_contains_expected_tables() -> None:
    assert EXPECTED_TABLES <= set(Base.metadata.tables)
    assert "chat_sessions" not in Base.metadata.tables
    assert "chat_messages" not in Base.metadata.tables


def test_uuid_primary_keys_and_timestamps() -> None:
    assert str(User.__table__.c.id.type) == "UUID"
    assert User.__table__.c.created_at.type.timezone is True
    assert User.__table__.c.updated_at.type.timezone is True
    assert WebsitePage.__table__.c.created_at.type.timezone is True
    assert "updated_at" not in Audit.__table__.c


def test_jsonb_schema_types_and_nullable_scores() -> None:
    assert str(WebsitePage.__table__.c.schema_types.type) == "JSONB"
    assert Audit.__table__.c.overall_score.nullable is True
    assert SeoFinding.__table__.c.page_id.nullable is True
    assert AiResponse.__table__.c.brand_position.nullable is True
    assert AiResponse.__table__.c.semantic_alignment.nullable is True
    assert AiResponse.__table__.c.latency_ms.nullable is True


def test_core_foreign_keys() -> None:
    brand_fks = {fk.target_fullname for fk in Brand.__table__.c.owner_id.foreign_keys}
    audit_fks = {fk.target_fullname for fk in Audit.__table__.c.brand_id.foreign_keys}
    page_fks = {fk.target_fullname for fk in WebsitePage.__table__.c.audit_id.foreign_keys}
    finding_page_fks = {fk.target_fullname for fk in SeoFinding.__table__.c.page_id.foreign_keys}
    response_fks = {fk.target_fullname for fk in AiResponse.__table__.c.query_id.foreign_keys}

    assert "users.id" in brand_fks
    assert "brands.id" in audit_fks
    assert "audits.id" in page_fks
    assert "website_pages.id" in finding_page_fks
    assert "ai_queries.id" in response_fks


def test_email_is_unique() -> None:
    assert User.__table__.c.email.unique is True


def test_database_url_uses_psycopg_driver() -> None:
    assert sqlalchemy_database_url("postgresql://u:p@db:5432/app") == "postgresql+psycopg://u:p@db:5432/app"
    assert sqlalchemy_database_url("postgres://u:p@localhost/app") == "postgresql+psycopg://u:p@localhost/app"
    assert sqlalchemy_database_url("postgresql+psycopg://u:p@localhost/app").startswith("postgresql+psycopg://")


def test_get_db_is_a_session_generator() -> None:
    assert callable(get_db)
    generator = get_db()
    assert isinstance(generator, Iterator)


def test_alembic_configuration_is_valid() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()

    assert len(heads) == 1
    assert heads[0] == "0001_initial_schema"
    assert list(script.walk_revisions())


def _postgres_available() -> bool:
    if not settings.DATABASE_URL.startswith(("postgresql://", "postgres://", "postgresql+")):
        return False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def test_migrated_postgres_tables() -> None:
    if not _postgres_available():
        pytest.skip("PostgreSQL is not available")

    inspector = inspect(engine)
    assert EXPECTED_TABLES <= set(inspector.get_table_names())


def test_get_db_yields_and_closes_session() -> None:
    if not _postgres_available():
        pytest.skip("PostgreSQL is not available")

    generator = get_db()
    session = next(generator)
    assert isinstance(session, Session)
    session.execute(text("SELECT 1"))
    generator.close()
    assert not session.is_active
