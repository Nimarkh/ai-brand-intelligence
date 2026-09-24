from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FindingSeverity
from app.models.website import SeoFinding


class SeoAnalyzeResponse(BaseModel):
    audit_id: UUID
    findings_count: int
    status: str = Field(description="Analysis run status. Independent of AuditStatus crawl lifecycle.")


class SeoFindingPageInfo(BaseModel):
    """Affected page summary for a finding. Omits raw HTML and owner details."""

    id: UUID
    url: str
    status_code: int | None = None


class SeoFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    audit_id: UUID
    page_id: UUID | None
    category: str
    severity: FindingSeverity
    title: str
    description: str | None
    recommendation: str | None
    created_at: datetime
    page: SeoFindingPageInfo | None = None


class SeoFindingListResponse(BaseModel):
    items: list[SeoFindingResponse]
    total: int


def serialize_seo_finding(finding: SeoFinding) -> SeoFindingResponse:
    page_info: SeoFindingPageInfo | None = None
    if finding.page is not None:
        page_info = SeoFindingPageInfo(
            id=finding.page.id,
            url=finding.page.url,
            status_code=finding.page.status_code,
        )
    return SeoFindingResponse(
        id=finding.id,
        audit_id=finding.audit_id,
        page_id=finding.page_id,
        category=finding.category,
        severity=finding.severity,
        title=finding.title,
        description=finding.description,
        recommendation=finding.recommendation,
        created_at=finding.created_at,
        page=page_info,
    )
