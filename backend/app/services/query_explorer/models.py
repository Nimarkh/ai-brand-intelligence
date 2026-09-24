"""Read-only Query Explorer view models.

These values are assembled from persisted rows. They are not scores and they
are not stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.models.enums import AiQueryCategory, AuditStatus


@dataclass(frozen=True)
class ExplorerAudit:
    id: UUID
    brand_id: UUID
    brand_name: str
    created_at: datetime
    completed_at: datetime | None
    status: AuditStatus


@dataclass(frozen=True)
class ExplorerResponse:
    text: str
    provider: str
    model: str
    brand_mentioned: bool | None
    brand_position: int | None
    citation_found: bool | None
    semantic_alignment: Decimal | None
    latency_ms: int | None


@dataclass(frozen=True)
class ExplorerItem:
    query_id: UUID
    query_text: str
    category: AiQueryCategory
    created_at: datetime
    has_response: bool
    response: ExplorerResponse | None


@dataclass(frozen=True)
class ExplorerSummary:
    total_queries: int
    responses: int
    failed: int
    mention_rate: Decimal | None
    citation_rate: Decimal | None


@dataclass(frozen=True)
class ExplorerPagination:
    page: int
    page_size: int
    total: int
    pages: int


@dataclass(frozen=True)
class ExplorerResult:
    audit: ExplorerAudit | None
    audits: tuple[ExplorerAudit, ...]
    summary: ExplorerSummary | None
    items: tuple[ExplorerItem, ...]
    pagination: ExplorerPagination
