"""API schemas for the read-only Query Explorer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AiQueryCategory, AuditStatus
from app.services.query_explorer.models import ExplorerResult


class QueryExplorerAudit(BaseModel):
    id: UUID
    brand_id: UUID
    brand_name: str
    created_at: datetime
    completed_at: datetime | None = None
    status: AuditStatus


class QueryExplorerSummary(BaseModel):
    total_queries: int
    responses: int
    failed: int
    mention_rate: float | None = Field(
        description="Mentioned responses divided by successful responses. Null when no responses exist.",
    )
    citation_rate: float | None = Field(
        description="Citation responses divided by successful responses. Null when no responses exist.",
    )


class QueryExplorerResponseBody(BaseModel):
    text: str
    provider: str
    model: str
    brand_mentioned: bool | None
    brand_position: int | None
    citation_found: bool | None
    semantic_alignment: float | None
    latency_ms: int | None


class QueryExplorerItem(BaseModel):
    query_id: UUID
    query_text: str
    category: AiQueryCategory
    created_at: datetime
    has_response: bool
    response: QueryExplorerResponseBody | None


class QueryExplorerPagination(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class QueryExplorerView(BaseModel):
    audit: QueryExplorerAudit | None
    audits: list[QueryExplorerAudit]
    summary: QueryExplorerSummary | None
    items: list[QueryExplorerItem]
    pagination: QueryExplorerPagination


def serialize_query_explorer(result: ExplorerResult) -> QueryExplorerView:
    audit = _serialize_audit(result.audit) if result.audit is not None else None
    summary = None
    if result.summary is not None:
        summary = QueryExplorerSummary(
            total_queries=result.summary.total_queries,
            responses=result.summary.responses,
            failed=result.summary.failed,
            mention_rate=_float_or_none(result.summary.mention_rate),
            citation_rate=_float_or_none(result.summary.citation_rate),
        )
    return QueryExplorerView(
        audit=audit,
        audits=[_serialize_audit(item) for item in result.audits],
        summary=summary,
        items=[
            QueryExplorerItem(
                query_id=item.query_id,
                query_text=item.query_text,
                category=item.category,
                created_at=item.created_at,
                has_response=item.has_response,
                response=(
                    QueryExplorerResponseBody(
                        text=item.response.text,
                        provider=item.response.provider,
                        model=item.response.model,
                        brand_mentioned=item.response.brand_mentioned,
                        brand_position=item.response.brand_position,
                        citation_found=item.response.citation_found,
                        semantic_alignment=_float_or_none(item.response.semantic_alignment),
                        latency_ms=item.response.latency_ms,
                    )
                    if item.response is not None
                    else None
                ),
            )
            for item in result.items
        ],
        pagination=QueryExplorerPagination(
            page=result.pagination.page,
            page_size=result.pagination.page_size,
            total=result.pagination.total,
            pages=result.pagination.pages,
        ),
    )


def _serialize_audit(audit) -> QueryExplorerAudit:
    return QueryExplorerAudit(
        id=audit.id,
        brand_id=audit.brand_id,
        brand_name=audit.brand_name,
        created_at=audit.created_at,
        completed_at=audit.completed_at,
        status=audit.status,
    )


def _float_or_none(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)
