"""API schemas for the Recommendations Engine."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import RecommendationPriority
from app.models.recommendation import Recommendation


class RecommendationRunResponse(BaseModel):
    audit_id: UUID
    recommendations_generated: int
    high: int
    medium: int
    low: int
    status: str


class RecommendationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    category: str
    priority: RecommendationPriority
    impact_score: Decimal | None
    effort_score: Decimal | None


class RecommendationListResponse(BaseModel):
    items: list[RecommendationItem]
    total: int


def serialize_recommendation(row: Recommendation) -> RecommendationItem:
    return RecommendationItem(
        id=row.id,
        title=row.title,
        description=row.description,
        category=row.category,
        priority=row.priority,
        impact_score=row.impact_score,
        effort_score=row.effort_score,
    )
