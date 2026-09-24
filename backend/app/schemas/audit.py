from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.audit import Audit
from app.models.enums import AuditStatus


class AuditResponse(BaseModel):
    """Audit snapshot. Null scores mean no score has been calculated."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brand_id: UUID
    status: AuditStatus
    pages_crawled: int = Field(description="Website pages stored for this audit.")
    overall_score: Decimal | None
    website_score: Decimal | None
    seo_score: Decimal | None
    ai_visibility_score: Decimal | None
    entity_score: Decimal | None
    semantic_score: Decimal | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class AuditListResponse(BaseModel):
    items: list[AuditResponse]


class CrawlResponse(BaseModel):
    audit_id: UUID
    status: AuditStatus
    pages_crawled: int


def serialize_audit(audit: Audit, pages_crawled: int) -> AuditResponse:
    return AuditResponse(
        id=audit.id,
        brand_id=audit.brand_id,
        status=audit.status,
        pages_crawled=pages_crawled,
        overall_score=audit.overall_score,
        website_score=audit.website_score,
        seo_score=audit.seo_score,
        ai_visibility_score=audit.ai_visibility_score,
        entity_score=audit.entity_score,
        semantic_score=audit.semantic_score,
        started_at=audit.started_at,
        completed_at=audit.completed_at,
        created_at=audit.created_at,
    )
