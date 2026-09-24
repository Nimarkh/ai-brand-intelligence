"""API schemas for the AI Visibility Engine."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.services.ai.visibility.models import AIVisibilityScore, VisibilityStatus


class VisibilityMetricsResponse(BaseModel):
    mention_rate: Decimal | None = None
    citation_rate: Decimal | None = None
    average_position: Decimal | None = None
    position_score: Decimal | None = None
    semantic_alignment: Decimal | None = None
    semantic_score: Decimal | None = None


class VisibilityComponentsResponse(BaseModel):
    mention: Decimal | None = None
    citation: Decimal | None = None
    position: Decimal | None = None
    semantic: Decimal | None = None


class VisibilityComponentDetail(BaseModel):
    name: str
    score: Decimal | None = None
    status: VisibilityStatus
    weight: Decimal
    effective_weight: Decimal | None = None
    sample_size: int = 0


class AIVisibilityResponse(BaseModel):
    audit_id: UUID
    status: VisibilityStatus
    overall_score: Decimal | None = None
    metrics: VisibilityMetricsResponse
    components: VisibilityComponentsResponse
    component_details: list[VisibilityComponentDetail] = Field(default_factory=list)
    total_queries: int
    successful_responses: int
    failed_responses: int
    response_coverage: Decimal | None = None
    note: str | None = None


def serialize_visibility(audit_id: UUID, result: AIVisibilityScore) -> AIVisibilityResponse:
    by_name = {item.name: item.score for item in result.components}
    note = None
    if result.status == VisibilityStatus.UNAVAILABLE:
        if result.successful_responses < 1:
            note = (
                "AI Visibility is unavailable. Run AI Query Analysis and ensure "
                "at least one successful response exists. Unavailable is not zero."
            )
        else:
            note = "AI Visibility has not been calculated yet for this audit."
    elif result.status == VisibilityStatus.PROVISIONAL:
        note = (
            "AI Visibility is provisional because some AI queries have no response. "
            "Scores use successful responses only."
        )

    return AIVisibilityResponse(
        audit_id=audit_id,
        status=result.status,
        overall_score=result.overall_score,
        metrics=VisibilityMetricsResponse(
            mention_rate=result.metrics.mention_rate,
            citation_rate=result.metrics.citation_rate,
            average_position=result.metrics.average_position,
            position_score=result.metrics.position_score,
            semantic_alignment=result.metrics.semantic_alignment,
            semantic_score=result.metrics.semantic_score,
        ),
        components=VisibilityComponentsResponse(
            mention=by_name.get("mention"),
            citation=by_name.get("citation"),
            position=by_name.get("position"),
            semantic=by_name.get("semantic"),
        ),
        component_details=[
            VisibilityComponentDetail(
                name=item.name,
                score=item.score,
                status=item.status,
                weight=item.weight,
                effective_weight=item.effective_weight,
                sample_size=item.sample_size,
            )
            for item in result.components
        ],
        total_queries=result.total_queries,
        successful_responses=result.successful_responses,
        failed_responses=result.failed_responses,
        response_coverage=result.response_coverage,
        note=note,
    )
