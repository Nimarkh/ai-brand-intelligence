"""Controlled recommendation category strings (stored on recommendations.category)."""

from __future__ import annotations

from enum import Enum


class RecommendationCategory(str, Enum):
    TECHNICAL = "TECHNICAL"
    SEO = "SEO"
    CONTENT = "CONTENT"
    STRUCTURED_DATA = "STRUCTURED_DATA"
    AI_VISIBILITY = "AI_VISIBILITY"
    ENTITY = "ENTITY"
    PERFORMANCE = "PERFORMANCE"


class RecommendationSource(str, Enum):
    SEO_FINDING = "SEO_FINDING"
    WEBSITE_SCORE = "WEBSITE_SCORE"
    AI_VISIBILITY = "AI_VISIBILITY"
    ENTITY_INTELLIGENCE = "ENTITY_INTELLIGENCE"
    STRUCTURED_DATA = "STRUCTURED_DATA"
