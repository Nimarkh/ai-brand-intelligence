"""Centralized recommendation scoring constants."""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import FindingSeverity, RecommendationPriority

# priority_score = impact * IMPACT_WEIGHT + (100 - effort) * EASE_WEIGHT
IMPACT_WEIGHT = Decimal("0.70")
EASE_WEIGHT = Decimal("0.30")
assert IMPACT_WEIGHT + EASE_WEIGHT == Decimal("1.00")

PRIORITY_HIGH_MIN = Decimal("75")
PRIORITY_MEDIUM_MIN = Decimal("50")

# Finding severity → base impact
SEVERITY_BASE_IMPACT: dict[FindingSeverity, Decimal] = {
    FindingSeverity.HIGH: Decimal("90"),
    FindingSeverity.MEDIUM: Decimal("65"),
    FindingSeverity.LOW: Decimal("40"),
    FindingSeverity.INFO: Decimal("15"),
}

# Coverage blend: impact = base × (COVERAGE_FLOOR + COVERAGE_SPAN × coverage)
COVERAGE_FLOOR = Decimal("0.50")
COVERAGE_SPAN = Decimal("0.50")

# Metric threshold for AI / Entity / Website-health rules
SCORE_THRESHOLD = Decimal("50")
COMPONENT_HEALTH_THRESHOLD = Decimal("60")

# Effort bands (implementation complexity, not importance)
EFFORT_LOW = Decimal("25")
EFFORT_LOW_MED = Decimal("35")
EFFORT_MEDIUM = Decimal("50")
EFFORT_MEDIUM_HIGH = Decimal("60")
EFFORT_HIGH = Decimal("80")
EFFORT_VERY_HIGH = Decimal("85")


def priority_from_score(priority_score: Decimal) -> RecommendationPriority:
    if priority_score >= PRIORITY_HIGH_MIN:
        return RecommendationPriority.HIGH
    if priority_score >= PRIORITY_MEDIUM_MIN:
        return RecommendationPriority.MEDIUM
    return RecommendationPriority.LOW
