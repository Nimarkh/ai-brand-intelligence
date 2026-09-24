"""Centralized AI Visibility component weights. Must sum to 1.0."""

from __future__ import annotations

from decimal import Decimal

MENTION_WEIGHT = Decimal("0.30")
CITATION_WEIGHT = Decimal("0.25")
POSITION_WEIGHT = Decimal("0.25")
SEMANTIC_WEIGHT = Decimal("0.20")

VISIBILITY_WEIGHTS: dict[str, Decimal] = {
    "mention": MENTION_WEIGHT,
    "citation": CITATION_WEIGHT,
    "position": POSITION_WEIGHT,
    "semantic": SEMANTIC_WEIGHT,
}

assert sum(VISIBILITY_WEIGHTS.values()) == Decimal("1.00")

# Bounded brand-mention bonus added to lexical overlap (Phase 12 semantic heuristic).
SEMANTIC_BRAND_BONUS = Decimal("0.10")

# Response mention-position → score (NOT search-engine ranking).
POSITION_SCORE_MAP: dict[int, Decimal] = {
    1: Decimal("100"),
    2: Decimal("75"),
    3: Decimal("50"),
    4: Decimal("25"),
}
POSITION_SCORE_DEFAULT = Decimal("0")  # position >= 5 or not mentioned
