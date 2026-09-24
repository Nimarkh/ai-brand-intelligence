"""Internal models for the AI Query Engine (not ORM)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.models.enums import AiQueryCategory


@dataclass(frozen=True)
class GeneratedQuery:
    """One deterministic query ready for persistence."""

    query_text: str
    category: AiQueryCategory


@dataclass(frozen=True)
class BrandContext:
    """Brand fields used for template substitution."""

    name: str
    industry: str
    country: str | None = None
    target_market: str | None = None
    description: str | None = None
    website_url: str | None = None


@dataclass(frozen=True)
class ResponseExtractions:
    """Basic deterministic extraction for ai_responses columns."""

    brand_mentioned: bool
    brand_position: int | None
    citation_found: bool


@dataclass(frozen=True)
class QueryRunSummary:
    audit_id: UUID
    queries_generated: int
    responses_succeeded: int
    responses_failed: int
    status: str = "COMPLETED"
