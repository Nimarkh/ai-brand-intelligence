"""Internal Entity Intelligence models (not ORM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from uuid import UUID


class EntityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    PROVISIONAL = "PROVISIONAL"


@dataclass(frozen=True)
class PageInput:
    """Persisted WebsitePage fields used for entity scoring."""

    id: UUID
    url: str
    title: str | None
    meta_description: str | None
    canonical_url: str | None
    has_schema: bool | None
    schema_types: tuple[str, ...]


@dataclass(frozen=True)
class AiResponseInput:
    """Persisted AI response fields used for AI entity recognition."""

    response_id: UUID
    brand_mentioned: bool
    brand_position: int | None


@dataclass(frozen=True)
class ComponentScore:
    name: str
    score: Decimal | None
    status: EntityStatus
    weight: Decimal
    effective_weight: Decimal | None
    sample_size: int = 0


@dataclass(frozen=True)
class EntityEvidence:
    """Deterministic evidence counts for explainability."""

    analyzable_pages: int
    pages_with_brand_in_title: int
    pages_with_brand_in_meta: int
    pages_with_canonical: int
    pages_with_same_origin_canonical: int
    pages_with_schema: int
    pages_with_entity_schema: int
    successful_ai_responses: int
    responses_mentioning_brand: int
    average_mention_position: Decimal | None
    brand_name: str
    normalized_brand_name: str
    origin: str | None = None


@dataclass(frozen=True)
class EntityMetrics:
    title_presence_rate: Decimal | None
    meta_presence_rate: Decimal | None
    title_consistency: Decimal | None
    canonical_consistency: Decimal | None
    schema_consistency: Decimal | None
    entity_schema_coverage: Decimal | None
    schema_quality: Decimal | None
    ai_mention_rate: Decimal | None
    ai_position_score: Decimal | None


@dataclass(frozen=True)
class EntityStrengthScore:
    overall_score: Decimal | None
    status: EntityStatus
    metrics: EntityMetrics
    components: tuple[ComponentScore, ...]
    evidence: EntityEvidence
    notes: tuple[str, ...] = field(default_factory=tuple)
