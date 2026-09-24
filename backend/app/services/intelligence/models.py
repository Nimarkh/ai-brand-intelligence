"""Typed models for Ask Intelligence. These are not ORM rows and not API schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


class QuestionIntent(str, Enum):
    OVERVIEW = "OVERVIEW"
    SCORES = "SCORES"
    SEO = "SEO"
    AI_VISIBILITY = "AI_VISIBILITY"
    ENTITY = "ENTITY"
    RECOMMENDATIONS = "RECOMMENDATIONS"
    WEBSITE = "WEBSITE"
    QUERIES = "QUERIES"
    GENERAL = "GENERAL"


class EvidenceType(str, Enum):
    SEO_FINDING = "seo_finding"
    RECOMMENDATION = "recommendation"
    AI_QUERY = "ai_query"
    AI_RESPONSE = "ai_response"
    WEBSITE_PAGE = "website_page"
    AUDIT_SCORE = "audit_score"
    AI_VISIBILITY_METRIC = "ai_visibility_metric"
    ENTITY_METRIC = "entity_metric"


# Bounded slices sent to the provider. Aggregates may still count every row.
MAX_SEO_FINDINGS = 20
MAX_RECOMMENDATIONS = 20
MAX_AI_QUERIES = 30
MAX_AI_RESPONSE_EXCERPTS = 20
MAX_WEBSITE_PAGES = 20
MAX_EXCERPT_CHARS = 240
MAX_DESCRIPTION_CHARS = 240
MAX_CONTEXT_CHARS = 14_000
MAX_PROMPT_CHARS = 24_000
MAX_HISTORY_MESSAGES = 10
MAX_HISTORY_CONTENT_CHARS = 4_000
MAX_QUESTION_CHARS = 2_000
MAX_EVIDENCE = 8


@dataclass(frozen=True)
class HistoryTurn:
    role: str
    content: str


@dataclass(frozen=True)
class BrandFacts:
    name: str
    website: str | None
    industry: str | None
    country: str | None
    target_market: str | None
    description: str | None


@dataclass(frozen=True)
class ScoreFact:
    name: str
    score: Decimal | None
    status: str
    note: str | None = None


@dataclass(frozen=True)
class AuditFacts:
    id: UUID
    status: str
    created_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    audit_date: datetime | None


@dataclass(frozen=True)
class PageFact:
    id: UUID
    url: str
    status_code: int | None
    title: str | None
    load_time_ms: int | None
    has_schema: bool | None
    word_count: int | None


@dataclass(frozen=True)
class WebsiteFacts:
    page_count: int
    analyzable_page_count: int
    status_distribution: tuple[tuple[str, int], ...]
    average_load_time_ms: int | None
    structured_data_coverage: Decimal | None
    pages_with_schema: int
    pages: tuple[PageFact, ...]


@dataclass(frozen=True)
class FindingFact:
    id: UUID
    title: str
    category: str
    severity: str
    page_id: UUID | None
    page_url: str | None
    description: str | None


@dataclass(frozen=True)
class CommonFinding:
    title: str
    category: str
    severity: str
    count: int
    representative_id: UUID


@dataclass(frozen=True)
class SeoFacts:
    total: int
    by_severity: tuple[tuple[str, int], ...]
    by_category: tuple[tuple[str, int], ...]
    common: tuple[CommonFinding, ...]
    findings: tuple[FindingFact, ...]


@dataclass(frozen=True)
class QueryFact:
    id: UUID
    query_text: str
    category: str
    has_response: bool
    response_id: UUID | None
    brand_mentioned: bool | None
    brand_position: int | None
    citation_found: bool | None
    excerpt: str | None


@dataclass(frozen=True)
class VisibilityFacts:
    status: str
    persisted_score: Decimal | None
    semantic_score: Decimal | None
    total_queries: int
    successful_responses: int
    failed_responses: int
    mention_count: int
    citation_count: int
    mention_rate: Decimal | None
    citation_rate: Decimal | None
    average_position: Decimal | None
    position_score: Decimal | None
    semantic_alignment: Decimal | None
    response_coverage: Decimal | None
    components: tuple[tuple[str, Decimal | None, str], ...]
    note: str | None


@dataclass(frozen=True)
class EntityFacts:
    status: str
    persisted_score: Decimal | None
    presence: Decimal | None
    consistency: Decimal | None
    structured_identity: Decimal | None
    ai_recognition: Decimal | None
    analyzable_pages: int
    pages_with_brand_in_title: int
    pages_with_schema: int
    pages_with_entity_schema: int
    responses_mentioning_brand: int
    note: str | None


@dataclass(frozen=True)
class RecommendationFact:
    id: UUID
    title: str
    category: str
    priority: str
    impact_score: Decimal | None
    effort_score: Decimal | None
    description: str | None


@dataclass(frozen=True)
class ContextBounds:
    seo_findings_total: int
    seo_findings_included: int
    recommendations_total: int
    recommendations_included: int
    queries_total: int
    queries_included: int
    excerpts_included: int
    pages_total: int
    pages_included: int


@dataclass(frozen=True)
class AuditIntelligenceContext:
    brand: BrandFacts
    audit: AuditFacts
    scores: tuple[ScoreFact, ...]
    website: WebsiteFacts
    seo: SeoFacts
    visibility: VisibilityFacts
    entity: EntityFacts
    recommendations: tuple[RecommendationFact, ...]
    queries: tuple[QueryFact, ...]
    insights: tuple[str, ...]
    bounds: ContextBounds
    record_ids: frozenset[UUID] = field(default_factory=frozenset)


@dataclass(frozen=True)
class EvidenceSource:
    type: str
    id: UUID
    label: str


@dataclass(frozen=True)
class OwnedAuditOption:
    id: UUID
    brand_id: UUID
    brand_name: str
    status: str
    created_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True)
class AuditCatalog:
    audits: tuple[OwnedAuditOption, ...]
    selected_audit_id: UUID | None


@dataclass(frozen=True)
class AnswerContext:
    brand_name: str
    audit_date: datetime | None
    overall_score: Decimal | None
    overall_status: str


@dataclass(frozen=True)
class AskOutcome:
    audit_id: UUID | None
    answer: str | None
    context: AnswerContext | None
    sources: tuple[EvidenceSource, ...]
    empty: bool = False
    message: str | None = None
