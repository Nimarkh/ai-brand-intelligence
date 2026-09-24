"""Persist SEO analysis results for an owned audit.

Idempotency: before inserting new findings, existing SeoFinding rows for the
audit are deleted. Other audits are not touched. Score columns are never written.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.website import SeoFinding, WebsitePage
from app.services.crawler.url_utils import normalize_url, origin_root
from app.services.seo_analyzer import AnalyzerThresholds, FindingResult, PageSnapshot, SEOAnalyzer

logger = logging.getLogger("app.seo_analyzer")


@dataclass(frozen=True)
class SeoAnalyzeResult:
    audit_id: UUID
    findings_count: int
    status: str = "COMPLETED"


def thresholds_from_settings() -> AnalyzerThresholds:
    return AnalyzerThresholds(
        title_max_length=settings.SEO_TITLE_MAX_LENGTH,
        title_min_length=settings.SEO_TITLE_MIN_LENGTH,
        meta_description_max_length=settings.SEO_META_DESCRIPTION_MAX_LENGTH,
        meta_description_min_length=settings.SEO_META_DESCRIPTION_MIN_LENGTH,
        low_word_count=settings.SEO_LOW_WORD_COUNT,
        slow_response_ms=settings.SEO_SLOW_RESPONSE_MS,
    )


def build_analyzer() -> SEOAnalyzer:
    return SEOAnalyzer(thresholds_from_settings())


def run_seo_analysis(db: Session, audit: Audit, brand: Brand) -> SeoAnalyzeResult:
    """Load pages, analyze in memory, then replace findings in one transaction.

    Does not change Audit.status. COMPLETED still means the crawl finished.
    """
    pages = list(
        db.scalars(
            select(WebsitePage)
            .where(WebsitePage.audit_id == audit.id)
            .order_by(WebsitePage.id.asc())
        ).all()
    )
    snapshots = [_to_snapshot(page) for page in pages]
    crawl_origin = _crawl_origin(brand.website_url)

    analyzer = build_analyzer()
    findings = analyzer.analyze(snapshots, crawl_origin=crawl_origin)

    try:
        db.execute(delete(SeoFinding).where(SeoFinding.audit_id == audit.id))
        from app.services.recommendation_service import clear_recommendations

        clear_recommendations(db, audit.id)
        for finding in findings:
            db.add(_to_row(audit.id, finding))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("seo_analysis_persist_failed audit_id=%s", audit.id)
        raise

    logger.info(
        "seo_analysis_completed audit_id=%s findings_count=%s",
        audit.id,
        len(findings),
    )
    return SeoAnalyzeResult(audit_id=audit.id, findings_count=len(findings), status="COMPLETED")


def list_seo_findings(db: Session, audit_id: UUID) -> list[SeoFinding]:
    """Return findings ordered by severity (HIGH→INFO), then page_id, category, created_at."""
    rows = list(
        db.scalars(
            select(SeoFinding)
            .options(selectinload(SeoFinding.page))
            .where(SeoFinding.audit_id == audit_id)
        ).all()
    )
    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}

    def sort_key(row: SeoFinding) -> tuple:
        return (
            severity_rank.get(row.severity.value if hasattr(row.severity, "value") else str(row.severity), 99),
            str(row.page_id) if row.page_id is not None else "",
            row.category,
            row.created_at,
            str(row.id),
        )

    rows.sort(key=sort_key)
    return rows


def finding_count(db: Session, audit_id: UUID) -> int:
    from sqlalchemy import func

    return int(
        db.scalar(select(func.count()).select_from(SeoFinding).where(SeoFinding.audit_id == audit_id)) or 0
    )


def _to_snapshot(page: WebsitePage) -> PageSnapshot:
    return PageSnapshot(
        id=page.id,
        url=page.url,
        status_code=page.status_code,
        title=page.title,
        meta_description=page.meta_description,
        canonical_url=page.canonical_url,
        word_count=page.word_count,
        h1_count=page.h1_count,
        has_schema=page.has_schema,
        load_time_ms=page.load_time_ms,
    )


def _to_row(audit_id: UUID, finding: FindingResult) -> SeoFinding:
    return SeoFinding(
        audit_id=audit_id,
        page_id=finding.page_id,
        category=finding.category,
        severity=finding.severity,
        title=finding.title,
        description=finding.description,
        recommendation=finding.recommendation,
    )


def _crawl_origin(website_url: str | None) -> str | None:
    if not website_url:
        return None
    normalized = normalize_url(website_url)
    if normalized is None:
        return None
    return origin_root(normalized)
