"""API schemas for audit intelligence reports."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_id: UUID


class ScoreView(BaseModel):
    key: str
    label: str
    score: float | None
    status: str


class ReportListItem(BaseModel):
    id: UUID
    audit_id: UUID
    brand_name: str
    title: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    audit_date: datetime | None


class CompletedAuditOption(BaseModel):
    id: UUID
    brand_name: str
    created_at: datetime
    completed_at: datetime | None


class ReportListResponse(BaseModel):
    items: list[ReportListItem]
    total: int
    page: int
    page_size: int
    completed_audits: list[CompletedAuditOption]


class ReportDetail(BaseModel):
    id: UUID
    audit_id: UUID
    brand_name: str
    website: str | None
    title: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    audit_date: datetime | None
    generated_at: datetime | None = None
    overall_score: float | None = None
    overall_status: str = "UNAVAILABLE"
    overall_note: str | None = None
    scores: list[ScoreView] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    message: str | None = None


def serialize_list_item(report, brand_name: str, audit_date: datetime | None) -> ReportListItem:
    return ReportListItem(
        id=report.id,
        audit_id=report.audit_id,
        brand_name=brand_name,
        title=report.title,
        status=_status(report.status),
        created_at=report.created_at,
        completed_at=report.completed_at,
        audit_date=audit_date,
    )


def serialize_completed_audit(audit, brand_name: str) -> CompletedAuditOption:
    return CompletedAuditOption(
        id=audit.id,
        brand_name=brand_name,
        created_at=audit.created_at,
        completed_at=audit.completed_at,
    )


def serialize_detail(report, brand, audit, summary: dict | None, message: str | None = None) -> ReportDetail:
    summary = summary or {}
    scores = []
    for item in summary.get("scores") or []:
        if not isinstance(item, dict):
            continue
        scores.append(
            ScoreView(
                key=str(item.get("key") or ""),
                label=str(item.get("label") or ""),
                score=item.get("score"),
                status=str(item.get("status") or "UNAVAILABLE"),
            )
        )
    sections = [str(section) for section in summary.get("sections") or []]
    audit_date = audit.completed_at or audit.created_at
    generated_at = _parse_datetime(summary.get("generated_at")) if summary else None
    return ReportDetail(
        id=report.id,
        audit_id=report.audit_id,
        brand_name=summary.get("brand_name") or brand.name,
        website=summary.get("website", brand.website_url),
        title=report.title,
        status=_status(report.status),
        created_at=report.created_at,
        completed_at=report.completed_at,
        audit_date=audit_date,
        generated_at=generated_at or report.completed_at,
        overall_score=summary.get("overall_score"),
        overall_status=str(summary.get("overall_status") or "UNAVAILABLE"),
        overall_note=summary.get("overall_note"),
        scores=scores,
        sections=sections,
        message=message,
    )


def _status(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
