"""Typed snapshot for an Audit Intelligence Report.

Values are copied from persisted rows at generation time. None means the
value is unavailable. A missing score is never stored here as zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

REPORT_TYPE = "Audit Intelligence Report"

REPORT_SECTIONS: tuple[str, ...] = (
    "Cover",
    "Executive Summary",
    "Website Health",
    "SEO Analysis",
    "AI Visibility",
    "Entity Intelligence",
    "Recommendations",
    "AI Query Snapshot",
    "Methodology",
)

MAX_RECOMMENDATIONS = 20
MAX_FINDINGS = 12
MAX_COMMON_ISSUES = 8
MAX_QUERY_EXAMPLES = 8
MAX_QUERY_TEXT = 140
MAX_DESCRIPTION = 400


@dataclass(frozen=True)
class BrandBlock:
    name: str
    website: str | None
    industry: str | None
    country: str | None
    target_market: str | None
    description: str | None


@dataclass(frozen=True)
class AuditBlock:
    id: UUID
    status: str
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class ScoreLine:
    key: str
    label: str
    score: Decimal | None
    status: str
    note: str | None = None


@dataclass(frozen=True)
class IssueCount:
    title: str
    count: int


@dataclass(frozen=True)
class WebsiteBlock:
    pages_crawled: int
    analyzable_pages: int
    successful_http: int
    client_errors: int
    server_errors: int
    average_load_ms: Decimal | None
    structured_data_coverage: Decimal | None
    common_issues: tuple[IssueCount, ...]


@dataclass(frozen=True)
class CategoryCount:
    category: str
    count: int


@dataclass(frozen=True)
class FindingLine:
    title: str
    severity: str
    category: str
    description: str | None
    page_url: str | None


@dataclass(frozen=True)
class SeoBlock:
    total: int
    high: int
    medium: int
    low: int
    info: int
    categories: tuple[CategoryCount, ...]
    findings: tuple[FindingLine, ...]


@dataclass(frozen=True)
class VisibilityBlock:
    score: Decimal | None
    status: str
    mention_rate: Decimal | None
    citation_rate: Decimal | None
    average_position: Decimal | None
    position_score: Decimal | None
    semantic_alignment: Decimal | None
    semantic_score: Decimal | None
    successful_responses: int
    total_queries: int


@dataclass(frozen=True)
class EntityBlock:
    score: Decimal | None
    status: str
    presence: Decimal | None
    consistency: Decimal | None
    structured_identity: Decimal | None
    ai_recognition: Decimal | None


@dataclass(frozen=True)
class RecommendationLine:
    title: str
    description: str | None
    category: str
    priority: str
    impact: Decimal | None
    effort: Decimal | None


@dataclass(frozen=True)
class QueryExample:
    text: str
    category: str
    brand_mentioned: bool
    citation_found: bool


@dataclass(frozen=True)
class QueryBlock:
    total_queries: int
    successful_responses: int
    brand_mentions: int
    citations: int
    categories: tuple[CategoryCount, ...]
    examples: tuple[QueryExample, ...]


@dataclass(frozen=True)
class ReportSnapshot:
    report_type: str
    title: str
    generated_at: datetime
    brand: BrandBlock
    audit: AuditBlock
    scores: tuple[ScoreLine, ...]
    overall: ScoreLine
    website: WebsiteBlock
    seo: SeoBlock
    visibility: VisibilityBlock
    entity: EntityBlock
    recommendations: tuple[RecommendationLine, ...]
    queries: QueryBlock
    methodology: tuple[str, ...]
    sections: tuple[str, ...]
