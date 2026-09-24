"""Internal score models. Not exposed directly through the API."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from uuid import UUID


class ScoreStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    PROVISIONAL = "PROVISIONAL"


@dataclass(frozen=True)
class FindingInput:
    """Minimal finding snapshot for scoring (no ORM)."""

    id: UUID
    category: str
    severity: str
    title: str
    page_id: UUID | None


@dataclass(frozen=True)
class PenaltyContribution:
    rule_id: str
    category: str
    component: str
    severity: str
    severity_weight: Decimal
    rule_weight: Decimal
    affected_pages: int
    analyzable_pages: int
    affected_page_rate: Decimal
    penalty_points: Decimal
    finding_ids: tuple[UUID, ...]
    page_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class ComponentScore:
    name: str
    score: Decimal | None
    status: ScoreStatus
    max_score: Decimal = Decimal("100")
    findings_count: int = 0
    affected_pages: int = 0
    penalties: tuple[PenaltyContribution, ...] = field(default_factory=tuple)

    @property
    def top_penalty_rules(self) -> tuple[PenaltyContribution, ...]:
        return tuple(sorted(self.penalties, key=lambda item: item.penalty_points, reverse=True)[:5])


@dataclass(frozen=True)
class DimensionScore:
    """A top-level score dimension with availability status."""

    score: Decimal | None
    status: ScoreStatus


@dataclass(frozen=True)
class AuditScoreResult:
    """Full deterministic score snapshot for an audit."""

    technical: ComponentScore
    seo: ComponentScore
    content: ComponentScore
    structured_data: ComponentScore
    website_health: DimensionScore
    seo_score: DimensionScore
    overall: DimensionScore
    analyzable_pages: int
    findings_count: int
    affected_pages: int
    status: ScoreStatus
