"""Deterministic AI query generation from brand context. No LLM calls."""

from __future__ import annotations

import re
from app.models.enums import AiQueryCategory
from app.services.ai.query_engine.categories import CATEGORY_ORDER
from app.services.ai.query_engine.models import BrandContext, GeneratedQuery

_WS_RE = re.compile(r"\s+")


# (category, template) — templates use Python format fields.
# Keep generic; never hardcode a specific company.
_TEMPLATES: tuple[tuple[AiQueryCategory, str], ...] = (
    # BRAND
    (AiQueryCategory.BRAND, "What is {brand_name}?"),
    (AiQueryCategory.BRAND, "What is {brand_name} known for?"),
    (AiQueryCategory.BRAND, "Can you describe {brand_name} and what it does?"),
    # PRODUCT
    (AiQueryCategory.PRODUCT, "What products or services does {brand_name} offer?"),
    (AiQueryCategory.PRODUCT, "What are the main services provided by {brand_name}?"),
    (AiQueryCategory.PRODUCT, "What does {brand_name} specialize in?"),
    # INDUSTRY
    (AiQueryCategory.INDUSTRY, "What are the leading companies in {industry}?"),
    (
        AiQueryCategory.INDUSTRY,
        "What companies should I consider for {industry} services in {market}?",
    ),
    (AiQueryCategory.INDUSTRY, "Who are notable providers in the {industry} industry?"),
    # COMPETITOR
    (AiQueryCategory.COMPETITOR, "Who are the main alternatives to {brand_name}?"),
    (AiQueryCategory.COMPETITOR, "What companies compete with {brand_name}?"),
    (
        AiQueryCategory.COMPETITOR,
        "Which {industry} companies are often compared with {brand_name}?",
    ),
    # COMMERCIAL
    (AiQueryCategory.COMMERCIAL, "What is the best {industry} company for {market}?"),
    (
        AiQueryCategory.COMMERCIAL,
        "Which {industry} companies should I consider for my business?",
    ),
    (
        AiQueryCategory.COMMERCIAL,
        "Who should I hire for {industry} work in {market}?",
    ),
    # INFORMATIONAL
    (AiQueryCategory.INFORMATIONAL, "How should I choose a {industry} company?"),
    (
        AiQueryCategory.INFORMATIONAL,
        "What should I look for when selecting a {industry} provider?",
    ),
    (
        AiQueryCategory.INFORMATIONAL,
        "What questions should I ask before hiring a {industry} company?",
    ),
)


class QueryGenerator:
    """Build a deterministic, deduplicated query set for one brand."""

    def generate(self, brand: BrandContext, *, max_queries: int) -> list[GeneratedQuery]:
        if max_queries < 1:
            return []

        market = _market_label(brand)
        values = {
            "brand_name": brand.name.strip(),
            "industry": brand.industry.strip(),
            "market": market,
            "country": (brand.country or "").strip() or market,
            "target_market": (brand.target_market or "").strip() or market,
        }

        generated: list[GeneratedQuery] = []
        seen: set[str] = set()
        for category, template in _TEMPLATES:
            text = normalize_query_text(template.format(**values))
            key = text.casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            generated.append(GeneratedQuery(query_text=text, category=category))

        if len(generated) <= max_queries:
            return generated
        return _truncate_with_diversity(generated, max_queries)


def normalize_query_text(value: str) -> str:
    return _WS_RE.sub(" ", value.strip())


def _market_label(brand: BrandContext) -> str:
    if brand.target_market and brand.target_market.strip():
        return brand.target_market.strip()
    if brand.country and brand.country.strip():
        return brand.country.strip()
    return "my market"


def _truncate_with_diversity(
    queries: list[GeneratedQuery],
    max_queries: int,
) -> list[GeneratedQuery]:
    """Keep category diversity while truncating to ``max_queries``.

    Round-robin across CATEGORY_ORDER using the original relative order within
    each category, then append leftovers in original order if slots remain.
    """
    by_category: dict[AiQueryCategory, list[GeneratedQuery]] = {cat: [] for cat in CATEGORY_ORDER}
    for query in queries:
        by_category.setdefault(query.category, []).append(query)

    selected: list[GeneratedQuery] = []
    selected_keys: set[str] = set()
    indices = {cat: 0 for cat in CATEGORY_ORDER}

    while len(selected) < max_queries:
        added = False
        for category in CATEGORY_ORDER:
            bucket = by_category.get(category, [])
            idx = indices[category]
            if idx >= len(bucket):
                continue
            candidate = bucket[idx]
            indices[category] = idx + 1
            key = candidate.query_text.casefold()
            if key in selected_keys:
                continue
            selected.append(candidate)
            selected_keys.add(key)
            added = True
            if len(selected) >= max_queries:
                break
        if not added:
            break

    if len(selected) < max_queries:
        for query in queries:
            key = query.query_text.casefold()
            if key in selected_keys:
                continue
            selected.append(query)
            selected_keys.add(key)
            if len(selected) >= max_queries:
                break

    return selected
