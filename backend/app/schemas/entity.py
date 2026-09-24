"""API schemas for Entity Intelligence."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.services.entity.models import EntityStatus, EntityStrengthScore


class EntityEvidenceResponse(BaseModel):
    analyzable_pages: int
    pages_with_brand_in_title: int
    pages_with_brand_in_meta: int
    pages_with_canonical: int
    pages_with_same_origin_canonical: int
    pages_with_schema: int
    pages_with_entity_schema: int
    successful_ai_responses: int
    responses_mentioning_brand: int
    average_mention_position: Decimal | None = None
    brand_name: str
    normalized_brand_name: str
    origin: str | None = None


class EntityMetricsResponse(BaseModel):
    title_presence_rate: Decimal | None = None
    meta_presence_rate: Decimal | None = None
    title_consistency: Decimal | None = None
    canonical_consistency: Decimal | None = None
    schema_consistency: Decimal | None = None
    entity_schema_coverage: Decimal | None = None
    schema_quality: Decimal | None = None
    ai_mention_rate: Decimal | None = None
    ai_position_score: Decimal | None = None


class EntityComponentResponse(BaseModel):
    name: str
    score: Decimal | None = None
    status: EntityStatus
    weight: Decimal
    effective_weight: Decimal | None = None
    sample_size: int = 0


class EntityComponentsSummary(BaseModel):
    presence: Decimal | None = None
    consistency: Decimal | None = None
    structured_identity: Decimal | None = None
    ai_recognition: Decimal | None = None


class EntityStrengthResponse(BaseModel):
    audit_id: UUID
    status: EntityStatus
    overall_score: Decimal | None = None
    metrics: EntityMetricsResponse
    components: EntityComponentsSummary
    component_details: list[EntityComponentResponse] = Field(default_factory=list)
    evidence: EntityEvidenceResponse
    notes: list[str] = Field(default_factory=list)


def serialize_entity(audit_id: UUID, result: EntityStrengthScore) -> EntityStrengthResponse:
    by_name = {item.name: item.score for item in result.components}
    evidence = result.evidence
    return EntityStrengthResponse(
        audit_id=audit_id,
        status=result.status,
        overall_score=result.overall_score,
        metrics=EntityMetricsResponse(
            title_presence_rate=result.metrics.title_presence_rate,
            meta_presence_rate=result.metrics.meta_presence_rate,
            title_consistency=result.metrics.title_consistency,
            canonical_consistency=result.metrics.canonical_consistency,
            schema_consistency=result.metrics.schema_consistency,
            entity_schema_coverage=result.metrics.entity_schema_coverage,
            schema_quality=result.metrics.schema_quality,
            ai_mention_rate=result.metrics.ai_mention_rate,
            ai_position_score=result.metrics.ai_position_score,
        ),
        components=EntityComponentsSummary(
            presence=by_name.get("presence"),
            consistency=by_name.get("consistency"),
            structured_identity=by_name.get("structured_identity"),
            ai_recognition=by_name.get("ai_recognition"),
        ),
        component_details=[
            EntityComponentResponse(
                name=item.name,
                score=item.score,
                status=item.status,
                weight=item.weight,
                effective_weight=item.effective_weight,
                sample_size=item.sample_size,
            )
            for item in result.components
        ],
        evidence=EntityEvidenceResponse(
            analyzable_pages=evidence.analyzable_pages,
            pages_with_brand_in_title=evidence.pages_with_brand_in_title,
            pages_with_brand_in_meta=evidence.pages_with_brand_in_meta,
            pages_with_canonical=evidence.pages_with_canonical,
            pages_with_same_origin_canonical=evidence.pages_with_same_origin_canonical,
            pages_with_schema=evidence.pages_with_schema,
            pages_with_entity_schema=evidence.pages_with_entity_schema,
            successful_ai_responses=evidence.successful_ai_responses,
            responses_mentioning_brand=evidence.responses_mentioning_brand,
            average_mention_position=evidence.average_mention_position,
            brand_name=evidence.brand_name,
            normalized_brand_name=evidence.normalized_brand_name,
            origin=evidence.origin,
        ),
        notes=list(result.notes),
    )
