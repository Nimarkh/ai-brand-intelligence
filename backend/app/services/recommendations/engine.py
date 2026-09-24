"""Recommendations Engine — rank and limit deterministic recommendation candidates."""

from __future__ import annotations

from app.models.enums import RecommendationPriority
from app.services.recommendations.models import AuditEvidence, RecommendationCandidate
from app.services.recommendations.rules import evaluate_all_rules

_PRIORITY_ORDER = {
    RecommendationPriority.HIGH: 0,
    RecommendationPriority.MEDIUM: 1,
    RecommendationPriority.LOW: 2,
}


class RecommendationsEngine:
    """Pure recommendation generation. No database access."""

    def generate(
        self,
        evidence: AuditEvidence,
        *,
        max_recommendations: int,
    ) -> list[RecommendationCandidate]:
        candidates = evaluate_all_rules(evidence)
        ranked = sorted(candidates, key=_sort_key)
        if max_recommendations < 1:
            return []
        return ranked[:max_recommendations]


def _sort_key(item: RecommendationCandidate) -> tuple:
    return (
        _PRIORITY_ORDER[item.priority],
        -item.impact_score,
        item.effort_score,
        item.rule_key,
        item.title,
    )
