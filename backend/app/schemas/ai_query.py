"""API schemas for the AI Query Engine."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai import AiQuery, AiResponse
from app.models.enums import AiQueryCategory


class AiQueryRunResponse(BaseModel):
    audit_id: UUID
    queries_generated: int
    responses_succeeded: int
    responses_failed: int
    status: str


class AiQueryListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    query_text: str
    category: AiQueryCategory
    created_at: datetime
    has_response: bool


class AiQueryListResponse(BaseModel):
    items: list[AiQueryListItem]
    total: int


class AiQueryResponseDetail(BaseModel):
    id: UUID
    provider: str
    model: str
    response_text: str
    brand_mentioned: bool | None
    brand_position: int | None
    citation_found: bool | None
    semantic_alignment: Decimal | None = Field(
        default=None,
        description="Lexical semantic alignment from Phase 12 AI Visibility Engine.",
    )
    latency_ms: int | None
    created_at: datetime


class AiQueryDetailResponse(BaseModel):
    id: UUID
    audit_id: UUID
    query_text: str
    category: AiQueryCategory
    created_at: datetime
    response: AiQueryResponseDetail | None


def serialize_query_list_item(query: AiQuery) -> AiQueryListItem:
    return AiQueryListItem(
        id=query.id,
        query_text=query.query_text,
        category=query.category,
        created_at=query.created_at,
        has_response=bool(query.responses),
    )


def serialize_query_detail(query: AiQuery) -> AiQueryDetailResponse:
    response_row = query.responses[0] if query.responses else None
    detail: AiQueryResponseDetail | None = None
    if response_row is not None:
        detail = _serialize_response(response_row)
    return AiQueryDetailResponse(
        id=query.id,
        audit_id=query.audit_id,
        query_text=query.query_text,
        category=query.category,
        created_at=query.created_at,
        response=detail,
    )


def _serialize_response(row: AiResponse) -> AiQueryResponseDetail:
    return AiQueryResponseDetail(
        id=row.id,
        provider=row.provider,
        model=row.model,
        response_text=row.response_text,
        brand_mentioned=row.brand_mentioned,
        brand_position=row.brand_position,
        citation_found=row.citation_found,
        semantic_alignment=row.semantic_alignment,
        latency_ms=row.latency_ms,
        created_at=row.created_at,
    )
