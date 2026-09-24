"""AI Visibility Engine — pure scoring over persisted query/response snapshots."""

from __future__ import annotations

from uuid import UUID

from app.services.ai.visibility.metrics import compute_metrics
from app.services.ai.visibility.models import AIVisibilityScore, ResponseInput
from app.services.ai.visibility.scoring import assemble_result


class AIVisibilityEngine:
    """Deterministic visibility scoring. No database or network access."""

    def score(
        self,
        *,
        total_queries: int,
        responses: list[ResponseInput],
    ) -> AIVisibilityScore:
        """Score an audit from query count and successful response inputs.

        ``failed_responses`` is derived as ``total_queries - len(responses)``.
        """
        successful = len(responses)
        failed = max(0, total_queries - successful)
        metrics, semantic_values = compute_metrics(responses)
        semantic_pairs: list[tuple[UUID, object]] = [
            (item.response_id, semantic_values[index])
            for index, item in enumerate(responses)
        ]
        return assemble_result(
            metrics=metrics,
            total_queries=total_queries,
            successful_responses=successful,
            failed_responses=failed,
            semantic_by_response_id=tuple(semantic_pairs),
        )
