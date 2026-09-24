"""Convert visibility metrics into normalized component and overall scores."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.services.ai.visibility.models import (
    AIVisibilityScore,
    ComponentScore,
    VisibilityMetrics,
    VisibilityStatus,
)
from app.services.ai.visibility.weights import VISIBILITY_WEIGHTS


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


def build_components(metrics: VisibilityMetrics) -> tuple[ComponentScore, ...]:
    mention = _component(
        "mention",
        (metrics.mention_rate * Decimal("100")) if metrics.mention_rate is not None else None,
        sample_size=1 if metrics.mention_rate is not None else 0,
    )
    citation = _component(
        "citation",
        (metrics.citation_rate * Decimal("100")) if metrics.citation_rate is not None else None,
        sample_size=1 if metrics.citation_rate is not None else 0,
    )
    position = _component(
        "position",
        metrics.position_score,
        sample_size=1 if metrics.position_score is not None else 0,
    )
    semantic = _component(
        "semantic",
        metrics.semantic_score,
        sample_size=1 if metrics.semantic_score is not None else 0,
    )
    return (mention, citation, position, semantic)


def score_overall(
    components: tuple[ComponentScore, ...],
) -> tuple[Decimal | None, tuple[ComponentScore, ...]]:
    """Weighted overall with renormalization across available components.

    Unavailable components are excluded (never treated as zero).
    """
    available = [item for item in components if item.status == VisibilityStatus.AVAILABLE]
    if not available:
        empty = tuple(
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
        return None, empty

    weight_sum = sum((item.weight for item in available), Decimal("0"))
    if weight_sum <= 0:
        return None, components

    updated: list[ComponentScore] = []
    total = Decimal("0")
    for item in components:
        if item.status != VisibilityStatus.AVAILABLE or item.score is None:
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

    overall = quantize_score(clamp_score(total))
    return overall, tuple(updated)


def assemble_result(
    *,
    metrics: VisibilityMetrics,
    total_queries: int,
    successful_responses: int,
    failed_responses: int,
    semantic_by_response_id: tuple[tuple, ...] = (),
) -> AIVisibilityScore:
    if successful_responses < 1:
        components = build_components(metrics)
        empty_components = tuple(
            ComponentScore(
                name=item.name,
                score=None,
                status=VisibilityStatus.UNAVAILABLE,
                weight=item.weight,
                effective_weight=None,
                sample_size=0,
            )
            for item in components
        )
        coverage = (
            Decimal("0")
            if total_queries == 0
            else (Decimal(successful_responses) / Decimal(total_queries)).quantize(
                Decimal("0.0001")
            )
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
            components=empty_components,
            total_queries=total_queries,
            successful_responses=successful_responses,
            failed_responses=failed_responses,
            response_coverage=coverage if total_queries > 0 else None,
            semantic_by_response_id=semantic_by_response_id,
        )

    components = build_components(metrics)
    overall, components = score_overall(components)

    if failed_responses > 0:
        status = VisibilityStatus.PROVISIONAL
    else:
        status = VisibilityStatus.AVAILABLE

    coverage = (
        (Decimal(successful_responses) / Decimal(total_queries)).quantize(Decimal("0.0001"))
        if total_queries > 0
        else None
    )

    return AIVisibilityScore(
        overall_score=overall,
        status=status,
        metrics=VisibilityMetrics(
            mention_rate=metrics.mention_rate,
            citation_rate=metrics.citation_rate,
            average_position=metrics.average_position,
            position_score=quantize_score(metrics.position_score),
            semantic_alignment=metrics.semantic_alignment,
            semantic_score=quantize_score(metrics.semantic_score),
        ),
        components=components,
        total_queries=total_queries,
        successful_responses=successful_responses,
        failed_responses=failed_responses,
        response_coverage=coverage,
        semantic_by_response_id=semantic_by_response_id,
    )


def _component(name: str, score: Decimal | None, *, sample_size: int) -> ComponentScore:
    weight = VISIBILITY_WEIGHTS[name]
    if score is None:
        return ComponentScore(
            name=name,
            score=None,
            status=VisibilityStatus.UNAVAILABLE,
            weight=weight,
            effective_weight=None,
            sample_size=sample_size,
        )
    return ComponentScore(
        name=name,
        score=quantize_score(clamp_score(score)),
        status=VisibilityStatus.AVAILABLE,
        weight=weight,
        effective_weight=None,
        sample_size=sample_size,
    )
