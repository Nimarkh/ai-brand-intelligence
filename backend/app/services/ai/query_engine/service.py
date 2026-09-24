"""Orchestrate AI query generation, persistence, and execution."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, settings
from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.brand import Brand
from app.services.ai.models import AIProviderError, AIRequestError
from app.services.ai.provider import AIProvider
from app.services.ai.query_engine.executor import QueryExecutor
from app.services.ai.query_engine.extraction import extract_response_signals
from app.services.ai.query_engine.generator import QueryGenerator
from app.services.ai.query_engine.models import BrandContext, QueryRunSummary

# Freshness: invalidating visibility when the AI query snapshot is replaced.
# Imported lazily-safe from the visibility service module.
from app.services.ai_visibility_service import clear_visibility_scores
from app.services.entity_service import clear_entity_score
from app.services.recommendation_service import clear_recommendations

logger = logging.getLogger("app.ai.query_engine")


class InsufficientBrandContextError(ValueError):
    """Brand lacks required fields for meaningful query generation."""


def brand_context_from_brand(brand: Brand) -> BrandContext:
    name = (brand.name or "").strip()
    industry = (brand.industry or "").strip()
    if not name or not industry:
        raise InsufficientBrandContextError(
            "Brand name and industry are required before running AI query analysis."
        )
    return BrandContext(
        name=name,
        industry=industry,
        country=(brand.country or None),
        target_market=(brand.target_market or None),
        description=(brand.description or None),
        website_url=(brand.website_url or None),
    )


async def run_ai_query_analysis(
    db: Session,
    audit: Audit,
    brand: Brand,
    provider: AIProvider,
    *,
    config: Settings | None = None,
) -> QueryRunSummary:
    """Replace the audit's AI query snapshot, execute queries, persist responses.

    Re-run behavior:
        Deletes existing ``ai_responses`` and ``ai_queries`` for this audit, then
        generates a fresh deterministic set.         Clears ``audit.ai_visibility_score``, ``audit.semantic_score``, and
        ``audit.entity_score`` so stale Phase 12/13 results are not shown.
        Does not touch WebsitePage, SeoFinding, overall/website/seo scores, or
        AuditStatus.

    Partial failures:
        Provider errors keep the query row and skip response creation. The
        operation still completes with status COMPLETED.
    """
    cfg = config or settings
    max_queries = cfg.AI_QUERY_MAX_PER_AUDIT
    context = brand_context_from_brand(brand)
    generated = QueryGenerator().generate(context, max_queries=max_queries)

    _replace_query_snapshot(db, audit.id)
    clear_visibility_scores(audit)
    clear_entity_score(audit)
    clear_recommendations(db, audit.id)

    query_rows: list[AiQuery] = []
    for item in generated:
        row = AiQuery(
            audit_id=audit.id,
            query_text=item.query_text,
            category=item.category,
        )
        db.add(row)
        query_rows.append(row)
    db.flush()

    executor = QueryExecutor(provider)
    succeeded = 0
    failed = 0

    for row in query_rows:
        try:
            ai_response = await executor.execute(row.query_text)
        except (AIRequestError, AIProviderError):
            failed += 1
            continue
        except Exception:
            logger.exception(
                "ai_query_unexpected_failure audit_id=%s query_id=%s",
                audit.id,
                row.id,
            )
            failed += 1
            continue

        signals = extract_response_signals(ai_response.text, context.name)
        db.add(
            AiResponse(
                query_id=row.id,
                provider=ai_response.provider,
                model=ai_response.model,
                response_text=ai_response.text,
                brand_mentioned=signals.brand_mentioned,
                brand_position=signals.brand_position,
                citation_found=signals.citation_found,
                semantic_alignment=None,
                latency_ms=ai_response.latency_ms,
            )
        )
        succeeded += 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("ai_query_persist_failed audit_id=%s", audit.id)
        raise

    logger.info(
        "ai_query_run_completed audit_id=%s generated=%s succeeded=%s failed=%s",
        audit.id,
        len(query_rows),
        succeeded,
        failed,
    )
    return QueryRunSummary(
        audit_id=audit.id,
        queries_generated=len(query_rows),
        responses_succeeded=succeeded,
        responses_failed=failed,
        status="COMPLETED",
    )


def list_ai_queries(db: Session, audit_id: UUID) -> list[AiQuery]:
    stmt = (
        select(AiQuery)
        .where(AiQuery.audit_id == audit_id)
        .options(selectinload(AiQuery.responses))
        .order_by(AiQuery.created_at.asc(), AiQuery.id.asc())
    )
    return list(db.scalars(stmt).all())


def get_ai_query(db: Session, audit_id: UUID, query_id: UUID) -> AiQuery | None:
    stmt = (
        select(AiQuery)
        .where(AiQuery.id == query_id, AiQuery.audit_id == audit_id)
        .options(selectinload(AiQuery.responses))
    )
    return db.scalars(stmt).first()


def _replace_query_snapshot(db: Session, audit_id: UUID) -> None:
    """Delete existing queries (and responses) for one audit."""
    existing_ids = list(
        db.scalars(select(AiQuery.id).where(AiQuery.audit_id == audit_id)).all()
    )
    if existing_ids:
        db.execute(delete(AiResponse).where(AiResponse.query_id.in_(existing_ids)))
        db.execute(delete(AiQuery).where(AiQuery.audit_id == audit_id))
        db.flush()
