"""Persist Audit Engine scores onto the existing Audit row.

Populates only overall_score, website_score, and seo_score.
Leaves ai_visibility_score, entity_score, and semantic_score null.

overall_score is always PROVISIONAL in Phase 09 (AI Visibility and Entity
Strength are not available). UNAVAILABLE audits store null score columns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import Audit
from app.models.website import SeoFinding, WebsitePage
from app.services.audit_engine import AuditEngine, FindingInput, ScoreStatus
from app.services.audit_engine.models import (
    AuditScoreResult,
    ComponentScore,
    DimensionScore,
)
from app.services.audit_engine.scoring import quantize_score
from app.services.crawl_service import page_count

logger = logging.getLogger("app.audit_engine")


@dataclass(frozen=True)
class ScorePersistResult:
    audit_id: UUID
    status: ScoreStatus
    result: object  # AuditScoreResult


def run_score_calculation(db: Session, audit: Audit) -> ScorePersistResult:
    """Load pages/findings, score in memory, persist score columns."""
    pages = list(
        db.scalars(
            select(WebsitePage.id).where(WebsitePage.audit_id == audit.id).order_by(WebsitePage.id.asc())
        ).all()
    )
    finding_rows = list(
        db.scalars(select(SeoFinding).where(SeoFinding.audit_id == audit.id)).all()
    )
    findings = [
        FindingInput(
            id=row.id,
            category=row.category,
            severity=row.severity.value if hasattr(row.severity, "value") else str(row.severity),
            title=row.title,
            page_id=row.page_id,
        )
        for row in finding_rows
    ]

    engine = AuditEngine()
    scored = engine.score(page_ids=list(pages), findings=findings)

    try:
        if scored.status == ScoreStatus.UNAVAILABLE:
            audit.overall_score = None
            audit.website_score = None
            audit.seo_score = None
        else:
            audit.website_score = quantize_score(scored.website_health.score)
            audit.seo_score = quantize_score(scored.seo_score.score)
            audit.overall_score = quantize_score(scored.overall.score)
        # Never touch AI / entity / semantic in Phase 09
        db.commit()
        db.refresh(audit)
    except Exception:
        db.rollback()
        logger.exception("score_persist_failed audit_id=%s", audit.id)
        raise

    logger.info(
        "score_calculated audit_id=%s status=%s website=%s seo=%s overall=%s",
        audit.id,
        scored.status.value,
        audit.website_score,
        audit.seo_score,
        audit.overall_score,
    )
    return ScorePersistResult(audit_id=audit.id, status=scored.status, result=scored)


def load_score_snapshot(db: Session, audit: Audit):
    """Rebuild explainable score structure from current pages/findings and stored columns.

    GET does not recalculate persistence. When columns are null and pages exist,
    still compute an in-memory explanation if requested, but the API uses stored
    values when present and UNAVAILABLE when never calculated and no pages.

    For GET: if overall/website/seo are all null:
      - zero pages → UNAVAILABLE
      - pages exist → UNAVAILABLE (not yet calculated) — do not auto-score
    """
    from app.services.audit_engine.models import (
        AuditScoreResult,
        ComponentScore,
        DimensionScore,
        ScoreStatus,
    )

    pages_n = page_count(db, audit.id)
    finding_rows = list(
        db.scalars(select(SeoFinding).where(SeoFinding.audit_id == audit.id)).all()
    )
    findings = [
        FindingInput(
            id=row.id,
            category=row.category,
            severity=row.severity.value if hasattr(row.severity, "value") else str(row.severity),
            title=row.title,
            page_id=row.page_id,
        )
        for row in finding_rows
    ]

    has_persisted = any(
        value is not None
        for value in (audit.overall_score, audit.website_score, audit.seo_score)
    )

    if not has_persisted:
        # Not calculated yet (or unavailable empty audit)
        engine = AuditEngine()
        page_ids = list(
            db.scalars(select(WebsitePage.id).where(WebsitePage.audit_id == audit.id)).all()
        )
        # For explainability of counts only when pages exist but unscored —
        # status remains UNAVAILABLE until POST calculate-score.
        if pages_n < 1:
            return engine.score(page_ids=[], findings=findings)

        # Unscored but has pages: return UNAVAILABLE shell with counts
        affected = len({f.page_id for f in findings if f.page_id is not None})
        empty = ComponentScore(
            name="technical",
            score=None,
            status=ScoreStatus.UNAVAILABLE,
            findings_count=0,
            affected_pages=0,
        )
        return AuditScoreResult(
            technical=empty,
            seo=ComponentScore(name="seo", score=None, status=ScoreStatus.UNAVAILABLE),
            content=ComponentScore(name="content", score=None, status=ScoreStatus.UNAVAILABLE),
            structured_data=ComponentScore(
                name="structured_data", score=None, status=ScoreStatus.UNAVAILABLE
            ),
            website_health=DimensionScore(score=None, status=ScoreStatus.UNAVAILABLE),
            seo_score=DimensionScore(score=None, status=ScoreStatus.UNAVAILABLE),
            overall=DimensionScore(score=None, status=ScoreStatus.UNAVAILABLE),
            analyzable_pages=pages_n,
            findings_count=len(findings),
            affected_pages=affected,
            status=ScoreStatus.UNAVAILABLE,
        )

    # Rebuild full explanation from current data (deterministic), then overlay
    # persisted top-level values so GET matches what was stored.
    engine = AuditEngine()
    page_ids = list(
        db.scalars(select(WebsitePage.id).where(WebsitePage.audit_id == audit.id)).all()
    )
    live = engine.score(page_ids=page_ids, findings=findings)

    # Prefer persisted dimension values when present
    website = (
        Decimal(str(audit.website_score))
        if audit.website_score is not None
        else live.website_health.score
    )
    seo = Decimal(str(audit.seo_score)) if audit.seo_score is not None else live.seo_score.score
    overall = (
        Decimal(str(audit.overall_score)) if audit.overall_score is not None else live.overall.score
    )

    return AuditScoreResult(
        technical=live.technical,
        seo=live.seo,
        content=live.content,
        structured_data=live.structured_data,
        website_health=DimensionScore(score=website, status=ScoreStatus.AVAILABLE),
        seo_score=DimensionScore(score=seo, status=ScoreStatus.AVAILABLE),
        overall=DimensionScore(score=overall, status=ScoreStatus.PROVISIONAL),
        analyzable_pages=live.analyzable_pages,
        findings_count=live.findings_count,
        affected_pages=live.affected_pages,
        status=ScoreStatus.PROVISIONAL,
    )
