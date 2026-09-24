"""Internal recommendation models (not ORM)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.models.enums import FindingSeverity, RecommendationPriority
from app.services.recommendations.categories import RecommendationCategory, RecommendationSource


@dataclass(frozen=True)
class FindingEvidence:
    id: UUID
    category: str
    severity: FindingSeverity
    title: str
    page_id: UUID | None


@dataclass(frozen=True)
class AuditEvidence:
    """Snapshot of persisted audit evidence for rule evaluation."""

    analyzable_pages: int
    findings: tuple[FindingEvidence, ...]
    # Phase 09 component scores (None = not calculated / unavailable)
    technical_score: Decimal | None
    seo_component_score: Decimal | None
    content_score: Decimal | None
    structured_data_score: Decimal | None
    scores_available: bool
    # Phase 12 (None components when visibility not calculated)
    visibility_available: bool
    mention_score: Decimal | None
    citation_score: Decimal | None
    position_score: Decimal | None
    semantic_score: Decimal | None
    successful_ai_responses: int
    responses_mentioning_brand: int
    mention_rate: Decimal | None
    # Phase 13
    entity_available: bool
    presence_score: Decimal | None
    consistency_score: Decimal | None
    structured_identity_score: Decimal | None
    ai_recognition_score: Decimal | None
    entity_pages: int
    pages_with_brand_in_title: int
    pages_with_brand_in_meta: int


@dataclass(frozen=True)
class RecommendationCandidate:
    rule_key: str
    source: RecommendationSource
    category: RecommendationCategory
    title: str
    description: str
    impact_score: Decimal
    effort_score: Decimal
    priority: RecommendationPriority
    priority_score: Decimal
    affected_pages: int = 0
    finding_count: int = 0
