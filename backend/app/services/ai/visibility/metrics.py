"""Raw AI Visibility metrics from successful responses."""

from __future__ import annotations

from decimal import Decimal

from app.services.ai.visibility.extraction import semantic_alignment
from app.services.ai.visibility.models import ResponseInput, VisibilityMetrics
from app.services.ai.visibility.weights import (
    POSITION_SCORE_DEFAULT,
    POSITION_SCORE_MAP,
)


def position_to_score(position: int | None, *, brand_mentioned: bool) -> Decimal:
    """Map response mention-position to 0–100. Not search ranking."""
    if not brand_mentioned or position is None:
        return POSITION_SCORE_DEFAULT
    if position >= 5:
        return POSITION_SCORE_DEFAULT
    return POSITION_SCORE_MAP.get(position, POSITION_SCORE_DEFAULT)


def compute_metrics(
    responses: list[ResponseInput],
) -> tuple[VisibilityMetrics, list[Decimal | None]]:
    """Compute aggregate metrics and per-response semantic alignments.

    Failed provider calls are not included in ``responses`` and must not
    appear in denominators.
    """
    n = len(responses)
    if n == 0:
        empty = VisibilityMetrics(
            mention_rate=None,
            citation_rate=None,
            average_position=None,
            position_score=None,
            semantic_alignment=None,
            semantic_score=None,
        )
        return empty, []

    mentioned = sum(1 for item in responses if item.brand_mentioned)
    cited = sum(1 for item in responses if item.citation_found)
    mention_rate = Decimal(mentioned) / Decimal(n)
    citation_rate = Decimal(cited) / Decimal(n)

    position_scores = [
        position_to_score(item.brand_position, brand_mentioned=item.brand_mentioned)
        for item in responses
    ]
    avg_position_score = sum(position_scores, Decimal("0")) / Decimal(n)

    positions_present = [
        Decimal(item.brand_position)
        for item in responses
        if item.brand_mentioned and item.brand_position is not None
    ]
    average_position = (
        sum(positions_present, Decimal("0")) / Decimal(len(positions_present))
        if positions_present
        else None
    )

    semantic_values: list[Decimal | None] = [
        semantic_alignment(
            item.query_text,
            item.response_text,
            brand_mentioned=item.brand_mentioned,
        )
        for item in responses
    ]
    usable = [value for value in semantic_values if value is not None]
    if usable:
        avg_semantic = sum(usable, Decimal("0")) / Decimal(len(usable))
        semantic_score = avg_semantic * Decimal("100")
    else:
        avg_semantic = None
        semantic_score = None

    metrics = VisibilityMetrics(
        mention_rate=_q4(mention_rate),
        citation_rate=_q4(citation_rate),
        average_position=_q4(average_position) if average_position is not None else None,
        position_score=_q1(avg_position_score),
        semantic_alignment=_q4(avg_semantic) if avg_semantic is not None else None,
        semantic_score=_q1(semantic_score) if semantic_score is not None else None,
    )
    return metrics, semantic_values


def _q4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def _q1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.1"))
