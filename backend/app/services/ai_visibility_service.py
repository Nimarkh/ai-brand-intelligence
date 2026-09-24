"""Persist AI Visibility scores onto the Audit row and response semantic fields.

Updates only:
  - audit.ai_visibility_score
  - audit.semantic_score
  - ai_responses.semantic_alignment

Never modifies overall_score, website_score, or seo_score (Phase 09).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.services.ai.visibility import (
    AIVisibilityEngine,
    AIVisibilityScore,
    ResponseInput,
    VisibilityStatus,
    quantize_score,
)

logger = logging.getLogger("app.ai.visibility")


@dataclass(frozen=True)
class VisibilityPersistResult:
    audit_id: UUID
    result: AIVisibilityScore


def run_visibility_calculation(db: Session, audit: Audit) -> VisibilityPersistResult:
    """Load query/response snapshot, score, persist visibility fields."""
    queries = list(
        db.scalars(
            select(AiQuery)
            .where(AiQuery.audit_id == audit.id)
            .options(selectinload(AiQuery.responses))
            .order_by(AiQuery.created_at.asc(), AiQuery.id.asc())
        ).all()
    )
    inputs = _response_inputs(queries)
    scored = AIVisibilityEngine().score(total_queries=len(queries), responses=inputs)

    try:
        _persist_semantic_alignments(db, scored)
        if scored.status == VisibilityStatus.UNAVAILABLE:
            audit.ai_visibility_score = None
            audit.semantic_score = None
        else:
            audit.ai_visibility_score = quantize_score(scored.overall_score)
            audit.semantic_score = quantize_score(scored.metrics.semantic_score)
        from app.services.recommendation_service import clear_recommendations

        clear_recommendations(db, audit.id)
        db.commit()
        db.refresh(audit)
    except Exception:
        db.rollback()
        logger.exception("ai_visibility_persist_failed audit_id=%s", audit.id)
        raise

    logger.info(
        "ai_visibility_calculated audit_id=%s status=%s score=%s semantic=%s",
        audit.id,
        scored.status.value,
        audit.ai_visibility_score,
        audit.semantic_score,
    )
    return VisibilityPersistResult(audit_id=audit.id, result=scored)


def load_visibility_snapshot(db: Session, audit: Audit) -> AIVisibilityScore:
    """Return visibility for GET.

    If ``ai_visibility_score`` is null (never calculated, cleared after a Phase 11
    re-run, or calculated UNAVAILABLE), return UNAVAILABLE with coverage counts
    from the current snapshot and null metric scores — do not fabricate a score.
    When a score is persisted, recompute the explainable breakdown from the
    current query/response data (deterministic).
    """
    queries = list(
        db.scalars(
            select(AiQuery)
            .where(AiQuery.audit_id == audit.id)
            .options(selectinload(AiQuery.responses))
            .order_by(AiQuery.created_at.asc(), AiQuery.id.asc())
        ).all()
    )
    inputs = _response_inputs(queries)
    live = AIVisibilityEngine().score(total_queries=len(queries), responses=inputs)

    if audit.ai_visibility_score is None:
        if live.status == VisibilityStatus.UNAVAILABLE:
            return live
        return _unavailable_with_coverage(live)

    return live


def _unavailable_with_coverage(live: AIVisibilityScore) -> AIVisibilityScore:
    """Coverage known, but calculation not persisted yet — scores stay null."""
    from app.services.ai.visibility.models import ComponentScore, VisibilityMetrics
    from app.services.ai.visibility.weights import VISIBILITY_WEIGHTS

    components = tuple(
        ComponentScore(
            name=name,
            score=None,
            status=VisibilityStatus.UNAVAILABLE,
            weight=weight,
            effective_weight=None,
            sample_size=0,
        )
        for name, weight in VISIBILITY_WEIGHTS.items()
    )
    return AIVisibilityScore(
        overall_score=None,
        status=VisibilityStatus.UNAVAILABLE,
        metrics=VisibilityMetrics(
            mention_rate=None,
            citation_rate=None,
            average_position=None,
            position_score=None,
            semantic_alignment=None,
            semantic_score=None,
        ),
        components=components,
        total_queries=live.total_queries,
        successful_responses=live.successful_responses,
        failed_responses=live.failed_responses,
        response_coverage=live.response_coverage,
        semantic_by_response_id=(),
    )


def clear_visibility_scores(audit: Audit) -> None:
    """Invalidate stale visibility after AI query snapshot replacement."""
    audit.ai_visibility_score = None
    audit.semantic_score = None


def _response_inputs(queries: list[AiQuery]) -> list[ResponseInput]:
    inputs: list[ResponseInput] = []
    for query in queries:
        if not query.responses:
            continue
        row: AiResponse = query.responses[0]
        inputs.append(
            ResponseInput(
                query_id=query.id,
                response_id=row.id,
                query_text=query.query_text,
                response_text=row.response_text or "",
                brand_mentioned=bool(row.brand_mentioned),
                brand_position=row.brand_position,
                citation_found=bool(row.citation_found),
                semantic_alignment=row.semantic_alignment,
            )
        )
    return inputs


def _persist_semantic_alignments(db: Session, scored: AIVisibilityScore) -> None:
    if not scored.semantic_by_response_id:
        return
    ids = [response_id for response_id, _ in scored.semantic_by_response_id]
    rows = {
        row.id: row
        for row in db.scalars(select(AiResponse).where(AiResponse.id.in_(ids))).all()
    }
    for response_id, value in scored.semantic_by_response_id:
        row = rows.get(response_id)
        if row is None:
            continue
        row.semantic_alignment = value if value is None else Decimal(str(value))
