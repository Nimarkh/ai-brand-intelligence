"""Impact, effort, and priority scoring for recommendations."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.models.enums import FindingSeverity, RecommendationPriority
from app.services.recommendations.constants import (
    COVERAGE_FLOOR,
    COVERAGE_SPAN,
    EASE_WEIGHT,
    IMPACT_WEIGHT,
    SEVERITY_BASE_IMPACT,
    priority_from_score,
)


def quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def clamp_0_100(value: Decimal) -> Decimal:
    if value < Decimal("0"):
        return Decimal("0")
    if value > Decimal("100"):
        return Decimal("100")
    return value


def impact_from_severity(
    severity: FindingSeverity,
    *,
    affected_pages: int,
    analyzable_pages: int,
) -> Decimal:
    """impact = base × (0.50 + 0.50 × coverage), bounded 0–100."""
    base = SEVERITY_BASE_IMPACT[severity]
    if analyzable_pages < 1:
        coverage = Decimal("1") if affected_pages > 0 else Decimal("0")
    else:
        coverage = min(Decimal("1"), Decimal(affected_pages) / Decimal(analyzable_pages))
    impact = base * (COVERAGE_FLOOR + COVERAGE_SPAN * coverage)
    return quantize(clamp_0_100(impact))


def fixed_impact(value: Decimal) -> Decimal:
    return quantize(clamp_0_100(value))


def compute_priority(impact: Decimal, effort: Decimal) -> tuple[RecommendationPriority, Decimal]:
    """priority_score = impact×0.70 + (100−effort)×0.30."""
    score = impact * IMPACT_WEIGHT + (Decimal("100") - effort) * EASE_WEIGHT
    score = quantize(clamp_0_100(score))
    return priority_from_score(score), score
