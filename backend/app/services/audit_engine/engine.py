"""Audit Engine entry point. Pure scoring over stored page/finding snapshots."""

from __future__ import annotations

from uuid import UUID

from app.services.audit_engine.models import AuditScoreResult, FindingInput
from app.services.audit_engine.scoring import ScoreCalculator


class AuditEngine:
    """Calculate deterministic audit scores without database or network access."""

    def __init__(self, calculator: ScoreCalculator | None = None) -> None:
        self.calculator = calculator or ScoreCalculator()

    def score(
        self,
        *,
        page_ids: list[UUID],
        findings: list[FindingInput],
    ) -> AuditScoreResult:
        """Score an audit from page IDs and findings.

        ``page_ids`` defines analyzable pages (>= 1 required for AVAILABLE scores).
        Findings may be empty (treated as zero penalties / high scores).
        """
        return self.calculator.calculate(
            analyzable_pages=len(page_ids),
            findings=findings,
        )
