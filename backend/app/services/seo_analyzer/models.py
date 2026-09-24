"""Internal SEO analyzer inputs and outputs. No database or ORM types."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.models.enums import FindingSeverity


@dataclass(frozen=True)
class PageSnapshot:
    """Factual page data consumed by SEO rules."""

    id: UUID
    url: str
    status_code: int | None
    title: str | None
    meta_description: str | None
    canonical_url: str | None
    word_count: int | None
    h1_count: int | None
    has_schema: bool | None
    load_time_ms: int | None


@dataclass(frozen=True)
class AnalyzerThresholds:
    title_max_length: int = 60
    title_min_length: int = 10
    meta_description_max_length: int = 160
    meta_description_min_length: int = 50
    low_word_count: int = 300
    slow_response_ms: int = 2000


@dataclass(frozen=True)
class FindingResult:
    """Deterministic SEO finding produced by the analyzer."""

    category: str
    severity: FindingSeverity
    title: str
    description: str
    recommendation: str
    page_id: UUID | None = None
