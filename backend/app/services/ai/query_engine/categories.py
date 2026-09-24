"""AI query category helpers and template category ordering."""

from __future__ import annotations

from app.models.enums import AiQueryCategory

# Stable category order for generation and diversity-preserving truncation.
CATEGORY_ORDER: tuple[AiQueryCategory, ...] = (
    AiQueryCategory.BRAND,
    AiQueryCategory.PRODUCT,
    AiQueryCategory.INDUSTRY,
    AiQueryCategory.COMPETITOR,
    AiQueryCategory.COMMERCIAL,
    AiQueryCategory.INFORMATIONAL,
)
