"""Persist recommendation snapshots and load audit evidence.

Updates only the ``recommendations`` table for an audit.
Never modifies score columns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, settings
from app.models.ai import AiQuery
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.enums import FindingSeverity, RecommendationPriority
from app.models.recommendation import Recommendation
from app.models.website import SeoFinding, WebsitePage
from app.services.ai.visibility import AIVisibilityEngine, ResponseInput, VisibilityStatus
from app.services.audit_engine import AuditEngine, FindingInput as ScoreFindingInput, ScoreStatus
from app.services.entity import EntityIntelligenceEngine, EntityStatus
from app.services.entity.extraction import ai_input_from_row, page_input_from_row
from app.services.recommendations import (
    AuditEvidence,
    FindingEvidence,
    RecommendationCandidate,
    RecommendationsEngine,
)

logger = logging.getLogger("app.recommendations")


@dataclass(frozen=True)
class RecommendationRunSummary:
    audit_id: UUID
    recommendations_generated: int
    high: int
    medium: int
    low: int
    status: str = "COMPLETED"


def run_recommendation_calculation(
    db: Session,
    audit: Audit,
    brand: Brand,
    *,
    config: Settings | None = None,
) -> RecommendationRunSummary:
    cfg = config or settings
    evidence = build_audit_evidence(db, audit, brand)
    candidates = RecommendationsEngine().generate(
        evidence,
        max_recommendations=cfg.RECOMMENDATIONS_MAX_PER_AUDIT,
    )

    try:
        clear_recommendations(db, audit.id)
        for item in candidates:
            db.add(
                Recommendation(
                    audit_id=audit.id,
                    title=item.title,
                    description=item.description,
                    category=item.category.value,
                    priority=item.priority,
                    impact_score=item.impact_score,
                    effort_score=item.effort_score,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("recommendations_persist_failed audit_id=%s", audit.id)
        raise

    high = sum(1 for item in candidates if item.priority == RecommendationPriority.HIGH)
    medium = sum(1 for item in candidates if item.priority == RecommendationPriority.MEDIUM)
    low = sum(1 for item in candidates if item.priority == RecommendationPriority.LOW)
    logger.info(
        "recommendations_calculated audit_id=%s count=%s high=%s medium=%s low=%s",
        audit.id,
        len(candidates),
        high,
        medium,
        low,
    )
    return RecommendationRunSummary(
        audit_id=audit.id,
        recommendations_generated=len(candidates),
        high=high,
        medium=medium,
        low=low,
        status="COMPLETED",
    )


def list_recommendations(db: Session, audit_id: UUID) -> list[Recommendation]:
    rows = list(
        db.scalars(select(Recommendation).where(Recommendation.audit_id == audit_id)).all()
    )
    priority_order = {
        RecommendationPriority.HIGH: 0,
        RecommendationPriority.MEDIUM: 1,
        RecommendationPriority.LOW: 2,
    }

    def sort_key(row: Recommendation) -> tuple:
        return (
            priority_order.get(row.priority, 9),
            -(row.impact_score or Decimal("0")),
            row.effort_score or Decimal("100"),
            row.title or "",
            str(row.id),
        )

    return sorted(rows, key=sort_key)


def clear_recommendations(db: Session, audit_id: UUID) -> None:
    """Delete the recommendation snapshot for one audit (freshness invalidation)."""
    db.execute(delete(Recommendation).where(Recommendation.audit_id == audit_id))
    db.flush()


def build_audit_evidence(db: Session, audit: Audit, brand: Brand) -> AuditEvidence:
    pages = list(
        db.scalars(
            select(WebsitePage)
            .where(WebsitePage.audit_id == audit.id)
            .order_by(WebsitePage.created_at.asc(), WebsitePage.id.asc())
        ).all()
    )
    findings = list(
        db.scalars(select(SeoFinding).where(SeoFinding.audit_id == audit.id)).all()
    )
    finding_evidence = tuple(
        FindingEvidence(
            id=row.id,
            category=row.category,
            severity=row.severity
            if isinstance(row.severity, FindingSeverity)
            else FindingSeverity(str(row.severity)),
            title=row.title,
            page_id=row.page_id,
        )
        for row in findings
    )

    technical = seo_comp = content = structured = None
    scores_available = audit.website_score is not None or audit.seo_score is not None
    if scores_available and pages:
        scored = AuditEngine().score(
            page_ids=[page.id for page in pages],
            findings=[
                ScoreFindingInput(
                    id=f.id,
                    category=f.category,
                    severity=f.severity.value
                    if isinstance(f.severity, FindingSeverity)
                    else str(f.severity),
                    title=f.title,
                    page_id=f.page_id,
                )
                for f in findings
            ],
        )
        if scored.status != ScoreStatus.UNAVAILABLE:
            technical = scored.technical.score
            seo_comp = scored.seo.score
            content = scored.content.score
            structured = scored.structured_data.score

    visibility_available = audit.ai_visibility_score is not None
    mention_score = citation_score = position_score = semantic_score = None
    successful = 0
    mentioning = 0
    mention_rate = None
    if visibility_available:
        queries = list(
            db.scalars(
                select(AiQuery)
                .where(AiQuery.audit_id == audit.id)
                .options(selectinload(AiQuery.responses))
                .order_by(AiQuery.created_at.asc(), AiQuery.id.asc())
            ).all()
        )
        responses: list[ResponseInput] = []
        for query in queries:
            if not query.responses:
                continue
            row = query.responses[0]
            responses.append(
                ResponseInput(
                    query_id=query.id,
                    response_id=row.id,
                    query_text=query.query_text,
                    response_text=row.response_text or "",
                    brand_mentioned=bool(row.brand_mentioned),
                    brand_position=row.brand_position,
                    citation_found=bool(row.citation_found),
                )
            )
        vis = AIVisibilityEngine().score(total_queries=len(queries), responses=responses)
        if vis.status != VisibilityStatus.UNAVAILABLE:
            by_name = {c.name: c.score for c in vis.components}
            mention_score = by_name.get("mention")
            citation_score = by_name.get("citation")
            position_score = by_name.get("position")
            semantic_score = by_name.get("semantic")
            successful = vis.successful_responses
            mentioning = sum(1 for item in responses if item.brand_mentioned)
            mention_rate = vis.metrics.mention_rate

    entity_available = audit.entity_score is not None
    presence = consistency = structured_id = ai_rec = None
    entity_pages = title_hits = meta_hits = 0
    if entity_available:
        page_inputs = [
            page_input_from_row(
                page_id=row.id,
                url=row.url,
                title=row.title,
                meta_description=row.meta_description,
                canonical_url=row.canonical_url,
                has_schema=row.has_schema,
                schema_types=row.schema_types,
            )
            for row in pages
        ]
        queries = list(
            db.scalars(
                select(AiQuery)
                .where(AiQuery.audit_id == audit.id)
                .options(selectinload(AiQuery.responses))
                .order_by(AiQuery.created_at.asc(), AiQuery.id.asc())
            ).all()
        )
        ai_inputs = []
        for query in queries:
            if not query.responses:
                continue
            row = query.responses[0]
            ai_inputs.append(
                ai_input_from_row(
                    response_id=row.id,
                    brand_mentioned=row.brand_mentioned,
                    brand_position=row.brand_position,
                )
            )
        ent = EntityIntelligenceEngine().score(
            brand_name=brand.name,
            pages=page_inputs,
            responses=ai_inputs,
            website_url=brand.website_url,
        )
        if ent.status != EntityStatus.UNAVAILABLE:
            by_name = {c.name: c.score for c in ent.components}
            presence = by_name.get("presence")
            consistency = by_name.get("consistency")
            structured_id = by_name.get("structured_identity")
            ai_rec = by_name.get("ai_recognition")
            entity_pages = ent.evidence.analyzable_pages
            title_hits = ent.evidence.pages_with_brand_in_title
            meta_hits = ent.evidence.pages_with_brand_in_meta

    return AuditEvidence(
        analyzable_pages=len(pages),
        findings=finding_evidence,
        technical_score=technical,
        seo_component_score=seo_comp,
        content_score=content,
        structured_data_score=structured,
        scores_available=scores_available,
        visibility_available=visibility_available,
        mention_score=mention_score,
        citation_score=citation_score,
        position_score=position_score,
        semantic_score=semantic_score,
        successful_ai_responses=successful,
        responses_mentioning_brand=mentioning,
        mention_rate=mention_rate,
        entity_available=entity_available,
        presence_score=presence,
        consistency_score=consistency,
        structured_identity_score=structured_id,
        ai_recognition_score=ai_rec,
        entity_pages=entity_pages,
        pages_with_brand_in_title=title_hits,
        pages_with_brand_in_meta=meta_hits,
    )
