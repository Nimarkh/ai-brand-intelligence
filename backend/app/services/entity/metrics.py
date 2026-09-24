"""Raw Entity Intelligence metrics from page and AI evidence."""

from __future__ import annotations

from decimal import Decimal

from app.services.ai.visibility.metrics import position_to_score
from app.services.entity.extraction import brand_appears_in_text, origin_of, same_origin
from app.services.entity.models import (
    AiResponseInput,
    EntityEvidence,
    EntityMetrics,
    PageInput,
)
from app.services.entity.weights import (
    ENTITY_RELEVANT_SCHEMA_TYPES,
    ENTITY_SCHEMA_TYPE_WEIGHTS,
    STRONG_ENTITY_SCHEMA_TYPES,
)


def compute_entity_metrics(
    *,
    brand_name: str,
    normalized_brand: str,
    pages: list[PageInput],
    responses: list[AiResponseInput],
    site_origin: str | None,
) -> tuple[EntityMetrics, EntityEvidence]:
    analyzable = len(pages)
    title_hits = 0
    meta_hits = 0
    with_canonical = 0
    same_origin_canonical = 0
    with_schema = 0
    with_entity_schema = 0
    quality_scores: list[Decimal] = []

    for page in pages:
        if brand_appears_in_text(normalized_brand, page.title):
            title_hits += 1
        if brand_appears_in_text(normalized_brand, page.meta_description):
            meta_hits += 1
        if page.canonical_url:
            with_canonical += 1
            if site_origin and same_origin(page.canonical_url, site_origin):
                same_origin_canonical += 1
            elif site_origin is None and same_origin(page.canonical_url, page.url):
                same_origin_canonical += 1
        if page.has_schema or page.schema_types:
            with_schema += 1
        relevant = [t for t in page.schema_types if t in ENTITY_RELEVANT_SCHEMA_TYPES]
        if relevant:
            with_entity_schema += 1
            quality_scores.append(_schema_quality(page.schema_types))

    mentioned = sum(1 for item in responses if item.brand_mentioned)
    positions = [
        Decimal(item.brand_position)
        for item in responses
        if item.brand_mentioned and item.brand_position is not None
    ]
    avg_position = (
        sum(positions, Decimal("0")) / Decimal(len(positions)) if positions else None
    )

    evidence = EntityEvidence(
        analyzable_pages=analyzable,
        pages_with_brand_in_title=title_hits,
        pages_with_brand_in_meta=meta_hits,
        pages_with_canonical=with_canonical,
        pages_with_same_origin_canonical=same_origin_canonical,
        pages_with_schema=with_schema,
        pages_with_entity_schema=with_entity_schema,
        successful_ai_responses=len(responses),
        responses_mentioning_brand=mentioned,
        average_mention_position=_q4(avg_position) if avg_position is not None else None,
        brand_name=brand_name,
        normalized_brand_name=normalized_brand,
        origin=site_origin or (origin_of(pages[0].url) if pages else None),
    )

    if analyzable == 0:
        title_presence = None
        meta_presence = None
        title_consistency = None
        canonical_consistency = None
        schema_consistency = None
        entity_coverage = None
        schema_quality = None
    else:
        n = Decimal(analyzable)
        title_presence = Decimal(title_hits) / n
        meta_presence = Decimal(meta_hits) / n
        title_consistency = title_presence
        canonical_consistency = (
            Decimal(same_origin_canonical) / Decimal(with_canonical)
            if with_canonical > 0
            else None
        )
        schema_consistency = Decimal(with_schema) / n
        entity_coverage = Decimal(with_entity_schema) / n
        schema_quality = (
            sum(quality_scores, Decimal("0")) / Decimal(len(quality_scores))
            if quality_scores
            else Decimal("0")
        )

    if not responses:
        ai_mention = None
        ai_position = None
    else:
        n_resp = Decimal(len(responses))
        ai_mention = Decimal(mentioned) / n_resp
        position_scores = [
            position_to_score(item.brand_position, brand_mentioned=item.brand_mentioned)
            for item in responses
        ]
        ai_position = sum(position_scores, Decimal("0")) / n_resp

    metrics = EntityMetrics(
        title_presence_rate=_q4(title_presence) if title_presence is not None else None,
        meta_presence_rate=_q4(meta_presence) if meta_presence is not None else None,
        title_consistency=_q4(title_consistency) if title_consistency is not None else None,
        canonical_consistency=(
            _q4(canonical_consistency) if canonical_consistency is not None else None
        ),
        schema_consistency=_q4(schema_consistency) if schema_consistency is not None else None,
        entity_schema_coverage=_q4(entity_coverage) if entity_coverage is not None else None,
        schema_quality=_q4(schema_quality) if schema_quality is not None else None,
        ai_mention_rate=_q4(ai_mention) if ai_mention is not None else None,
        ai_position_score=_q1(ai_position) if ai_position is not None else None,
    )
    return metrics, evidence


def _schema_quality(types: tuple[str, ...]) -> Decimal:
    """Best matching type weight for a page, normalized to 0–1."""
    if not types:
        return Decimal("0")
    best = Decimal("0")
    for item in types:
        weight = ENTITY_SCHEMA_TYPE_WEIGHTS.get(item, Decimal("0"))
        if weight > best:
            best = weight
    # Boost slightly when a strong org type is present alongside others.
    if any(item in STRONG_ENTITY_SCHEMA_TYPES for item in types):
        best = max(best, Decimal("0.90"))
    return best


def _q4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def _q1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.1"))
