"""Convert entity metrics into component and overall Entity Strength scores."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.services.entity.models import (
    ComponentScore,
    EntityEvidence,
    EntityMetrics,
    EntityStatus,
    EntityStrengthScore,
)
from app.services.entity.weights import ENTITY_WEIGHTS


def quantize_score(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def clamp_score(value: Decimal) -> Decimal:
    if value < Decimal("0"):
        return Decimal("0")
    if value > Decimal("100"):
        return Decimal("100")
    return value


def score_presence(metrics: EntityMetrics, *, sample_size: int) -> ComponentScore:
    """Presence from title (+ meta when available), average of available rates."""
    rates: list[Decimal] = []
    if metrics.title_presence_rate is not None:
        rates.append(metrics.title_presence_rate)
    if metrics.meta_presence_rate is not None:
        rates.append(metrics.meta_presence_rate)
    if not rates or sample_size < 1:
        return _unavailable("presence", sample_size=0)
    avg = sum(rates, Decimal("0")) / Decimal(len(rates))
    return _available("presence", avg * Decimal("100"), sample_size=sample_size)


def score_consistency(metrics: EntityMetrics, *, sample_size: int) -> ComponentScore:
    """Equal-weight average of available consistency submetrics."""
    parts: list[Decimal] = []
    if metrics.title_consistency is not None:
        parts.append(metrics.title_consistency)
    if metrics.canonical_consistency is not None:
        parts.append(metrics.canonical_consistency)
    if metrics.schema_consistency is not None:
        parts.append(metrics.schema_consistency)
    if not parts or sample_size < 1:
        return _unavailable("consistency", sample_size=0)
    avg = sum(parts, Decimal("0")) / Decimal(len(parts))
    return _available("consistency", avg * Decimal("100"), sample_size=sample_size)


def score_structured_identity(metrics: EntityMetrics, *, sample_size: int) -> ComponentScore:
    """average(entity_schema_coverage, schema_quality) × 100."""
    if sample_size < 1:
        return _unavailable("structured_identity", sample_size=0)
    if metrics.entity_schema_coverage is None or metrics.schema_quality is None:
        return _unavailable("structured_identity", sample_size=0)
    # Zero schema pages → coverage 0 and quality 0 → score 0 (AVAILABLE with data).
    avg = (metrics.entity_schema_coverage + metrics.schema_quality) / Decimal("2")
    return _available("structured_identity", avg * Decimal("100"), sample_size=sample_size)


def score_ai_recognition(metrics: EntityMetrics, *, sample_size: int) -> ComponentScore:
    """average(mention_rate × 100, position_component)."""
    if sample_size < 1 or metrics.ai_mention_rate is None or metrics.ai_position_score is None:
        return _unavailable("ai_recognition", sample_size=0)
    mention_score = metrics.ai_mention_rate * Decimal("100")
    avg = (mention_score + metrics.ai_position_score) / Decimal("2")
    return _available("ai_recognition", avg, sample_size=sample_size)


def score_overall(
    components: tuple[ComponentScore, ...],
) -> tuple[Decimal | None, tuple[ComponentScore, ...]]:
    available = [item for item in components if item.status == EntityStatus.AVAILABLE]
    if not available:
        return None, tuple(
            ComponentScore(
                name=item.name,
                score=item.score,
                status=item.status,
                weight=item.weight,
                effective_weight=None,
                sample_size=item.sample_size,
            )
            for item in components
        )

    weight_sum = sum((item.weight for item in available), Decimal("0"))
    updated: list[ComponentScore] = []
    total = Decimal("0")
    for item in components:
        if item.status != EntityStatus.AVAILABLE or item.score is None:
            updated.append(
                ComponentScore(
                    name=item.name,
                    score=item.score,
                    status=item.status,
                    weight=item.weight,
                    effective_weight=None,
                    sample_size=item.sample_size,
                )
            )
            continue
        effective = item.weight / weight_sum
        total += item.score * effective
        updated.append(
            ComponentScore(
                name=item.name,
                score=quantize_score(item.score),
                status=item.status,
                weight=item.weight,
                effective_weight=effective.quantize(Decimal("0.0001")),
                sample_size=item.sample_size,
            )
        )
    return quantize_score(clamp_score(total)), tuple(updated)


def assemble_result(
    *,
    metrics: EntityMetrics,
    evidence: EntityEvidence,
) -> EntityStrengthScore:
    pages = evidence.analyzable_pages
    responses = evidence.successful_ai_responses

    if pages < 1 and responses < 1:
        components = (
            _unavailable("presence"),
            _unavailable("consistency"),
            _unavailable("structured_identity"),
            _unavailable("ai_recognition"),
        )
        return EntityStrengthScore(
            overall_score=None,
            status=EntityStatus.UNAVAILABLE,
            metrics=metrics,
            components=components,
            evidence=evidence,
            notes=(
                "Entity Strength is unavailable. Crawl the website and/or run AI Query "
                "Analysis first. Unavailable is not zero.",
            ),
        )

    components = (
        score_presence(metrics, sample_size=pages),
        score_consistency(metrics, sample_size=pages),
        score_structured_identity(metrics, sample_size=pages),
        score_ai_recognition(metrics, sample_size=responses),
    )
    overall, components = score_overall(components)

    available_count = sum(1 for item in components if item.status == EntityStatus.AVAILABLE)
    if available_count == 0:
        status = EntityStatus.UNAVAILABLE
        overall = None
    elif available_count == len(components):
        status = EntityStatus.AVAILABLE
    else:
        status = EntityStatus.PROVISIONAL

    notes: list[str] = [
        "This score evaluates signals found on the audited website and analyzed AI "
        "responses. It does not verify Google Knowledge Graph, Wikidata, Wikipedia, "
        "or third-party entity databases.",
    ]
    if status == EntityStatus.PROVISIONAL:
        notes.append(
            "Entity Strength is provisional because one or more components lack "
            "sufficient underlying data."
        )

    return EntityStrengthScore(
        overall_score=overall,
        status=status,
        metrics=metrics,
        components=components,
        evidence=evidence,
        notes=tuple(notes),
    )


def _available(name: str, score: Decimal, *, sample_size: int) -> ComponentScore:
    return ComponentScore(
        name=name,
        score=quantize_score(clamp_score(score)),
        status=EntityStatus.AVAILABLE,
        weight=ENTITY_WEIGHTS[name],
        effective_weight=None,
        sample_size=sample_size,
    )


def _unavailable(name: str, *, sample_size: int = 0) -> ComponentScore:
    return ComponentScore(
        name=name,
        score=None,
        status=EntityStatus.UNAVAILABLE,
        weight=ENTITY_WEIGHTS[name],
        effective_weight=None,
        sample_size=sample_size,
    )
