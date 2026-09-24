"""Dashboard orchestration: ownership-scoped aggregation of persisted intelligence.

Does not recalculate Phase 09–14 scores. Reads stored columns and related rows only.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.enums import AuditStatus, FindingSeverity, RecommendationPriority
from app.models.recommendation import Recommendation
from app.models.user import User
from app.models.website import SeoFinding, WebsitePage
from app.services.dashboard.insights import build_insights
from app.services.dashboard.models import (
    BrandOption,
    DashboardAggregate,
    FreshnessTimestamps,
    OverallLayer,
    RecommendationPreview,
    ScoreAvailability,
    ScoreLayer,
    SelectedAuditInfo,
    SnapshotMetrics,
    WorkspaceSummary,
)
from app.services.recommendation_service import list_recommendations

RECOMMENDATION_PREVIEW_LIMIT = 5

SELECTION_RULE = (
    "1) Most recently completed owned audit "
    "(completed_at DESC, created_at DESC, id DESC). "
    "2) If none completed, most recent owned audit "
    "(created_at DESC, id DESC). "
    "3) Optional brand_id narrows selection to that owned brand. "
    "4) Empty when the user has no audits."
)

PROVISIONAL_OVERALL_EXPLANATION = (
    "Based on currently available website and SEO signals. "
    "AI Visibility and Entity Strength are not yet included in the overall score."
)


def get_dashboard_overview(
    current_user: User,
    db: Session,
    *,
    brand_id: UUID | None = None,
) -> DashboardAggregate:
    """Build the Main Intelligence Dashboard for the authenticated user.

    Every query filters through Brand.owner_id == current_user.id.
    """
    owner_id = current_user.id
    brands = _owned_brands(db, owner_id)
    brand_options = tuple(BrandOption(id=b.id, name=b.name) for b in brands)

    selected_brand_id = _resolve_brand_filter(brands, brand_id)
    workspace = _workspace_summary(db, owner_id, selected_brand_id)

    audit = _select_audit(db, owner_id, selected_brand_id)
    if audit is None:
        return _empty_aggregate(workspace, brand_options)

    brand = audit.brand
    snapshot = _build_snapshot(db, audit)
    freshness = _build_freshness(db, audit.id)
    recommendations = _recommendation_preview(db, audit.id)

    website_available = audit.website_score is not None
    seo_available = audit.seo_score is not None
    ai_available = audit.ai_visibility_score is not None
    entity_available = audit.entity_score is not None
    overall_available = audit.overall_score is not None

    audit_date = audit.completed_at or audit.created_at

    website = ScoreLayer(
        score=_quantize(audit.website_score),
        status=_layer_status(website_available),
        explanation=(
            "Website health from the latest scored audit."
            if website_available
            else "Not calculated yet"
        ),
        audit_date=audit_date if website_available else None,
    )
    seo = ScoreLayer(
        score=_quantize(audit.seo_score),
        status=_layer_status(seo_available),
        explanation=(
            "SEO strength from stored findings and page signals."
            if seo_available
            else "Not calculated yet"
        ),
        audit_date=audit_date if seo_available else None,
    )
    ai_visibility = ScoreLayer(
        score=_quantize(audit.ai_visibility_score),
        status=_layer_status(ai_available),
        explanation=(
            "AI visibility from persisted query responses."
            if ai_available
            else "Not calculated yet"
        ),
        response_coverage=snapshot.ai_response_coverage if ai_available else None,
        audit_date=freshness.last_ai_analysis if ai_available else None,
    )
    entity = ScoreLayer(
        score=_quantize(audit.entity_score),
        status=_layer_status(entity_available),
        explanation=(
            "Entity strength from crawl and AI evidence."
            if entity_available
            else "Not calculated yet"
        ),
        evidence_coverage=(
            snapshot.structured_identity_coverage if entity_available else None
        ),
        audit_date=audit_date if entity_available else None,
    )
    overall = _overall_layer(
        overall_score=audit.overall_score,
        ai_available=ai_available,
        entity_available=entity_available,
    )

    selected = SelectedAuditInfo(
        id=audit.id,
        brand_id=audit.brand_id,
        brand_name=brand.name if brand is not None else "",
        status=audit.status,
        created_at=audit.created_at,
        completed_at=audit.completed_at,
        website_score_available=website_available,
        seo_score_available=seo_available,
        ai_visibility_available=ai_available,
        entity_available=entity_available,
        overall_score_available=overall_available,
        pages_crawled=snapshot.pages_crawled or 0,
        seo_findings=snapshot.seo_findings or 0,
    )

    return DashboardAggregate(
        workspace=workspace,
        selected_audit=selected,
        overall=overall,
        website=website,
        seo=seo,
        ai_visibility=ai_visibility,
        entity=entity,
        snapshot=snapshot,
        insights=build_insights(snapshot),
        recommendations=recommendations,
        freshness=freshness,
        brands=brand_options,
        selection_rule=SELECTION_RULE,
    )


def _empty_aggregate(
    workspace: WorkspaceSummary,
    brands: tuple[BrandOption, ...],
) -> DashboardAggregate:
    unavailable = ScoreLayer(
        score=None,
        status=ScoreAvailability.UNAVAILABLE,
        explanation="Not calculated yet",
    )
    return DashboardAggregate(
        workspace=workspace,
        selected_audit=None,
        overall=OverallLayer(
            score=None,
            status=ScoreAvailability.UNAVAILABLE,
            explanation="Not available",
        ),
        website=unavailable,
        seo=unavailable,
        ai_visibility=unavailable,
        entity=unavailable,
        snapshot=SnapshotMetrics(),
        insights=(),
        recommendations=(),
        freshness=FreshnessTimestamps(),
        brands=brands,
        selection_rule=SELECTION_RULE,
    )


def _owned_brands(db: Session, owner_id: UUID) -> list[Brand]:
    return list(
        db.scalars(
            select(Brand)
            .where(Brand.owner_id == owner_id)
            .order_by(Brand.name.asc(), Brand.id.asc())
        ).all()
    )


def _resolve_brand_filter(
    brands: list[Brand],
    brand_id: UUID | None,
) -> UUID | None:
    if brand_id is None:
        return None
    owned_ids = {brand.id for brand in brands}
    if brand_id not in owned_ids:
        return None
    return brand_id


def _workspace_summary(
    db: Session,
    owner_id: UUID,
    brand_id: UUID | None,
) -> WorkspaceSummary:
    owned = select(Brand.id).where(Brand.owner_id == owner_id)
    brand_query = select(func.count()).select_from(Brand).where(Brand.owner_id == owner_id)
    if brand_id is not None:
        brand_query = brand_query.where(Brand.id == brand_id)
        owned = owned.where(Brand.id == brand_id)

    brand_count = int(db.scalar(brand_query) or 0)

    completed = Audit.status == AuditStatus.COMPLETED
    audit_count, completed_count = db.execute(
        select(
            func.count(Audit.id),
            func.coalesce(func.sum(case((completed, 1), else_=0)), 0),
        ).where(Audit.brand_id.in_(owned))
    ).one()

    return WorkspaceSummary(
        brand_count=brand_count,
        audit_count=int(audit_count or 0),
        completed_audit_count=int(completed_count or 0),
    )


def _select_audit(
    db: Session,
    owner_id: UUID,
    brand_id: UUID | None,
) -> Audit | None:
    """Deterministic audit selection for the dashboard."""
    base = (
        select(Audit)
        .join(Brand, Brand.id == Audit.brand_id)
        .where(Brand.owner_id == owner_id)
        .options(selectinload(Audit.brand))
    )
    if brand_id is not None:
        base = base.where(Audit.brand_id == brand_id)

    completed = db.scalars(
        base.where(Audit.status == AuditStatus.COMPLETED).order_by(
            Audit.completed_at.desc().nulls_last(),
            Audit.created_at.desc(),
            Audit.id.desc(),
        ).limit(1)
    ).first()
    if completed is not None:
        return completed

    return db.scalars(
        base.order_by(Audit.created_at.desc(), Audit.id.desc()).limit(1)
    ).first()


def _build_snapshot(db: Session, audit: Audit) -> SnapshotMetrics:
    pages_crawled = int(
        db.scalar(
            select(func.count()).select_from(WebsitePage).where(WebsitePage.audit_id == audit.id)
        )
        or 0
    )
    pages_with_schema = int(
        db.scalar(
            select(func.count())
            .select_from(WebsitePage)
            .where(
                WebsitePage.audit_id == audit.id,
                WebsitePage.has_schema.is_(True),
            )
        )
        or 0
    )

    seo_findings = int(
        db.scalar(
            select(func.count()).select_from(SeoFinding).where(SeoFinding.audit_id == audit.id)
        )
        or 0
    )
    high_severity = int(
        db.scalar(
            select(func.count())
            .select_from(SeoFinding)
            .where(
                SeoFinding.audit_id == audit.id,
                SeoFinding.severity == FindingSeverity.HIGH,
            )
        )
        or 0
    )

    ai_queries = int(
        db.scalar(
            select(func.count()).select_from(AiQuery).where(AiQuery.audit_id == audit.id)
        )
        or 0
    )

    # First response per query (matches Phase 12 input selection).
    first_response = (
        select(
            AiResponse.id.label("id"),
            AiResponse.brand_mentioned.label("brand_mentioned"),
            func.row_number()
            .over(
                partition_by=AiResponse.query_id,
                order_by=(AiResponse.created_at.asc(), AiResponse.id.asc()),
            )
            .label("rn"),
        )
        .join(AiQuery, AiQuery.id == AiResponse.query_id)
        .where(AiQuery.audit_id == audit.id)
        .subquery()
    )
    first_rows = db.execute(
        select(first_response.c.brand_mentioned).where(first_response.c.rn == 1)
    ).all()
    successful = len(first_rows)
    mentions = sum(1 for row in first_rows if row.brand_mentioned is True)

    ai_coverage = None
    mention_rate = None
    if ai_queries > 0:
        ai_coverage = (Decimal(successful) / Decimal(ai_queries)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
    if successful > 0:
        mention_rate = (Decimal(mentions) / Decimal(successful)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    schema_coverage = None
    if pages_crawled > 0:
        schema_coverage = (Decimal(pages_with_schema) / Decimal(pages_crawled)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    recommendations = list(
        db.scalars(select(Recommendation).where(Recommendation.audit_id == audit.id)).all()
    )
    rec_total = len(recommendations)
    rec_high = sum(1 for row in recommendations if row.priority == RecommendationPriority.HIGH)
    rec_medium = sum(
        1 for row in recommendations if row.priority == RecommendationPriority.MEDIUM
    )

    # Expose counts when related evidence exists. Null means the layer was not run.
    has_pages = pages_crawled > 0
    has_seo_layer = seo_findings > 0 or audit.seo_score is not None
    has_ai_layer = ai_queries > 0 or audit.ai_visibility_score is not None
    has_entity_layer = audit.entity_score is not None
    has_recs = rec_total > 0

    pages_value: int | None
    if has_pages:
        pages_value = pages_crawled
    elif audit.status == AuditStatus.COMPLETED:
        pages_value = 0
    else:
        pages_value = None

    return SnapshotMetrics(
        pages_crawled=pages_value,
        seo_findings=seo_findings if has_seo_layer or has_pages else None,
        high_severity_findings=high_severity if has_seo_layer or has_pages else None,
        ai_queries=ai_queries if has_ai_layer else None,
        ai_successful_responses=successful if has_ai_layer else None,
        ai_response_coverage=ai_coverage if has_ai_layer else None,
        ai_mention_rate=mention_rate if has_ai_layer and successful > 0 else None,
        ai_mentions=mentions if has_ai_layer and successful > 0 else None,
        entity_pages_analyzed=pages_crawled if has_entity_layer and has_pages else None,
        pages_with_schema=pages_with_schema if has_pages else None,
        structured_identity_coverage=schema_coverage if has_pages else None,
        recommendations_total=rec_total if has_recs else None,
        recommendations_high=rec_high if has_recs else None,
        recommendations_medium=rec_medium if has_recs else None,
    )


def _build_freshness(db: Session, audit_id: UUID) -> FreshnessTimestamps:
    last_crawl = db.scalar(
        select(func.max(WebsitePage.created_at)).where(WebsitePage.audit_id == audit_id)
    )
    last_seo = db.scalar(
        select(func.max(SeoFinding.created_at)).where(SeoFinding.audit_id == audit_id)
    )
    last_ai = db.scalar(
        select(func.max(AiResponse.created_at))
        .join(AiQuery, AiQuery.id == AiResponse.query_id)
        .where(AiQuery.audit_id == audit_id)
    )
    last_recs = db.scalar(
        select(func.max(Recommendation.created_at)).where(
            Recommendation.audit_id == audit_id
        )
    )
    return FreshnessTimestamps(
        last_website_crawl=_as_datetime(last_crawl),
        last_seo_analysis=_as_datetime(last_seo),
        last_ai_analysis=_as_datetime(last_ai),
        last_recommendations_calculation=_as_datetime(last_recs),
    )


def _recommendation_preview(
    db: Session,
    audit_id: UUID,
) -> tuple[RecommendationPreview, ...]:
    rows = list_recommendations(db, audit_id)[:RECOMMENDATION_PREVIEW_LIMIT]
    return tuple(
        RecommendationPreview(
            id=row.id,
            title=row.title,
            category=row.category,
            priority=row.priority,
            impact_score=_quantize(row.impact_score),
            effort_score=_quantize(row.effort_score),
        )
        for row in rows
    )


def _overall_layer(
    *,
    overall_score: object,
    ai_available: bool,
    entity_available: bool,
) -> OverallLayer:
    score = _quantize(overall_score)
    if score is None:
        return OverallLayer(
            score=None,
            status=ScoreAvailability.UNAVAILABLE,
            explanation="Not available",
        )
    if not ai_available or not entity_available:
        return OverallLayer(
            score=score,
            status=ScoreAvailability.PROVISIONAL,
            explanation=PROVISIONAL_OVERALL_EXPLANATION,
        )
    return OverallLayer(
        score=score,
        status=ScoreAvailability.AVAILABLE,
        explanation=(
            "Stored overall score from the Audit Engine. "
            "It is not recalculated on the dashboard."
        ),
    )


def _layer_status(available: bool) -> ScoreAvailability:
    return ScoreAvailability.AVAILABLE if available else ScoreAvailability.UNAVAILABLE


def _quantize(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _as_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return None
