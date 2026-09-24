"""Build a report snapshot from rows that are already stored.

This module reads score columns and related tables. It does not assign score
columns, crawl, call an AI provider, or run recommendation generation.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.enums import FindingSeverity
from app.models.website import SeoFinding, WebsitePage
from app.services.ai_visibility_service import load_visibility_snapshot
from app.services.dashboard.service import PROVISIONAL_OVERALL_EXPLANATION
from app.services.entity_service import load_entity_snapshot
from app.services.recommendation_service import list_recommendations
from app.services.reports.models import (
    MAX_COMMON_ISSUES,
    MAX_DESCRIPTION,
    MAX_FINDINGS,
    MAX_QUERY_EXAMPLES,
    MAX_QUERY_TEXT,
    MAX_RECOMMENDATIONS,
    REPORT_SECTIONS,
    REPORT_TYPE,
    AuditBlock,
    BrandBlock,
    CategoryCount,
    EntityBlock,
    FindingLine,
    IssueCount,
    QueryBlock,
    QueryExample,
    RecommendationLine,
    ReportSnapshot,
    ScoreLine,
    SeoBlock,
    VisibilityBlock,
    WebsiteBlock,
)
from app.services.reports.security import redact_secrets, report_title

METHODOLOGY: tuple[str, ...] = (
    "Scores in this report are the values stored by the platform's deterministic scoring engines for the selected audit.",
    "Generating this report does not recalculate Website Health, SEO, AI Visibility, Entity Strength, the overall score, or recommendations.",
    "AI Visibility uses persisted AI query and response analysis. No new AI analysis is run for this report.",
    "Recommendations are the stored recommendations for this audit, in their existing priority order.",
    "Unavailable components are not treated as zero.",
    "This report is a snapshot of the selected audit. Later changes to the audit do not modify this file.",
)

_SEVERITY_RANK = {
    FindingSeverity.HIGH: 0,
    FindingSeverity.MEDIUM: 1,
    FindingSeverity.LOW: 2,
    FindingSeverity.INFO: 3,
}


def build_snapshot(
    db: Session,
    audit: Audit,
    brand: Brand,
    *,
    generated_at: datetime,
) -> ReportSnapshot:
    pages = _pages(db, audit.id)
    findings = _findings(db, audit.id)
    queries = _queries(db, audit.id)
    page_urls = {page.id: page.url for page in pages}

    scores, overall = _scores(audit)
    return ReportSnapshot(
        report_type=REPORT_TYPE,
        title=report_title(brand.name),
        generated_at=generated_at,
        brand=_brand(brand),
        audit=AuditBlock(
            id=audit.id,
            status=_enum_value(audit.status),
            created_at=audit.created_at,
            completed_at=audit.completed_at,
        ),
        scores=scores,
        overall=overall,
        website=_website(pages, findings),
        seo=_seo(findings, page_urls),
        visibility=_visibility(db, audit, queries),
        entity=_entity(db, audit, brand),
        recommendations=_recommendations(db, audit.id),
        queries=_query_summary(queries),
        methodology=METHODOLOGY,
        sections=REPORT_SECTIONS,
    )


def _brand(brand: Brand) -> BrandBlock:
    return BrandBlock(
        name=redact_secrets(brand.name).strip() or "Brand",
        website=_blank_to_none(redact_secrets(brand.website_url)),
        industry=_blank_to_none(redact_secrets(brand.industry)),
        country=_blank_to_none(redact_secrets(brand.country)),
        target_market=_blank_to_none(redact_secrets(brand.target_market)),
        description=_clip(redact_secrets(brand.description), 500),
    )


def _scores(audit: Audit) -> tuple[tuple[ScoreLine, ...], ScoreLine]:
    visibility_available = audit.ai_visibility_score is not None
    entity_available = audit.entity_score is not None
    if audit.overall_score is None:
        overall_status = "UNAVAILABLE"
        overall_note = "Not available"
    elif not visibility_available or not entity_available:
        overall_status = "PROVISIONAL"
        overall_note = PROVISIONAL_OVERALL_EXPLANATION
    else:
        overall_status = "AVAILABLE"
        overall_note = (
            "Stored overall score from the Audit Engine. "
            "It is not recalculated for this report."
        )
    overall = ScoreLine(
        key="overall",
        label="Overall",
        score=_decimal(audit.overall_score),
        status=overall_status,
        note=overall_note,
    )
    lines = (
        overall,
        ScoreLine("website_health", "Website Health", _decimal(audit.website_score), _availability(audit.website_score)),
        ScoreLine("seo", "SEO", _decimal(audit.seo_score), _availability(audit.seo_score)),
        ScoreLine(
            "ai_visibility",
            "AI Visibility",
            _decimal(audit.ai_visibility_score),
            _availability(audit.ai_visibility_score),
        ),
        ScoreLine("entity", "Entity", _decimal(audit.entity_score), _availability(audit.entity_score)),
    )
    return lines, overall


def _website(pages: list[WebsitePage], findings: list[SeoFinding]) -> WebsiteBlock:
    loads = [page.load_time_ms for page in pages if page.load_time_ms is not None]
    known_schema = [page for page in pages if page.has_schema is not None]
    coverage = None
    if known_schema:
        covered = sum(1 for page in known_schema if page.has_schema)
        coverage = Decimal(covered) / Decimal(len(known_schema))
    counts = Counter(finding.title for finding in findings if finding.title)
    issues = tuple(
        IssueCount(title=title, count=count)
        for title, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:MAX_COMMON_ISSUES]
    )
    return WebsiteBlock(
        pages_crawled=len(pages),
        analyzable_pages=sum(1 for page in pages if _analyzable(page.status_code)),
        successful_http=sum(1 for page in pages if _status_in(page.status_code, 200, 300)),
        client_errors=sum(1 for page in pages if _status_in(page.status_code, 400, 500)),
        server_errors=sum(1 for page in pages if _status_in(page.status_code, 500, 600)),
        average_load_ms=_mean(loads),
        structured_data_coverage=coverage,
        common_issues=issues,
    )


def _seo(findings: list[SeoFinding], page_urls: dict[UUID, str]) -> SeoBlock:
    categories = Counter(finding.category or "Uncategorized" for finding in findings)
    ranked = sorted(
        findings,
        key=lambda finding: (
            _SEVERITY_RANK.get(finding.severity, 9),
            finding.title or "",
            str(finding.id),
        ),
    )
    lines = tuple(
        FindingLine(
            title=finding.title,
            severity=_enum_value(finding.severity),
            category=finding.category,
            description=_clip(redact_secrets(finding.description), 240),
            page_url=page_urls.get(finding.page_id) if finding.page_id else None,
        )
        for finding in ranked[:MAX_FINDINGS]
    )
    return SeoBlock(
        total=len(findings),
        high=sum(1 for finding in findings if finding.severity == FindingSeverity.HIGH),
        medium=sum(1 for finding in findings if finding.severity == FindingSeverity.MEDIUM),
        low=sum(1 for finding in findings if finding.severity == FindingSeverity.LOW),
        info=sum(1 for finding in findings if finding.severity == FindingSeverity.INFO),
        categories=tuple(
            CategoryCount(category=name, count=count)
            for name, count in sorted(categories.items(), key=lambda item: (-item[1], item[0]))
        ),
        findings=lines,
    )


def _visibility(db: Session, audit: Audit, queries: list[AiQuery]) -> VisibilityBlock:
    successful = sum(1 for query in queries if _first_response(query) is not None)
    mention_rate = None
    citation_rate = None
    average_position = None
    position_score = None
    semantic_alignment = None
    semantic_score = _decimal(audit.semantic_score)
    status = _availability(audit.ai_visibility_score)
    if audit.ai_visibility_score is not None:
        live = load_visibility_snapshot(db, audit)
        metrics = live.metrics
        mention_rate = _decimal(metrics.mention_rate)
        citation_rate = _decimal(metrics.citation_rate)
        average_position = _decimal(metrics.average_position)
        position_score = _decimal(metrics.position_score)
        semantic_alignment = _decimal(metrics.semantic_alignment)
        if semantic_score is None:
            semantic_score = _decimal(metrics.semantic_score)
        status = _enum_value(live.status)
    return VisibilityBlock(
        score=_decimal(audit.ai_visibility_score),
        status=status,
        mention_rate=mention_rate,
        citation_rate=citation_rate,
        average_position=average_position,
        position_score=position_score,
        semantic_alignment=semantic_alignment,
        semantic_score=semantic_score,
        successful_responses=successful,
        total_queries=len(queries),
    )


def _entity(db: Session, audit: Audit, brand: Brand) -> EntityBlock:
    presence = consistency = structured = recognition = None
    status = _availability(audit.entity_score)
    if audit.entity_score is not None:
        live = load_entity_snapshot(db, audit, brand)
        presence = _component(live.components, "presence")
        consistency = _component(live.components, "consistency")
        structured = _component(live.components, "structured_identity")
        recognition = _component(live.components, "ai_recognition")
        status = _enum_value(live.status)
    return EntityBlock(
        score=_decimal(audit.entity_score),
        status=status,
        presence=presence,
        consistency=consistency,
        structured_identity=structured,
        ai_recognition=recognition,
    )


def _recommendations(db: Session, audit_id: UUID) -> tuple[RecommendationLine, ...]:
    rows = list_recommendations(db, audit_id)[:MAX_RECOMMENDATIONS]
    return tuple(
        RecommendationLine(
            title=row.title,
            description=_clip(redact_secrets(row.description), MAX_DESCRIPTION),
            category=row.category,
            priority=_enum_value(row.priority),
            impact=_decimal(row.impact_score),
            effort=_decimal(row.effort_score),
        )
        for row in rows
    )


def _query_summary(queries: list[AiQuery]) -> QueryBlock:
    firsts = [(query, _first_response(query)) for query in queries]
    mentions = 0
    citations = 0
    ranked: list[tuple[int, int, datetime, QueryExample]] = []
    for query, response in firsts:
        mentioned = bool(response and response.brand_mentioned)
        cited = bool(response and response.citation_found)
        if mentioned:
            mentions += 1
        if cited:
            citations += 1
        example = QueryExample(
            text=_clip(redact_secrets(query.query_text), MAX_QUERY_TEXT) or "Query",
            category=_enum_value(query.category),
            brand_mentioned=mentioned,
            citation_found=cited,
        )
        ranked.append((1 if mentioned else 0, 1 if cited else 0, query.created_at, example))
    categories = Counter(_enum_value(query.category) for query in queries)
    chosen = tuple(
        item[3]
        for item in sorted(ranked, key=lambda item: (-item[0], -item[1], _sort_time(item[2])))[:MAX_QUERY_EXAMPLES]
    )
    successful = sum(1 for _query, response in firsts if response is not None)
    return QueryBlock(
        total_queries=len(queries),
        successful_responses=successful,
        brand_mentions=mentions,
        citations=citations,
        categories=tuple(
            CategoryCount(category=name, count=count)
            for name, count in sorted(categories.items(), key=lambda item: (-item[1], item[0]))
        ),
        examples=chosen,
    )


def _pages(db: Session, audit_id: UUID) -> list[WebsitePage]:
    return list(
        db.scalars(
            select(WebsitePage)
            .where(WebsitePage.audit_id == audit_id)
            .order_by(WebsitePage.created_at.asc(), WebsitePage.id.asc())
        ).all()
    )


def _findings(db: Session, audit_id: UUID) -> list[SeoFinding]:
    return list(db.scalars(select(SeoFinding).where(SeoFinding.audit_id == audit_id)).all())


def _queries(db: Session, audit_id: UUID) -> list[AiQuery]:
    return list(
        db.scalars(
            select(AiQuery)
            .where(AiQuery.audit_id == audit_id)
            .options(selectinload(AiQuery.responses))
            .order_by(AiQuery.created_at.asc(), AiQuery.id.asc())
        ).all()
    )


def _first_response(query: AiQuery) -> AiResponse | None:
    if not query.responses:
        return None
    return sorted(query.responses, key=lambda row: (_sort_time(row.created_at), str(row.id)))[0]


def _component(components: tuple, name: str) -> Decimal | None:
    for component in components:
        if component.name == name:
            return _decimal(component.score)
    return None


def _availability(score: object) -> str:
    return "AVAILABLE" if score is not None else "UNAVAILABLE"


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _mean(values: list[int]) -> Decimal | None:
    if not values:
        return None
    return (Decimal(sum(values)) / Decimal(len(values))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _analyzable(status_code: int | None) -> bool:
    return status_code is not None and 200 <= status_code < 400


def _status_in(status_code: int | None, start: int, end: int) -> bool:
    return status_code is not None and start <= status_code < end


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _sort_time(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()
