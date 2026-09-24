"""Internal dashboard aggregation models (not API schemas)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from app.models.enums import AuditStatus, RecommendationPriority


class ScoreAvailability(str, Enum):
    """Score presentation status for dashboard layers."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    PROVISIONAL = "PROVISIONAL"


class InsightSource(str, Enum):
    SEO_FINDINGS = "SEO_FINDINGS"
    AI_VISIBILITY = "AI_VISIBILITY"
    ENTITY = "ENTITY"
    RECOMMENDATIONS = "RECOMMENDATIONS"
    WEBSITE = "WEBSITE"


@dataclass(frozen=True)
class ScoreLayer:
    score: Decimal | None
    status: ScoreAvailability
    explanation: str
    response_coverage: Decimal | None = None
    evidence_coverage: Decimal | None = None
    audit_date: datetime | None = None


@dataclass(frozen=True)
class OverallLayer:
    score: Decimal | None
    status: ScoreAvailability
    explanation: str


@dataclass(frozen=True)
class SnapshotMetrics:
    pages_crawled: int | None = None
    seo_findings: int | None = None
    high_severity_findings: int | None = None
    ai_queries: int | None = None
    ai_successful_responses: int | None = None
    ai_response_coverage: Decimal | None = None
    ai_mention_rate: Decimal | None = None
    ai_mentions: int | None = None
    entity_pages_analyzed: int | None = None
    pages_with_schema: int | None = None
    structured_identity_coverage: Decimal | None = None
    recommendations_total: int | None = None
    recommendations_high: int | None = None
    recommendations_medium: int | None = None


@dataclass(frozen=True)
class InsightItem:
    text: str
    source: InsightSource


@dataclass(frozen=True)
class RecommendationPreview:
    id: UUID
    title: str
    category: str
    priority: RecommendationPriority
    impact_score: Decimal | None
    effort_score: Decimal | None


@dataclass(frozen=True)
class FreshnessTimestamps:
    last_website_crawl: datetime | None = None
    last_seo_analysis: datetime | None = None
    last_ai_analysis: datetime | None = None
    last_recommendations_calculation: datetime | None = None


@dataclass(frozen=True)
class SelectedAuditInfo:
    id: UUID
    brand_id: UUID
    brand_name: str
    status: AuditStatus
    created_at: datetime
    completed_at: datetime | None
    website_score_available: bool
    seo_score_available: bool
    ai_visibility_available: bool
    entity_available: bool
    overall_score_available: bool
    pages_crawled: int
    seo_findings: int


@dataclass(frozen=True)
class BrandOption:
    id: UUID
    name: str


@dataclass(frozen=True)
class WorkspaceSummary:
    brand_count: int
    audit_count: int
    completed_audit_count: int


@dataclass(frozen=True)
class DashboardAggregate:
    workspace: WorkspaceSummary
    selected_audit: SelectedAuditInfo | None
    overall: OverallLayer
    website: ScoreLayer
    seo: ScoreLayer
    ai_visibility: ScoreLayer
    entity: ScoreLayer
    snapshot: SnapshotMetrics
    insights: tuple[InsightItem, ...] = field(default_factory=tuple)
    recommendations: tuple[RecommendationPreview, ...] = field(default_factory=tuple)
    freshness: FreshnessTimestamps = field(default_factory=FreshnessTimestamps)
    brands: tuple[BrandOption, ...] = field(default_factory=tuple)
    selection_rule: str = ""
