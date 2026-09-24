from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.services.audit_engine.models import AuditScoreResult, ScoreStatus


class ScoreValue(BaseModel):
    score: Decimal | None = None
    status: ScoreStatus


class ComponentScoreResponse(BaseModel):
    name: str
    score: Decimal | None = None
    status: ScoreStatus
    findings_count: int = 0
    affected_pages: int = 0
    top_penalty_categories: list[str] = Field(default_factory=list)


class AuditScoreResponse(BaseModel):
    audit_id: UUID
    status: ScoreStatus
    website_health: ScoreValue
    seo: ScoreValue
    overall: ScoreValue
    components: list[ComponentScoreResponse]
    findings_count: int
    affected_pages: int
    analyzable_pages: int
    ai_visibility: ScoreValue
    entity_strength: ScoreValue
    note: str | None = None


def serialize_score(audit_id: UUID, result: AuditScoreResult) -> AuditScoreResponse:
    components = [
        _component(result.technical),
        _component(result.seo),
        _component(result.content),
        _component(result.structured_data),
    ]
    note = None
    if result.status == ScoreStatus.PROVISIONAL:
        note = (
            "Overall score is provisional. It uses Website Health and SEO only. "
            "AI Visibility and Entity Strength are not available yet."
        )
    elif result.status == ScoreStatus.UNAVAILABLE:
        if result.analyzable_pages < 1:
            note = "No analyzable pages. Scores are unavailable (not zero)."
        else:
            note = "Score has not been calculated yet."

    return AuditScoreResponse(
        audit_id=audit_id,
        status=result.status,
        website_health=ScoreValue(
            score=result.website_health.score,
            status=result.website_health.status,
        ),
        seo=ScoreValue(score=result.seo_score.score, status=result.seo_score.status),
        overall=ScoreValue(score=result.overall.score, status=result.overall.status),
        components=components,
        findings_count=result.findings_count,
        affected_pages=result.affected_pages,
        analyzable_pages=result.analyzable_pages,
        ai_visibility=ScoreValue(score=None, status=ScoreStatus.UNAVAILABLE),
        entity_strength=ScoreValue(score=None, status=ScoreStatus.UNAVAILABLE),
        note=note,
    )


def _component(component) -> ComponentScoreResponse:
    top = []
    for penalty in component.top_penalty_rules:
        if penalty.category not in top:
            top.append(penalty.category)
    return ComponentScoreResponse(
        name=component.name,
        score=component.score,
        status=component.status,
        findings_count=component.findings_count,
        affected_pages=component.affected_pages,
        top_penalty_categories=top[:5],
    )
