"""API schemas for the Main Intelligence Dashboard."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AuditStatus, RecommendationPriority
from app.services.dashboard.models import DashboardAggregate, ScoreAvailability


class DashboardScoreStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    PROVISIONAL = "PROVISIONAL"


class DashboardInsightSource(str, Enum):
    SEO_FINDINGS = "SEO_FINDINGS"
    AI_VISIBILITY = "AI_VISIBILITY"
    ENTITY = "ENTITY"
    RECOMMENDATIONS = "RECOMMENDATIONS"
    WEBSITE = "WEBSITE"


class DashboardWorkspace(BaseModel):
    brand_count: int
    audit_count: int
    completed_audit_count: int


class DashboardSelectedAudit(BaseModel):
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


class DashboardScoreCard(BaseModel):
    score: float | None = Field(
        description="Persisted score when available. Null means unavailable, never coerced to zero.",
    )
    status: DashboardScoreStatus
    explanation: str
    audit_date: datetime | None = None
    response_coverage: float | None = Field(
        default=None,
        description="AI successful responses / queries when AI visibility is available.",
    )
    evidence_coverage: float | None = Field(
        default=None,
        description="Share of crawled pages with structured data when entity is available.",
    )


class DashboardOverallScore(BaseModel):
    score: float | None
    status: DashboardScoreStatus
    explanation: str


class DashboardScores(BaseModel):
    overall: DashboardOverallScore
    website: DashboardScoreCard
    seo: DashboardScoreCard
    ai_visibility: DashboardScoreCard
    entity: DashboardScoreCard


class DashboardSnapshot(BaseModel):
    pages_crawled: int | None = None
    seo_findings: int | None = None
    high_severity_findings: int | None = None
    ai_queries: int | None = None
    ai_successful_responses: int | None = None
    ai_response_coverage: float | None = None
    ai_mention_rate: float | None = None
    entity_pages_analyzed: int | None = None
    pages_with_schema: int | None = None
    structured_identity_coverage: float | None = None
    recommendations_total: int | None = None
    recommendations_high: int | None = None
    recommendations_medium: int | None = None


class DashboardInsight(BaseModel):
    text: str
    source: DashboardInsightSource


class DashboardRecommendationPreview(BaseModel):
    id: UUID
    title: str
    category: str
    priority: RecommendationPriority
    impact_score: float | None
    effort_score: float | None


class DashboardFreshness(BaseModel):
    last_website_crawl: datetime | None = None
    last_seo_analysis: datetime | None = None
    last_ai_analysis: datetime | None = None
    last_recommendations_calculation: datetime | None = None


class DashboardBrandOption(BaseModel):
    id: UUID
    name: str


class DashboardOverview(BaseModel):
    """Main Intelligence Dashboard payload for the authenticated user."""

    workspace: DashboardWorkspace
    selected_audit: DashboardSelectedAudit | None
    scores: DashboardScores
    snapshot: DashboardSnapshot
    insights: list[DashboardInsight]
    recommendations: list[DashboardRecommendationPreview]
    freshness: DashboardFreshness
    brands: list[DashboardBrandOption]
    selection_rule: str = Field(
        description="Deterministic rule used to pick selected_audit.",
    )


def serialize_dashboard(aggregate: DashboardAggregate) -> DashboardOverview:
    selected = None
    if aggregate.selected_audit is not None:
        audit = aggregate.selected_audit
        selected = DashboardSelectedAudit(
            id=audit.id,
            brand_id=audit.brand_id,
            brand_name=audit.brand_name,
            status=audit.status,
            created_at=audit.created_at,
            completed_at=audit.completed_at,
            website_score_available=audit.website_score_available,
            seo_score_available=audit.seo_score_available,
            ai_visibility_available=audit.ai_visibility_available,
            entity_available=audit.entity_available,
            overall_score_available=audit.overall_score_available,
            pages_crawled=audit.pages_crawled,
            seo_findings=audit.seo_findings,
        )

    return DashboardOverview(
        workspace=DashboardWorkspace(
            brand_count=aggregate.workspace.brand_count,
            audit_count=aggregate.workspace.audit_count,
            completed_audit_count=aggregate.workspace.completed_audit_count,
        ),
        selected_audit=selected,
        scores=DashboardScores(
            overall=DashboardOverallScore(
                score=_float_or_none(aggregate.overall.score),
                status=_map_status(aggregate.overall.status),
                explanation=aggregate.overall.explanation,
            ),
            website=_serialize_card(aggregate.website),
            seo=_serialize_card(aggregate.seo),
            ai_visibility=_serialize_card(aggregate.ai_visibility),
            entity=_serialize_card(aggregate.entity),
        ),
        snapshot=DashboardSnapshot(
            pages_crawled=aggregate.snapshot.pages_crawled,
            seo_findings=aggregate.snapshot.seo_findings,
            high_severity_findings=aggregate.snapshot.high_severity_findings,
            ai_queries=aggregate.snapshot.ai_queries,
            ai_successful_responses=aggregate.snapshot.ai_successful_responses,
            ai_response_coverage=_float_or_none(aggregate.snapshot.ai_response_coverage),
            ai_mention_rate=_float_or_none(aggregate.snapshot.ai_mention_rate),
            entity_pages_analyzed=aggregate.snapshot.entity_pages_analyzed,
            pages_with_schema=aggregate.snapshot.pages_with_schema,
            structured_identity_coverage=_float_or_none(
                aggregate.snapshot.structured_identity_coverage
            ),
            recommendations_total=aggregate.snapshot.recommendations_total,
            recommendations_high=aggregate.snapshot.recommendations_high,
            recommendations_medium=aggregate.snapshot.recommendations_medium,
        ),
        insights=[
            DashboardInsight(
                text=item.text,
                source=DashboardInsightSource(item.source.value),
            )
            for item in aggregate.insights
        ],
        recommendations=[
            DashboardRecommendationPreview(
                id=item.id,
                title=item.title,
                category=item.category,
                priority=item.priority,
                impact_score=_float_or_none(item.impact_score),
                effort_score=_float_or_none(item.effort_score),
            )
            for item in aggregate.recommendations
        ],
        freshness=DashboardFreshness(
            last_website_crawl=aggregate.freshness.last_website_crawl,
            last_seo_analysis=aggregate.freshness.last_seo_analysis,
            last_ai_analysis=aggregate.freshness.last_ai_analysis,
            last_recommendations_calculation=(
                aggregate.freshness.last_recommendations_calculation
            ),
        ),
        brands=[
            DashboardBrandOption(id=brand.id, name=brand.name) for brand in aggregate.brands
        ],
        selection_rule=aggregate.selection_rule,
    )


def _serialize_card(layer) -> DashboardScoreCard:
    return DashboardScoreCard(
        score=_float_or_none(layer.score),
        status=_map_status(layer.status),
        explanation=layer.explanation,
        audit_date=layer.audit_date,
        response_coverage=_float_or_none(layer.response_coverage),
        evidence_coverage=_float_or_none(layer.evidence_coverage),
    )


def _map_status(status: ScoreAvailability) -> DashboardScoreStatus:
    return DashboardScoreStatus(status.value)


def _float_or_none(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)
