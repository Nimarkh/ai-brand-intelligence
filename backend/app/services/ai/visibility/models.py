"""Internal AI Visibility models (not ORM)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import UUID


class VisibilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    PROVISIONAL = "PROVISIONAL"


@dataclass(frozen=True)
class ResponseInput:
    """One successful AI response paired with its query (no ORM)."""

    query_id: UUID
    response_id: UUID
    query_text: str
    response_text: str
    brand_mentioned: bool
    brand_position: int | None
    citation_found: bool
    semantic_alignment: Decimal | None = None


@dataclass(frozen=True)
class ComponentScore:
    name: str
    score: Decimal | None
    status: VisibilityStatus
    weight: Decimal
    effective_weight: Decimal | None
    sample_size: int = 0


@dataclass(frozen=True)
class VisibilityMetrics:
    mention_rate: Decimal | None
    citation_rate: Decimal | None
    average_position: Decimal | None
    position_score: Decimal | None
    semantic_alignment: Decimal | None
    semantic_score: Decimal | None


@dataclass(frozen=True)
class AIVisibilityScore:
    overall_score: Decimal | None
    status: VisibilityStatus
    metrics: VisibilityMetrics
    components: tuple[ComponentScore, ...]
    total_queries: int
    successful_responses: int
    failed_responses: int
    response_coverage: Decimal | None
    # Per-response semantic values to persist onto ai_responses.semantic_alignment
    semantic_by_response_id: tuple[tuple[UUID, Decimal | None], ...] = ()
