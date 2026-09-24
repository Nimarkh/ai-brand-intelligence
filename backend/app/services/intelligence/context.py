"""Deterministic audit context and intent routing for Ask Intelligence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.audit import Audit
from app.models.enums import AuditStatus, FindingSeverity, RecommendationPriority
from app.services.ai_visibility_service import load_visibility_snapshot
from app.services.dashboard.insights import build_insights
from app.services.dashboard.models import SnapshotMetrics
from app.services.entity_service import load_entity_snapshot
from app.services.intelligence.models import (
    MAX_AI_QUERIES,
    MAX_AI_RESPONSE_EXCERPTS,
    MAX_DESCRIPTION_CHARS,
    MAX_EXCERPT_CHARS,
    MAX_RECOMMENDATIONS,
    MAX_SEO_FINDINGS,
    MAX_WEBSITE_PAGES,
    AuditFacts,
    AuditIntelligenceContext,
    BrandFacts,
    CommonFinding,
    ContextBounds,
    EntityFacts,
    EvidenceSource,
    EvidenceType,
    FindingFact,
    PageFact,
    QueryFact,
    QuestionIntent,
    RecommendationFact,
    ScoreFact,
    SeoFacts,
    VisibilityFacts,
    WebsiteFacts,
)
from app.services.intelligence.retrieval import (
    first_response,
    load_findings,
    load_pages,
    load_queries,
    load_recommendations,
)

_SEVERITY_RANK = {
    FindingSeverity.HIGH.value: 0,
    FindingSeverity.MEDIUM.value: 1,
    FindingSeverity.LOW.value: 2,
    FindingSeverity.INFO.value: 3,
}

_QUERY_PHRASES = (
    "ai quer",
    "which quer",
    "queries",
    "query ",
    "failed to mention",
)
_AI_PHRASES = (
    "ai visibility",
    "mention rate",
    "how often",
    "brand mentioned",
    "citation",
    "mentioned",
)
_ENTITY_PHRASES = (
    "entity",
    "brand identity",
    "entity presence",
)
_SEO_PHRASES = (
    "seo",
    "meta description",
    "search engine",
)
_WEBSITE_PHRASES = (
    "website",
    "pages slow",
    "page speed",
    "load time",
    "how healthy",
)
_RECOMMENDATION_PHRASES = (
    "fix first",
    "what should i fix",
    "opportunit",
    "recommend",
)
_SCORE_PHRASES = (
    "score",
    "provisional",
)
_OVERVIEW_PHRASES = (
    "overview",
    "how is my brand",
    "brand doing",
    "what should i know",
)

_NEGATIVE_MENTION = (
    "don't",
    "do not",
    "doesn't",
    "does not",
    "not mention",
    "failed to mention",
    "didn't mention",
    "did not mention",
)


def detect_intent(question: str) -> QuestionIntent:
    """Keyword router. First matching category wins. Unknown questions are GENERAL."""
    text = " ".join((question or "").lower().split())
    checks = (
        (_QUERY_PHRASES, QuestionIntent.QUERIES),
        (_AI_PHRASES, QuestionIntent.AI_VISIBILITY),
        (_ENTITY_PHRASES, QuestionIntent.ENTITY),
        (_SEO_PHRASES, QuestionIntent.SEO),
        (_WEBSITE_PHRASES, QuestionIntent.WEBSITE),
        (_RECOMMENDATION_PHRASES, QuestionIntent.RECOMMENDATIONS),
        (_SCORE_PHRASES, QuestionIntent.SCORES),
        (_OVERVIEW_PHRASES, QuestionIntent.OVERVIEW),
    )
    for phrases, intent in checks:
        if any(phrase in text for phrase in phrases):
            return intent
    return QuestionIntent.GENERAL


def build_audit_context(db: Session, audit: Audit) -> AuditIntelligenceContext:
    """Assemble a typed, bounded context from persisted rows and read-only snapshots."""
    brand = audit.brand
    pages = load_pages(db, audit.id)
    findings = load_findings(db, audit.id)
    queries = load_queries(db, audit.id)
    recommendations = load_recommendations(db, audit.id)
    visibility = load_visibility_snapshot(db, audit)
    entity = load_entity_snapshot(db, audit, brand)

    page_by_id = {page.id: page for page in pages}
    finding_counts = Counter(finding.page_id for finding in findings if finding.page_id)
    selected_pages = _select_pages(pages, finding_counts)
    selected_findings = _select_findings(findings, page_by_id)
    selected_queries, excerpt_count = _select_queries(queries)
    selected_recommendations = tuple(
        _recommendation_fact(row) for row in recommendations[:MAX_RECOMMENDATIONS]
    )

    website = _website_facts(pages, selected_pages)
    seo = _seo_facts(findings, selected_findings)
    visibility_facts = _visibility_facts(audit, queries, visibility)
    entity_facts = _entity_facts(audit, entity)
    scores = _score_facts(audit, visibility_facts.status, entity_facts.status)
    insights = _insights(audit, website, seo, visibility_facts, recommendations)

    record_ids = {audit.id}
    record_ids.update(page.id for page in pages)
    record_ids.update(finding.id for finding in findings)
    record_ids.update(query.id for query in queries)
    for query in queries:
        response = first_response(query)
        if response is not None:
            record_ids.add(response.id)
    record_ids.update(row.id for row in recommendations)

    status = audit.status.value if isinstance(audit.status, AuditStatus) else str(audit.status)
    audit_date = audit.completed_at or audit.created_at
    description = brand.description
    if description and len(description) > 500:
        description = description[:499] + "…"

    return AuditIntelligenceContext(
        brand=BrandFacts(
            name=brand.name,
            website=brand.website_url,
            industry=brand.industry,
            country=brand.country,
            target_market=brand.target_market,
            description=description,
        ),
        audit=AuditFacts(
            id=audit.id,
            status=status,
            created_at=audit.created_at,
            started_at=audit.started_at,
            completed_at=audit.completed_at,
            audit_date=audit_date,
        ),
        scores=scores,
        website=website,
        seo=seo,
        visibility=visibility_facts,
        entity=entity_facts,
        recommendations=selected_recommendations,
        queries=selected_queries,
        insights=insights,
        bounds=ContextBounds(
            seo_findings_total=len(findings),
            seo_findings_included=len(selected_findings),
            recommendations_total=len(recommendations),
            recommendations_included=len(selected_recommendations),
            queries_total=len(queries),
            queries_included=len(selected_queries),
            excerpts_included=excerpt_count,
            pages_total=len(pages),
            pages_included=len(selected_pages),
        ),
        record_ids=frozenset(record_ids),
    )


def select_evidence(
    intent: QuestionIntent,
    context: AuditIntelligenceContext,
    question: str,
) -> tuple[EvidenceSource, ...]:
    """Pick persisted records for the question. The model does not choose ids."""
    text = " ".join((question or "").lower().split())
    items: list[EvidenceSource] = []

    if intent == QuestionIntent.SEO:
        items.extend(_finding_sources(context, 5))
        items.extend(_page_sources(context, 2))
        items.extend(_recommendation_sources(context, 2, ("SEO", "META", "CONTENT")))
    elif intent == QuestionIntent.AI_VISIBILITY:
        items.extend(_visibility_sources(context))
        items.extend(_query_sources(context, text, 3))
        items.extend(_response_sources(context, text, 2))
        items.extend(_recommendation_sources(context, 2, ("AI", "VISIBILITY")))
    elif intent == QuestionIntent.ENTITY:
        items.extend(_entity_sources(context))
        items.extend(_schema_page_sources(context, 2))
        items.extend(_recommendation_sources(context, 2, ("ENTITY", "SCHEMA", "STRUCTURED")))
    elif intent == QuestionIntent.RECOMMENDATIONS:
        items.extend(_recommendation_sources(context, 5, None))
    elif intent == QuestionIntent.WEBSITE:
        items.append(_website_source(context))
        items.extend(_page_sources(context, 3))
        items.extend(_finding_sources(context, 2))
    elif intent == QuestionIntent.QUERIES:
        items.extend(_query_sources(context, text, 5))
        items.extend(_response_sources(context, text, 2))
        items.extend(_visibility_sources(context))
    elif intent == QuestionIntent.SCORES:
        items.extend(_score_sources(context))
        items.extend(_visibility_sources(context))
        items.extend(_entity_sources(context))
    else:
        items.extend(_score_sources(context)[:1])
        items.extend(_finding_sources(context, 2))
        items.extend(_recommendation_sources(context, 2, None))
        items.extend(_visibility_sources(context))
        items.extend(_entity_sources(context)[:1])

    if not items:
        items.extend(_score_sources(context)[:1])

    unique: list[EvidenceSource] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        if item.id not in context.record_ids:
            continue
        key = (item.type, str(item.id), item.label)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= 8:
            break
    return tuple(unique)


def context_for_prompt(context: AuditIntelligenceContext, intent: QuestionIntent) -> dict:
    """JSON-ready context. GENERAL includes every bounded section."""
    header = {
        "brand": {
            "name": context.brand.name,
            "website": context.brand.website,
            "industry": context.brand.industry,
            "country": context.brand.country,
            "target_market": context.brand.target_market,
            "description": context.brand.description,
        },
        "audit": {
            "id": str(context.audit.id),
            "status": context.audit.status,
            "created_at": _iso(context.audit.created_at),
            "started_at": _iso(context.audit.started_at),
            "completed_at": _iso(context.audit.completed_at),
            "audit_date": _iso(context.audit.audit_date),
        },
        "scores": [_score_dict(score) for score in context.scores],
        "bounds": {
            "seo_findings_total": context.bounds.seo_findings_total,
            "seo_findings_included": context.bounds.seo_findings_included,
            "recommendations_total": context.bounds.recommendations_total,
            "recommendations_included": context.bounds.recommendations_included,
            "queries_total": context.bounds.queries_total,
            "queries_included": context.bounds.queries_included,
            "excerpts_included": context.bounds.excerpts_included,
            "pages_total": context.bounds.pages_total,
            "pages_included": context.bounds.pages_included,
        },
    }
    sections = {
        "website": _website_dict(context),
        "seo": _seo_dict(context),
        "ai_visibility": _visibility_dict(context),
        "entity": _entity_dict(context),
        "recommendations": {
            "items": [_recommendation_dict(row) for row in context.recommendations],
        },
        "queries": {"items": [_query_dict(row) for row in context.queries]},
        "insights": list(context.insights),
    }
    if intent == QuestionIntent.GENERAL:
        header.update(sections)
        return header

    wanted = {
        QuestionIntent.OVERVIEW: ("website", "seo", "ai_visibility", "entity", "recommendations", "insights"),
        QuestionIntent.SCORES: ("ai_visibility", "entity", "insights"),
        QuestionIntent.SEO: ("seo", "website", "recommendations"),
        QuestionIntent.AI_VISIBILITY: ("ai_visibility", "queries", "recommendations"),
        QuestionIntent.ENTITY: ("entity", "website", "recommendations"),
        QuestionIntent.RECOMMENDATIONS: ("recommendations", "seo", "insights"),
        QuestionIntent.WEBSITE: ("website", "seo"),
        QuestionIntent.QUERIES: ("queries", "ai_visibility"),
    }[intent]
    for key in wanted:
        header[key] = sections[key]
    return header


def _score_facts(audit: Audit, visibility_status: str, entity_status: str) -> tuple[ScoreFact, ...]:
    overall_status = _overall_status(audit)
    overall_note = None
    if overall_status == "PROVISIONAL":
        overall_note = (
            "Based on currently available website and SEO signals. "
            "AI Visibility and Entity Strength are not yet included in the overall score."
        )
    elif overall_status == "UNAVAILABLE":
        overall_note = "Overall score has not been stored for this audit."
    else:
        overall_note = "Stored overall score. It is not recalculated by Ask Intelligence."

    return (
        ScoreFact("overall", _decimal(audit.overall_score), overall_status, overall_note),
        ScoreFact(
            "website",
            _decimal(audit.website_score),
            _stored_status(audit.website_score),
            "Persisted website health score.",
        ),
        ScoreFact(
            "seo",
            _decimal(audit.seo_score),
            _stored_status(audit.seo_score),
            "Persisted SEO score.",
        ),
        ScoreFact(
            "ai_visibility",
            _decimal(audit.ai_visibility_score),
            visibility_status,
            "Persisted AI visibility score. Component metrics come from the stored snapshot.",
        ),
        ScoreFact(
            "entity",
            _decimal(audit.entity_score),
            entity_status,
            "Persisted entity score.",
        ),
        ScoreFact(
            "semantic",
            _decimal(audit.semantic_score),
            _stored_status(audit.semantic_score),
            "Persisted semantic score.",
        ),
    )


def _overall_status(audit: Audit) -> str:
    if audit.overall_score is None:
        return "UNAVAILABLE"
    if audit.ai_visibility_score is None or audit.entity_score is None:
        return "PROVISIONAL"
    return "AVAILABLE"


def _stored_status(value: object) -> str:
    return "AVAILABLE" if value is not None else "UNAVAILABLE"


def _website_facts(pages: list, selected: tuple[PageFact, ...]) -> WebsiteFacts:
    analyzable = sum(1 for page in pages if _analyzable(page.status_code))
    with_schema = sum(1 for page in pages if page.has_schema is True)
    loads = [page.load_time_ms for page in pages if page.load_time_ms is not None]
    average = int(sum(loads) / len(loads)) if loads else None
    coverage = None
    if pages:
        coverage = (Decimal(with_schema) / Decimal(len(pages))).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
    distribution = Counter(
        str(page.status_code) if page.status_code is not None else "unknown" for page in pages
    )
    ordered = tuple(sorted(distribution.items(), key=lambda item: (-item[1], item[0])))
    return WebsiteFacts(
        page_count=len(pages),
        analyzable_page_count=analyzable,
        status_distribution=ordered,
        average_load_time_ms=average,
        structured_data_coverage=coverage,
        pages_with_schema=with_schema,
        pages=selected,
    )


def _select_pages(pages: list, finding_counts: Counter) -> tuple[PageFact, ...]:
    ordered = sorted(
        pages,
        key=lambda page: (
            -int(finding_counts.get(page.id, 0)),
            -(page.load_time_ms if page.load_time_ms is not None else -1),
            str(page.id),
        ),
    )
    return tuple(_page_fact(page) for page in ordered[:MAX_WEBSITE_PAGES])


def _page_fact(page) -> PageFact:
    return PageFact(
        id=page.id,
        url=page.url,
        status_code=page.status_code,
        title=page.title,
        load_time_ms=page.load_time_ms,
        has_schema=page.has_schema,
        word_count=page.word_count,
    )


def _seo_facts(findings: list, selected: tuple[FindingFact, ...]) -> SeoFacts:
    by_severity: Counter[str] = Counter(_enum_value(row.severity) for row in findings)
    by_category: Counter[str] = Counter(row.category for row in findings)
    grouped: dict[str, list] = {}
    for row in findings:
        grouped.setdefault(row.title, []).append(row)
    common: list[CommonFinding] = []
    for title, rows in grouped.items():
        representative = sorted(rows, key=_finding_sort_key)[0]
        common.append(
            CommonFinding(
                title=title,
                category=representative.category,
                severity=_enum_value(representative.severity),
                count=len(rows),
                representative_id=representative.id,
            )
        )
    common.sort(key=lambda item: (-item.count, _SEVERITY_RANK.get(item.severity, 9), item.title))
    return SeoFacts(
        total=len(findings),
        by_severity=tuple(sorted(by_severity.items(), key=lambda item: (_SEVERITY_RANK.get(item[0], 9), item[0]))),
        by_category=tuple(sorted(by_category.items(), key=lambda item: (-item[1], item[0]))),
        common=tuple(common[:8]),
        findings=selected,
    )


def _select_findings(findings: list, page_by_id: dict) -> tuple[FindingFact, ...]:
    ordered = sorted(findings, key=_finding_sort_key)
    facts: list[FindingFact] = []
    for row in ordered[:MAX_SEO_FINDINGS]:
        page = page_by_id.get(row.page_id) if row.page_id else None
        description = row.description
        if description and len(description) > MAX_DESCRIPTION_CHARS:
            description = description[: MAX_DESCRIPTION_CHARS - 1] + "…"
        facts.append(
            FindingFact(
                id=row.id,
                title=row.title,
                category=row.category,
                severity=_enum_value(row.severity),
                page_id=row.page_id,
                page_url=page.url if page is not None else None,
                description=description,
            )
        )
    return tuple(facts)


def _finding_sort_key(row) -> tuple:
    created = row.created_at.timestamp() if row.created_at is not None else 0
    return (_SEVERITY_RANK.get(_enum_value(row.severity), 9), -created, str(row.id))


def _select_queries(queries: list) -> tuple[tuple[QueryFact, ...], int]:
    def sort_key(query) -> tuple:
        response = first_response(query)
        if response is None:
            mention_rank = 1
        elif response.brand_mentioned is False:
            mention_rank = 0
        elif response.brand_mentioned is True:
            mention_rank = 2
        else:
            mention_rank = 1
        created = query.created_at.timestamp() if query.created_at is not None else 0
        return (mention_rank, -created, str(query.id))

    ordered = sorted(queries, key=sort_key)[:MAX_AI_QUERIES]
    facts: list[QueryFact] = []
    excerpts = 0
    for query in ordered:
        response = first_response(query)
        excerpt = None
        response_id = None
        mentioned = None
        position = None
        cited = None
        if response is not None:
            response_id = response.id
            mentioned = response.brand_mentioned
            position = response.brand_position
            cited = response.citation_found
            if excerpts < MAX_AI_RESPONSE_EXCERPTS and response.response_text:
                excerpt = " ".join(response.response_text.split())
                if len(excerpt) > MAX_EXCERPT_CHARS:
                    excerpt = excerpt[: MAX_EXCERPT_CHARS - 1] + "…"
                excerpts += 1
        category = query.category.value if hasattr(query.category, "value") else str(query.category)
        facts.append(
            QueryFact(
                id=query.id,
                query_text=query.query_text,
                category=category,
                has_response=response is not None,
                response_id=response_id,
                brand_mentioned=mentioned,
                brand_position=position,
                citation_found=cited,
                excerpt=excerpt,
            )
        )
    return tuple(facts), excerpts


def _visibility_facts(audit: Audit, queries: list, snapshot) -> VisibilityFacts:
    responses = [first_response(query) for query in queries]
    present = [row for row in responses if row is not None]
    mentions = sum(1 for row in present if row.brand_mentioned is True)
    citations = sum(1 for row in present if row.citation_found is True)
    metrics = snapshot.metrics
    components = tuple(
        (item.name, item.score, item.status.value if hasattr(item.status, "value") else str(item.status))
        for item in snapshot.components
    )
    note = None
    status = snapshot.status.value if hasattr(snapshot.status, "value") else str(snapshot.status)
    if status == "UNAVAILABLE":
        note = "AI Visibility is unavailable for this audit. Unavailable is not zero."
    elif status == "PROVISIONAL":
        note = "AI Visibility is provisional because some queries have no stored response."
    return VisibilityFacts(
        status=status,
        persisted_score=_decimal(audit.ai_visibility_score),
        semantic_score=_decimal(audit.semantic_score),
        total_queries=len(queries),
        successful_responses=len(present),
        failed_responses=len(queries) - len(present),
        mention_count=mentions,
        citation_count=citations,
        mention_rate=metrics.mention_rate,
        citation_rate=metrics.citation_rate,
        average_position=metrics.average_position,
        position_score=metrics.position_score,
        semantic_alignment=metrics.semantic_alignment,
        response_coverage=snapshot.response_coverage,
        components=components,
        note=note,
    )


def _entity_facts(audit: Audit, snapshot) -> EntityFacts:
    by_name = {item.name: item.score for item in snapshot.components}
    status = snapshot.status.value if hasattr(snapshot.status, "value") else str(snapshot.status)
    evidence = snapshot.evidence
    note = snapshot.notes[0] if snapshot.notes else None
    return EntityFacts(
        status=status,
        persisted_score=_decimal(audit.entity_score),
        presence=by_name.get("presence"),
        consistency=by_name.get("consistency"),
        structured_identity=by_name.get("structured_identity"),
        ai_recognition=by_name.get("ai_recognition"),
        analyzable_pages=evidence.analyzable_pages,
        pages_with_brand_in_title=evidence.pages_with_brand_in_title,
        pages_with_schema=evidence.pages_with_schema,
        pages_with_entity_schema=evidence.pages_with_entity_schema,
        responses_mentioning_brand=evidence.responses_mentioning_brand,
        note=note,
    )


def _recommendation_fact(row) -> RecommendationFact:
    description = row.description
    if description and len(description) > MAX_DESCRIPTION_CHARS:
        description = description[: MAX_DESCRIPTION_CHARS - 1] + "…"
    priority = row.priority.value if isinstance(row.priority, RecommendationPriority) else str(row.priority)
    return RecommendationFact(
        id=row.id,
        title=row.title,
        category=row.category,
        priority=priority,
        impact_score=_decimal(row.impact_score),
        effort_score=_decimal(row.effort_score),
        description=description,
    )


def _insights(audit: Audit, website: WebsiteFacts, seo: SeoFacts, visibility: VisibilityFacts, recommendations: list) -> tuple[str, ...]:
    high = sum(1 for row in recommendations if _enum_value(row.priority) == RecommendationPriority.HIGH.value)
    medium = sum(1 for row in recommendations if _enum_value(row.priority) == RecommendationPriority.MEDIUM.value)
    has_seo = seo.total > 0 or audit.seo_score is not None
    has_ai = visibility.total_queries > 0 or audit.ai_visibility_score is not None
    has_recs = len(recommendations) > 0
    mention_rate = None
    if visibility.successful_responses > 0:
        mention_rate = (
            Decimal(visibility.mention_count) / Decimal(visibility.successful_responses)
        ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    coverage = None
    if visibility.total_queries > 0:
        coverage = (
            Decimal(visibility.successful_responses) / Decimal(visibility.total_queries)
        ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    snapshot = SnapshotMetrics(
        pages_crawled=website.page_count if website.page_count or audit.status == AuditStatus.COMPLETED else None,
        seo_findings=seo.total if has_seo or website.page_count else None,
        high_severity_findings=dict(seo.by_severity).get(FindingSeverity.HIGH.value, 0) if has_seo else None,
        ai_queries=visibility.total_queries if has_ai else None,
        ai_successful_responses=visibility.successful_responses if has_ai else None,
        ai_response_coverage=coverage if has_ai else None,
        ai_mention_rate=mention_rate if has_ai and visibility.successful_responses else None,
        ai_mentions=visibility.mention_count if has_ai and visibility.successful_responses else None,
        pages_with_schema=website.pages_with_schema if website.page_count else None,
        structured_identity_coverage=website.structured_data_coverage if website.page_count else None,
        recommendations_total=len(recommendations) if has_recs else None,
        recommendations_high=high if has_recs else None,
        recommendations_medium=medium if has_recs else None,
        entity_pages_analyzed=website.page_count if audit.entity_score is not None and website.page_count else None,
    )
    return tuple(item.text for item in build_insights(snapshot))


def _finding_sources(context: AuditIntelligenceContext, limit: int) -> list[EvidenceSource]:
    sources: list[EvidenceSource] = []
    for issue in context.seo.common[:limit]:
        label = issue.title
        if issue.count > 1:
            label = f"{issue.title} — {issue.count} pages"
        sources.append(
            EvidenceSource(type=EvidenceType.SEO_FINDING.value, id=issue.representative_id, label=label)
        )
    if sources:
        return sources
    return [
        EvidenceSource(type=EvidenceType.SEO_FINDING.value, id=row.id, label=row.title)
        for row in context.seo.findings[:limit]
    ]


def _page_sources(context: AuditIntelligenceContext, limit: int) -> list[EvidenceSource]:
    sources: list[EvidenceSource] = []
    for page in context.website.pages[:limit]:
        label = page.title or page.url
        if page.load_time_ms is not None:
            label = f"{label} — {page.load_time_ms} ms"
        sources.append(EvidenceSource(type=EvidenceType.WEBSITE_PAGE.value, id=page.id, label=label))
    return sources


def _schema_page_sources(context: AuditIntelligenceContext, limit: int) -> list[EvidenceSource]:
    chosen = [page for page in context.website.pages if page.has_schema] or list(context.website.pages)
    sources: list[EvidenceSource] = []
    for page in chosen[:limit]:
        label = page.title or page.url
        if page.has_schema:
            label = f"{label} — structured data present"
        sources.append(EvidenceSource(type=EvidenceType.WEBSITE_PAGE.value, id=page.id, label=label))
    return sources


def _recommendation_sources(
    context: AuditIntelligenceContext,
    limit: int,
    keywords: tuple[str, ...] | None,
) -> list[EvidenceSource]:
    rows = list(context.recommendations)
    if keywords:
        matched = [
            row
            for row in rows
            if any(keyword in row.category.upper() or keyword in row.title.upper() for keyword in keywords)
        ]
        if matched:
            rows = matched
    sources: list[EvidenceSource] = []
    for row in rows[:limit]:
        label = row.title
        if row.priority == RecommendationPriority.HIGH.value:
            label = f"High-priority recommendation — {row.title}"
        sources.append(EvidenceSource(type=EvidenceType.RECOMMENDATION.value, id=row.id, label=label))
    return sources


def _query_sources(context: AuditIntelligenceContext, question: str, limit: int) -> list[EvidenceSource]:
    rows = _queries_for_question(context, question)
    sources: list[EvidenceSource] = []
    for row in rows[:limit]:
        state = "no stored response"
        if row.brand_mentioned is True:
            state = "brand mentioned"
        elif row.brand_mentioned is False:
            state = "brand not mentioned"
        label = row.query_text if len(row.query_text) <= 80 else row.query_text[:79] + "…"
        sources.append(
            EvidenceSource(type=EvidenceType.AI_QUERY.value, id=row.id, label=f"{label} — {state}")
        )
    return sources


def _response_sources(context: AuditIntelligenceContext, question: str, limit: int) -> list[EvidenceSource]:
    rows = [row for row in _queries_for_question(context, question) if row.response_id is not None]
    sources: list[EvidenceSource] = []
    for row in rows[:limit]:
        label = "Stored AI response"
        if row.brand_mentioned is False:
            label = "Stored AI response — brand not mentioned"
        elif row.brand_mentioned is True:
            label = "Stored AI response — brand mentioned"
        sources.append(EvidenceSource(type=EvidenceType.AI_RESPONSE.value, id=row.response_id, label=label))  # type: ignore[arg-type]
    return sources


def _queries_for_question(context: AuditIntelligenceContext, question: str) -> list:
    rows = list(context.queries)
    negative = any(phrase in question for phrase in _NEGATIVE_MENTION)
    if negative:
        preferred = [row for row in rows if row.brand_mentioned is False or not row.has_response]
        return preferred or rows
    if "mention" in question:
        preferred = [row for row in rows if row.brand_mentioned is True]
        return preferred or rows
    return rows


def _visibility_sources(context: AuditIntelligenceContext) -> list[EvidenceSource]:
    rate = _percent(context.visibility.mention_rate)
    if rate is None and context.visibility.successful_responses:
        rate = _percent(Decimal(context.visibility.mention_count) / Decimal(context.visibility.successful_responses))
    label = f"Mention rate: {rate}" if rate else "Mention rate: unavailable"
    citation = _percent(context.visibility.citation_rate)
    sources = [
        EvidenceSource(
            type=EvidenceType.AI_VISIBILITY_METRIC.value,
            id=context.audit.id,
            label=label,
        )
    ]
    if citation is not None:
        sources.append(
            EvidenceSource(
                type=EvidenceType.AI_VISIBILITY_METRIC.value,
                id=context.audit.id,
                label=f"Citation rate: {citation}",
            )
        )
    return sources


def _entity_sources(context: AuditIntelligenceContext) -> list[EvidenceSource]:
    presence = _score_number(context.entity.presence)
    if presence is None:
        label = f"Entity presence: {context.entity.status.lower()}"
    else:
        label = f"Entity presence: {presence}"
    consistency = _score_number(context.entity.consistency)
    sources = [
        EvidenceSource(type=EvidenceType.ENTITY_METRIC.value, id=context.audit.id, label=label)
    ]
    if consistency is not None:
        sources.append(
            EvidenceSource(
                type=EvidenceType.ENTITY_METRIC.value,
                id=context.audit.id,
                label=f"Entity consistency: {consistency}",
            )
        )
    return sources


def _score_sources(context: AuditIntelligenceContext) -> list[EvidenceSource]:
    sources: list[EvidenceSource] = []
    for score in context.scores:
        shown = _score_number(score.score)
        value = shown if shown is not None else "unavailable"
        sources.append(
            EvidenceSource(
                type=EvidenceType.AUDIT_SCORE.value,
                id=context.audit.id,
                label=f"{score.name.replace('_', ' ').title()} score: {value} ({score.status})",
            )
        )
    return sources


def _website_source(context: AuditIntelligenceContext) -> EvidenceSource:
    average = (
        f"{context.website.average_load_time_ms} ms average load"
        if context.website.average_load_time_ms is not None
        else "load time unavailable"
    )
    return EvidenceSource(
        type=EvidenceType.WEBSITE_PAGE.value,
        id=context.audit.id if not context.website.pages else context.website.pages[0].id,
        label=f"{context.website.page_count} pages — {average}",
    )


def _score_dict(score: ScoreFact) -> dict:
    return {
        "name": score.name,
        "score": _number(score.score),
        "status": score.status,
        "note": score.note,
        "kind": "persisted_score",
    }


def _website_dict(context: AuditIntelligenceContext) -> dict:
    return {
        "page_count": context.website.page_count,
        "analyzable_page_count": context.website.analyzable_page_count,
        "status_distribution": [
            {"status_code": code, "count": count} for code, count in context.website.status_distribution
        ],
        "average_load_time_ms": context.website.average_load_time_ms,
        "structured_data_coverage": _number(context.website.structured_data_coverage),
        "pages_with_schema": context.website.pages_with_schema,
        "pages": [
            {
                "id": str(page.id),
                "url": page.url,
                "status_code": page.status_code,
                "title": page.title,
                "load_time_ms": page.load_time_ms,
                "has_schema": page.has_schema,
                "word_count": page.word_count,
            }
            for page in context.website.pages
        ],
    }


def _seo_dict(context: AuditIntelligenceContext) -> dict:
    return {
        "total": context.seo.total,
        "by_severity": [{"severity": name, "count": count} for name, count in context.seo.by_severity],
        "by_category": [{"category": name, "count": count} for name, count in context.seo.by_category],
        "common": [
            {
                "title": issue.title,
                "category": issue.category,
                "severity": issue.severity,
                "count": issue.count,
                "id": str(issue.representative_id),
            }
            for issue in context.seo.common
        ],
        "findings": [
            {
                "id": str(row.id),
                "title": row.title,
                "category": row.category,
                "severity": row.severity,
                "page_url": row.page_url,
                "description": row.description,
            }
            for row in context.seo.findings
        ],
    }


def _visibility_dict(context: AuditIntelligenceContext) -> dict:
    visibility = context.visibility
    return {
        "status": visibility.status,
        "persisted_score": _number(visibility.persisted_score),
        "semantic_score": _number(visibility.semantic_score),
        "total_queries": visibility.total_queries,
        "successful_responses": visibility.successful_responses,
        "failed_responses": visibility.failed_responses,
        "mention_count": visibility.mention_count,
        "citation_count": visibility.citation_count,
        "mention_rate": _number(visibility.mention_rate),
        "citation_rate": _number(visibility.citation_rate),
        "average_position": _number(visibility.average_position),
        "position_score": _number(visibility.position_score),
        "semantic_alignment": _number(visibility.semantic_alignment),
        "response_coverage": _number(visibility.response_coverage),
        "components": [
            {"name": name, "score": _number(score), "status": status}
            for name, score, status in visibility.components
        ],
        "note": visibility.note,
        "kind": "calculated_metric",
    }


def _entity_dict(context: AuditIntelligenceContext) -> dict:
    entity = context.entity
    return {
        "status": entity.status,
        "persisted_score": _number(entity.persisted_score),
        "presence": _number(entity.presence),
        "consistency": _number(entity.consistency),
        "structured_identity": _number(entity.structured_identity),
        "ai_recognition": _number(entity.ai_recognition),
        "analyzable_pages": entity.analyzable_pages,
        "pages_with_brand_in_title": entity.pages_with_brand_in_title,
        "pages_with_schema": entity.pages_with_schema,
        "pages_with_entity_schema": entity.pages_with_entity_schema,
        "responses_mentioning_brand": entity.responses_mentioning_brand,
        "note": entity.note,
        "kind": "calculated_metric",
    }


def _recommendation_dict(row: RecommendationFact) -> dict:
    return {
        "id": str(row.id),
        "title": row.title,
        "category": row.category,
        "priority": row.priority,
        "impact_score": _number(row.impact_score),
        "effort_score": _number(row.effort_score),
        "description": row.description,
        "kind": "recommendation",
    }


def _query_dict(row: QueryFact) -> dict:
    return {
        "id": str(row.id),
        "query_text": row.query_text,
        "category": row.category,
        "has_response": row.has_response,
        "response_id": str(row.response_id) if row.response_id else None,
        "brand_mentioned": row.brand_mentioned,
        "brand_position": row.brand_position,
        "citation_found": row.citation_found,
        "excerpt": row.excerpt,
    }


def _analyzable(status_code: int | None) -> bool:
    return status_code is not None and 200 <= status_code < 400


def _enum_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _number(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _score_number(value: Decimal | None) -> str | None:
    if value is None:
        return None
    shown = f"{_decimal(value):f}"
    if "." in shown:
        shown = shown.rstrip("0").rstrip(".")
    return shown


def _percent(value: Decimal | None) -> str | None:
    if value is None:
        return None
    pct = (Decimal(str(value)) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{int(pct)}%"


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
