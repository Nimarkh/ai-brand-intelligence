"""Centralized Entity Strength component weights. Must sum to 1.0."""

from __future__ import annotations

from decimal import Decimal

PRESENCE_WEIGHT = Decimal("0.30")
CONSISTENCY_WEIGHT = Decimal("0.25")
STRUCTURED_WEIGHT = Decimal("0.25")
AI_RECOGNITION_WEIGHT = Decimal("0.20")

ENTITY_WEIGHTS: dict[str, Decimal] = {
    "presence": PRESENCE_WEIGHT,
    "consistency": CONSISTENCY_WEIGHT,
    "structured_identity": STRUCTURED_WEIGHT,
    "ai_recognition": AI_RECOGNITION_WEIGHT,
}

assert sum(ENTITY_WEIGHTS.values()) == Decimal("1.00")

# Legal suffixes stripped only when they appear as trailing tokens.
LEGAL_SUFFIXES: frozenset[str] = frozenset(
    {
        "inc",
        "ltd",
        "llc",
        "srl",
        "spa",
        "gmbh",
        "corp",
        "co",
        "limited",
        "incorporated",
        "plc",
        "bv",
        "oy",
        "ab",
    }
)

# Schema types relevant to entity identity (persisted WebsitePage.schema_types).
# Higher weight = stronger identity signal. Configurable and documented.
ENTITY_SCHEMA_TYPE_WEIGHTS: dict[str, Decimal] = {
    "Organization": Decimal("1.00"),
    "Corporation": Decimal("1.00"),
    "LocalBusiness": Decimal("0.95"),
    "Brand": Decimal("0.90"),
    "WebSite": Decimal("0.40"),
    "Product": Decimal("0.35"),
    "Person": Decimal("0.30"),
}

# Types considered "entity-relevant" for coverage (stronger org-oriented set).
ENTITY_RELEVANT_SCHEMA_TYPES: frozenset[str] = frozenset(
    {
        "Organization",
        "Corporation",
        "LocalBusiness",
        "Brand",
        "WebSite",
        "Product",
        "Person",
    }
)

STRONG_ENTITY_SCHEMA_TYPES: frozenset[str] = frozenset(
    {
        "Organization",
        "Corporation",
        "LocalBusiness",
        "Brand",
    }
)
