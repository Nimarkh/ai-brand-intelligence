from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register mappers before table setup
from app.core.database import get_db
from app.core.middleware import reset_auth_rate_limits
from app.main import app
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.user import User
from app.models.website import SeoFinding, WebsitePage
from app.models.ai import AiQuery, AiResponse
from app.models.recommendation import Recommendation
from app.models.report import Report


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw) -> str:  # noqa: ANN001
    return "JSON"


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


@pytest.fixture(autouse=True)
def _reset_auth_rate_limits() -> Generator[None, None, None]:
    """TestClient shares one client IP; clear in-process auth rate buckets each test."""
    reset_auth_rate_limits()
    yield
    reset_auth_rate_limits()


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    User.__table__.create(bind=engine)
    Brand.__table__.create(bind=engine)
    Audit.__table__.create(bind=engine)
    WebsitePage.__table__.create(bind=engine)
    SeoFinding.__table__.create(bind=engine)
    AiQuery.__table__.create(bind=engine)
    AiResponse.__table__.create(bind=engine)
    Recommendation.__table__.create(bind=engine)
    Report.__table__.create(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Report.__table__.drop(bind=engine)
        Recommendation.__table__.drop(bind=engine)
        AiResponse.__table__.drop(bind=engine)
        AiQuery.__table__.drop(bind=engine)
        SeoFinding.__table__.drop(bind=engine)
        WebsitePage.__table__.drop(bind=engine)
        Audit.__table__.drop(bind=engine)
        Brand.__table__.drop(bind=engine)
        User.__table__.drop(bind=engine)


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db
        finally:
            db.expire_all()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
