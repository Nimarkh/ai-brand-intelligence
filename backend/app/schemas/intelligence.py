"""API schemas for Ask Intelligence."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.intelligence.models import AskOutcome, AuditCatalog


class HistoryMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content must not be blank")
        return cleaned


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_id: UUID | None = None
    question: str = Field(min_length=1, max_length=2000)
    history: list[HistoryMessageIn] = Field(default_factory=list, max_length=10)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question must not be blank")
        return cleaned


class EvidenceSourceOut(BaseModel):
    type: str
    id: UUID
    label: str


class AskContextOut(BaseModel):
    brand_name: str
    audit_date: datetime | None = None
    overall_score: float | None = None
    overall_status: str


class AskResponse(BaseModel):
    audit_id: UUID | None = None
    answer: str | None = None
    context: AskContextOut | None = None
    sources: list[EvidenceSourceOut] = Field(default_factory=list)
    empty: bool = False
    message: str | None = None


class IntelligenceAuditOut(BaseModel):
    id: UUID
    brand_id: UUID
    brand_name: str
    status: str
    created_at: datetime | None = None
    completed_at: datetime | None = None


class IntelligenceAuditList(BaseModel):
    audits: list[IntelligenceAuditOut]
    selected_audit_id: UUID | None = None


def serialize_ask(result: AskOutcome) -> AskResponse:
    context = None
    if result.context is not None:
        score = result.context.overall_score
        context = AskContextOut(
            brand_name=result.context.brand_name,
            audit_date=result.context.audit_date,
            overall_score=float(score) if score is not None else None,
            overall_status=result.context.overall_status,
        )
    return AskResponse(
        audit_id=result.audit_id,
        answer=result.answer,
        context=context,
        sources=[
            EvidenceSourceOut(type=item.type, id=item.id, label=item.label) for item in result.sources
        ],
        empty=result.empty,
        message=result.message,
    )


def serialize_catalog(catalog: AuditCatalog) -> IntelligenceAuditList:
    return IntelligenceAuditList(
        audits=[
            IntelligenceAuditOut(
                id=item.id,
                brand_id=item.brand_id,
                brand_name=item.brand_name,
                status=item.status,
                created_at=item.created_at,
                completed_at=item.completed_at,
            )
            for item in catalog.audits
        ],
        selected_audit_id=catalog.selected_audit_id,
    )
