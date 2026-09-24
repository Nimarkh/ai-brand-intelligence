"""Persist Entity Strength onto the Audit row.

Updates only:
  - audit.entity_score

Never modifies overall_score, website_score, seo_score, or ai_visibility_score.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.ai import AiQuery
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.website import WebsitePage
from app.services.entity import (
    AiResponseInput,
    EntityIntelligenceEngine,
    EntityStatus,
    EntityStrengthScore,
    PageInput,
    quantize_score,
)
from app.services.entity.extraction import ai_input_from_row, page_input_from_row

logger = logging.getLogger("app.entity")


@dataclass(frozen=True)
class EntityPersistResult:
    audit_id: UUID
    result: EntityStrengthScore


def run_entity_calculation(db: Session, audit: Audit, brand: Brand) -> EntityPersistResult:
    pages, responses = _load_inputs(db, audit.id)
    scored = EntityIntelligenceEngine().score(
        brand_name=brand.name,
        pages=pages,
        responses=responses,
        website_url=brand.website_url,
    )

    try:
        if scored.status == EntityStatus.UNAVAILABLE:
            audit.entity_score = None
        else:
            audit.entity_score = quantize_score(scored.overall_score)
        from app.services.recommendation_service import clear_recommendations

        clear_recommendations(db, audit.id)
        db.commit()
        db.refresh(audit)
    except Exception:
        db.rollback()
        logger.exception("entity_persist_failed audit_id=%s", audit.id)
        raise

    logger.info(
        "entity_calculated audit_id=%s status=%s score=%s",
        audit.id,
        scored.status.value,
        audit.entity_score,
    )
    return EntityPersistResult(audit_id=audit.id, result=scored)


def load_entity_snapshot(db: Session, audit: Audit, brand: Brand) -> EntityStrengthScore:
    """Return entity result for GET.

    If ``entity_score`` is null (never calculated, cleared, or UNAVAILABLE),
    return UNAVAILABLE with evidence counts — do not fabricate a score.
    When persisted, recompute the explainable breakdown from current data.
    """
    pages, responses = _load_inputs(db, audit.id)
    live = EntityIntelligenceEngine().score(
        brand_name=brand.name,
        pages=pages,
        responses=responses,
        website_url=brand.website_url,
    )

    if audit.entity_score is None:
        if live.status == EntityStatus.UNAVAILABLE:
            return live
        return _not_calculated(live)

    return live


def clear_entity_score(audit: Audit) -> None:
    """Invalidate stale entity strength after crawl or AI query snapshot replacement."""
    audit.entity_score = None


def _not_calculated(live: EntityStrengthScore) -> EntityStrengthScore:
    from app.services.entity.models import ComponentScore, EntityMetrics
    from app.services.entity.weights import ENTITY_WEIGHTS

    components = tuple(
        ComponentScore(
            name=name,
            score=None,
            status=EntityStatus.UNAVAILABLE,
            weight=weight,
            effective_weight=None,
            sample_size=0,
        )
        for name, weight in ENTITY_WEIGHTS.items()
    )
    return EntityStrengthScore(
        overall_score=None,
        status=EntityStatus.UNAVAILABLE,
        metrics=EntityMetrics(
            title_presence_rate=None,
            meta_presence_rate=None,
            title_consistency=None,
            canonical_consistency=None,
            schema_consistency=None,
            entity_schema_coverage=None,
            schema_quality=None,
            ai_mention_rate=None,
            ai_position_score=None,
        ),
        components=components,
        evidence=live.evidence,
        notes=(
            "Entity Strength has not been calculated yet for this audit.",
            "This score evaluates signals found on the audited website and analyzed AI "
            "responses. It does not verify Google Knowledge Graph, Wikidata, Wikipedia, "
            "or third-party entity databases.",
        ),
    )


def _load_inputs(
    db: Session, audit_id: UUID
) -> tuple[list[PageInput], list[AiResponseInput]]:
    page_rows = list(
        db.scalars(
            select(WebsitePage)
            .where(WebsitePage.audit_id == audit_id)
            .order_by(WebsitePage.created_at.asc(), WebsitePage.id.asc())
        ).all()
    )
    pages = [
        page_input_from_row(
            page_id=row.id,
            url=row.url,
            title=row.title,
            meta_description=row.meta_description,
            canonical_url=row.canonical_url,
            has_schema=row.has_schema,
            schema_types=row.schema_types,
        )
        for row in page_rows
    ]

    queries = list(
        db.scalars(
            select(AiQuery)
            .where(AiQuery.audit_id == audit_id)
            .options(selectinload(AiQuery.responses))
            .order_by(AiQuery.created_at.asc(), AiQuery.id.asc())
        ).all()
    )
    responses: list[AiResponseInput] = []
    for query in queries:
        if not query.responses:
            continue
        row = query.responses[0]
        responses.append(
            ai_input_from_row(
                response_id=row.id,
                brand_mentioned=row.brand_mentioned,
                brand_position=row.brand_position,
            )
        )
    return pages, responses
