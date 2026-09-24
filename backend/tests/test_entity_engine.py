"""Pure unit tests for Entity Intelligence."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.entity import (
    AI_RECOGNITION_WEIGHT,
    CONSISTENCY_WEIGHT,
    ENTITY_WEIGHTS,
    EntityIntelligenceEngine,
    EntityStatus,
    PRESENCE_WEIGHT,
    STRUCTURED_WEIGHT,
    normalize_brand_name,
)
from app.services.entity.models import AiResponseInput, PageInput
from app.services.entity.scoring import score_overall


def _page(
    *,
    url: str = "https://acme.example/",
    title: str | None = "Acme Analytics — Home",
    meta: str | None = "Acme Analytics marketing tools",
    canonical: str | None = "https://acme.example/",
    has_schema: bool | None = True,
    schema_types: tuple[str, ...] = ("Organization",),
) -> PageInput:
    return PageInput(
        id=uuid4(),
        url=url,
        title=title,
        meta_description=meta,
        canonical_url=canonical,
        has_schema=has_schema,
        schema_types=schema_types,
    )


def _resp(*, mentioned: bool = True, position: int | None = 1) -> AiResponseInput:
    return AiResponseInput(
        response_id=uuid4(),
        brand_mentioned=mentioned,
        brand_position=position,
    )


def test_weights_sum_to_one() -> None:
    assert sum(ENTITY_WEIGHTS.values()) == Decimal("1.00")
    assert PRESENCE_WEIGHT == Decimal("0.30")
    assert CONSISTENCY_WEIGHT == Decimal("0.25")
    assert STRUCTURED_WEIGHT == Decimal("0.25")
    assert AI_RECOGNITION_WEIGHT == Decimal("0.20")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Acme Analytics", "acme analytics"),
        ("ACME ANALYTICS", "acme analytics"),
        ("  Acme   Analytics  ", "acme analytics"),
        ("Acme Analytics, Inc.", "acme analytics"),
        ("Acme Analytics Ltd", "acme analytics"),
        ("Acme Analytics LLC", "acme analytics"),
        ("Café Brand", "café brand"),
        ("Brand & Co.", "brand"),  # trailing legal suffix "co" removed
    ],
)
def test_normalize_brand_name(raw: str, expected: str) -> None:
    assert normalize_brand_name(raw) == expected


def test_normalize_preserves_meaningful_words() -> None:
    assert "analytics" in normalize_brand_name("North Analytics Platform")
    assert normalize_brand_name("Inc Brand Name") == "inc brand name"  # leading Inc kept


def test_presence_full_and_partial() -> None:
    pages = [
        _page(title="Acme Analytics Home"),
        _page(title="Acme Analytics Pricing"),
    ]
    result = EntityIntelligenceEngine().score(
        brand_name="Acme Analytics",
        pages=pages,
        responses=[],
        website_url="https://acme.example",
    )
    presence = next(c for c in result.components if c.name == "presence")
    assert presence.status == EntityStatus.AVAILABLE
    assert presence.score == Decimal("100.0")

    mixed = [
        _page(title="Acme Analytics Home"),
        _page(title="Pricing page", meta="No brand here"),
    ]
    result2 = EntityIntelligenceEngine().score(
        brand_name="Acme Analytics",
        pages=mixed,
        responses=[],
        website_url="https://acme.example",
    )
    presence2 = next(c for c in result2.components if c.name == "presence")
    assert presence2.score is not None
    assert Decimal("0") < presence2.score < Decimal("100")


def test_presence_unavailable_without_pages() -> None:
    result = EntityIntelligenceEngine().score(
        brand_name="Acme Analytics",
        pages=[],
        responses=[_resp()],
        website_url="https://acme.example",
    )
    presence = next(c for c in result.components if c.name == "presence")
    assert presence.status == EntityStatus.UNAVAILABLE
    assert presence.score is None
    assert result.status == EntityStatus.PROVISIONAL


def test_consistency_canonical_and_title() -> None:
    pages = [
        _page(canonical="https://acme.example/a"),
        _page(canonical="https://other.example/x", title="Other"),
    ]
    result = EntityIntelligenceEngine().score(
        brand_name="Acme Analytics",
        pages=pages,
        responses=[],
        website_url="https://acme.example",
    )
    consistency = next(c for c in result.components if c.name == "consistency")
    assert consistency.status == EntityStatus.AVAILABLE
    assert result.metrics.canonical_consistency == Decimal("0.5000")


def test_structured_identity_schema_variants() -> None:
    none = EntityIntelligenceEngine().score(
        brand_name="Acme",
        pages=[_page(has_schema=False, schema_types=())],
        responses=[],
        website_url="https://acme.example",
    )
    structured = next(c for c in none.components if c.name == "structured_identity")
    assert structured.score == Decimal("0.0")

    website_only = EntityIntelligenceEngine().score(
        brand_name="Acme",
        pages=[_page(schema_types=("WebSite",))],
        responses=[],
        website_url="https://acme.example",
    )
    website_score = next(
        c.score for c in website_only.components if c.name == "structured_identity"
    )
    org = EntityIntelligenceEngine().score(
        brand_name="Acme",
        pages=[_page(schema_types=("Organization",))],
        responses=[],
        website_url="https://acme.example",
    )
    org_score = next(c.score for c in org.components if c.name == "structured_identity")
    assert org_score is not None and website_score is not None
    assert org_score > website_score


@pytest.mark.parametrize("schema_type", ["Organization", "Corporation", "LocalBusiness", "Brand"])
def test_structured_strong_types(schema_type: str) -> None:
    result = EntityIntelligenceEngine().score(
        brand_name="Acme",
        pages=[_page(schema_types=(schema_type,))],
        responses=[],
        website_url="https://acme.example",
    )
    structured = next(c for c in result.components if c.name == "structured_identity")
    assert structured.status == EntityStatus.AVAILABLE
    assert structured.score is not None
    assert structured.score >= Decimal("90.0")


def test_ai_recognition_rates() -> None:
    empty = EntityIntelligenceEngine().score(
        brand_name="Acme",
        pages=[_page()],
        responses=[],
        website_url="https://acme.example",
    )
    assert next(c for c in empty.components if c.name == "ai_recognition").status == (
        EntityStatus.UNAVAILABLE
    )

    full = EntityIntelligenceEngine().score(
        brand_name="Acme",
        pages=[_page()],
        responses=[_resp(mentioned=True, position=1) for _ in range(4)],
        website_url="https://acme.example",
    )
    ai = next(c for c in full.components if c.name == "ai_recognition")
    assert ai.score == Decimal("100.0")

    zero = EntityIntelligenceEngine().score(
        brand_name="Acme",
        pages=[_page()],
        responses=[_resp(mentioned=False, position=None) for _ in range(4)],
        website_url="https://acme.example",
    )
    ai0 = next(c for c in zero.components if c.name == "ai_recognition")
    assert ai0.score == Decimal("0.0")


def test_final_score_all_components_and_renormalization() -> None:
    result = EntityIntelligenceEngine().score(
        brand_name="Acme Analytics",
        pages=[_page(), _page(url="https://acme.example/about", title="About Acme Analytics")],
        responses=[_resp(), _resp(position=2)],
        website_url="https://acme.example",
    )
    assert result.status == EntityStatus.AVAILABLE
    assert result.overall_score is not None
    assert Decimal("0") <= result.overall_score <= Decimal("100")
    assert result.overall_score == result.overall_score.quantize(Decimal("0.1"))
    effective_sum = sum(
        (c.effective_weight or Decimal("0"))
        for c in result.components
        if c.status == EntityStatus.AVAILABLE
    )
    assert abs(effective_sum - Decimal("1")) < Decimal("0.001")

    # No pages → AI only → renormalize
    partial = EntityIntelligenceEngine().score(
        brand_name="Acme Analytics",
        pages=[],
        responses=[_resp()],
        website_url="https://acme.example",
    )
    assert partial.status == EntityStatus.PROVISIONAL
    ai = next(c for c in partial.components if c.name == "ai_recognition")
    assert ai.effective_weight == Decimal("1.0000")


def test_unavailable_no_evidence() -> None:
    result = EntityIntelligenceEngine().score(
        brand_name="Acme",
        pages=[],
        responses=[],
        website_url=None,
    )
    assert result.status == EntityStatus.UNAVAILABLE
    assert result.overall_score is None
    assert all(c.score is None for c in result.components)


def test_score_overall_excludes_unavailable() -> None:
    from app.services.entity.models import ComponentScore

    components = (
        ComponentScore(
            name="presence",
            score=Decimal("80"),
            status=EntityStatus.AVAILABLE,
            weight=PRESENCE_WEIGHT,
            effective_weight=None,
            sample_size=2,
        ),
        ComponentScore(
            name="consistency",
            score=None,
            status=EntityStatus.UNAVAILABLE,
            weight=CONSISTENCY_WEIGHT,
            effective_weight=None,
            sample_size=0,
        ),
        ComponentScore(
            name="structured_identity",
            score=Decimal("60"),
            status=EntityStatus.AVAILABLE,
            weight=STRUCTURED_WEIGHT,
            effective_weight=None,
            sample_size=2,
        ),
        ComponentScore(
            name="ai_recognition",
            score=None,
            status=EntityStatus.UNAVAILABLE,
            weight=AI_RECOGNITION_WEIGHT,
            effective_weight=None,
            sample_size=0,
        ),
    )
    overall, updated = score_overall(components)
    assert overall is not None
    assert next(c for c in updated if c.name == "consistency").effective_weight is None
    avail = [c for c in updated if c.status == EntityStatus.AVAILABLE]
    assert abs(sum(c.effective_weight or 0 for c in avail) - Decimal("1")) < Decimal("0.001")
