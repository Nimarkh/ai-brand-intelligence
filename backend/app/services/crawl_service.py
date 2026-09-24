from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.enums import AuditStatus
from app.models.website import WebsitePage
from app.services.crawler import CrawlContext, CrawlLimits, WebsiteCrawler, build_client
from app.services.crawler.models import CrawledPage, CrawlStartError
from app.services.crawler.url_utils import endpoint_is_allowed, normalize_url

logger = logging.getLogger("app.crawler")


class BrandWebsiteMissingError(Exception):
    """The brand has no website URL. The audit status is left unchanged."""


class CrawlAlreadyRunningError(Exception):
    """This audit is already RUNNING."""


class CrawlFailedError(Exception):
    """The crawl failed. The audit is already marked FAILED. Safe for API mapping."""


@dataclass(frozen=True)
class CrawlRunResult:
    audit_id: UUID
    status: AuditStatus
    pages_crawled: int


def limits_from_settings() -> CrawlLimits:
    return CrawlLimits(
        max_pages=settings.CRAWLER_MAX_PAGES,
        max_depth=settings.CRAWLER_MAX_DEPTH,
        timeout_seconds=settings.CRAWLER_REQUEST_TIMEOUT_SECONDS,
        delay_seconds=settings.CRAWLER_DELAY_SECONDS,
        max_response_bytes=settings.CRAWLER_MAX_RESPONSE_BYTES,
        user_agent=settings.CRAWLER_USER_AGENT,
        max_redirects=settings.CRAWLER_MAX_REDIRECTS,
    )


def build_crawler(limits: CrawlLimits | None = None) -> WebsiteCrawler:
    resolved = limits or limits_from_settings()
    return WebsiteCrawler(resolved, build_client(resolved))


def create_audit(db: Session, brand: Brand) -> Audit:
    """Create an empty audit snapshot. Scores stay null. Nothing is crawled."""
    audit = Audit(brand_id=brand.id, status=AuditStatus.PENDING)
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def get_owned_audit(db: Session, owner_id: UUID, audit_id: UUID) -> Audit | None:
    """Return the audit only when its brand belongs to owner_id."""
    return db.scalar(
        select(Audit)
        .join(Brand, Brand.id == Audit.brand_id)
        .where(Audit.id == audit_id, Brand.owner_id == owner_id)
    )


def list_brand_audits(db: Session, brand_id: UUID, *, limit: int) -> list[Audit]:
    return list(
        db.scalars(
            select(Audit)
            .where(Audit.brand_id == brand_id)
            .order_by(Audit.created_at.desc(), Audit.id.desc())
            .limit(limit)
        ).all()
    )


def page_count(db: Session, audit_id: UUID) -> int:
    return int(
        db.scalar(select(func.count()).select_from(WebsitePage).where(WebsitePage.audit_id == audit_id)) or 0
    )


def run_crawl(db: Session, audit: Audit, brand: Brand, crawler: WebsiteCrawler) -> CrawlRunResult:
    """Run a bounded crawl and store a fresh WebsitePage snapshot for this audit.

    The database transaction is committed before HTTP begins and opened again
    only to write results. Score columns website/seo/overall/ai_visibility are
    not modified. ``entity_score`` is cleared so stale Entity Strength is not
    shown against a new page snapshot.

    Recrawl deletes this audit's pages once the start URL is allowed, then
    inserts the new snapshot. Other audits are not touched. A rejected start
    URL marks the audit FAILED and leaves any previous pages in place.
    """
    if not brand.website_url:
        raise BrandWebsiteMissingError
    if audit.status == AuditStatus.RUNNING:
        raise CrawlAlreadyRunningError

    started = time.perf_counter()
    now = datetime.now(timezone.utc)
    audit.status = AuditStatus.RUNNING
    audit.started_at = now
    audit.completed_at = None
    from app.services.entity_service import clear_entity_score
    from app.services.recommendation_service import clear_recommendations

    clear_entity_score(audit)
    clear_recommendations(db, audit.id)
    db.commit()
    logger.info("crawl_running audit_id=%s brand_id=%s", audit.id, brand.id)

    try:
        normalized = normalize_url(brand.website_url)
        if normalized is None or not endpoint_is_allowed(normalized, crawler.resolver):
            raise CrawlStartError("Start URL destination is not allowed.")

        db.execute(delete(WebsitePage).where(WebsitePage.audit_id == audit.id))
        db.commit()

        result = crawler.crawl(
            brand.website_url,
            CrawlContext(audit_id=str(audit.id), brand_id=str(brand.id)),
        )
        for page in result.pages:
            db.add(_page_row(audit.id, page))
        audit.status = AuditStatus.COMPLETED
        audit.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(audit)
        logger.info(
            "crawl_completed audit_id=%s brand_id=%s pages_crawled=%s duration_ms=%s",
            audit.id,
            brand.id,
            len(result.pages),
            max(0, int((time.perf_counter() - started) * 1000)),
        )
        return CrawlRunResult(
            audit_id=audit.id,
            status=audit.status,
            pages_crawled=len(result.pages),
        )
    except Exception as exc:
        db.rollback()
        audit.status = AuditStatus.FAILED
        audit.completed_at = datetime.now(timezone.utc)
        db.commit()
        if isinstance(exc, CrawlStartError):
            logger.warning("crawl_rejected audit_id=%s brand_id=%s", audit.id, brand.id)
        else:
            logger.exception("crawl_failed audit_id=%s brand_id=%s", audit.id, brand.id)
        raise CrawlFailedError from None


def _page_row(audit_id: UUID, page: CrawledPage) -> WebsitePage:
    schema_types = page.schema_types if page.has_schema else None
    return WebsitePage(
        audit_id=audit_id,
        url=page.url,
        status_code=page.status_code,
        title=page.title,
        meta_description=page.meta_description,
        canonical_url=page.canonical_url,
        word_count=page.word_count,
        h1_count=page.h1_count,
        h2_count=page.h2_count,
        has_schema=page.has_schema,
        schema_types=schema_types,
        load_time_ms=page.load_time_ms,
    )
