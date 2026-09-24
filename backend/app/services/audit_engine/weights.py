"""Deterministic scoring configuration for the Audit Engine.

All weights live here. They are not user-editable via the API.
"""

from __future__ import annotations

from decimal import Decimal

# ---------------------------------------------------------------------------
# Website Health component weights (must sum to 1.0)
# ---------------------------------------------------------------------------
WEBSITE_HEALTH_WEIGHTS: dict[str, Decimal] = {
    "technical": Decimal("0.30"),
    "seo": Decimal("0.30"),
    "content": Decimal("0.20"),
    "structured_data": Decimal("0.20"),
}

# Final overall formula (future phases). AI Visibility and Entity are unavailable
# in Phase 09, so provisional overall renormalizes Website Health + SEO only.
FINAL_OVERALL_WEIGHTS: dict[str, Decimal] = {
    "website_health": Decimal("0.25"),
    "seo": Decimal("0.20"),
    "ai_visibility": Decimal("0.35"),
    "entity_strength": Decimal("0.20"),
}

# Currently available overall dimensions (Phase 09)
PROVISIONAL_OVERALL_AVAILABLE = ("website_health", "seo")

# ---------------------------------------------------------------------------
# Severity weights used inside category penalty sums
# ---------------------------------------------------------------------------
SEVERITY_WEIGHTS: dict[str, Decimal] = {
    "HIGH": Decimal("15"),
    "MEDIUM": Decimal("7"),
    "LOW": Decimal("3"),
    "INFO": Decimal("0"),
}

# ---------------------------------------------------------------------------
# Finding category → score component (explicit; no string guessing elsewhere)
# ---------------------------------------------------------------------------
FINDING_CATEGORY_TO_COMPONENT: dict[str, str] = {
    "STATUS": "technical",
    "PERFORMANCE": "technical",
    "CRAWL": "technical",
    "TITLE": "seo",
    "META_DESCRIPTION": "seo",
    "CANONICAL": "seo",
    "HEADINGS": "seo",
    "CONTENT": "content",
    "STRUCTURED_DATA": "structured_data",
}

# ---------------------------------------------------------------------------
# Rule weights (stable rule ids → impact multipliers)
# ---------------------------------------------------------------------------
RULE_WEIGHTS: dict[str, Decimal] = {
    "missing_title": Decimal("1.00"),
    "long_title": Decimal("0.35"),
    "short_title": Decimal("0.20"),
    "missing_meta": Decimal("0.70"),
    "long_meta": Decimal("0.25"),
    "short_meta": Decimal("0.15"),
    "missing_canonical": Decimal("0.55"),
    "external_canonical": Decimal("0.70"),
    "missing_h1": Decimal("0.65"),
    "multiple_h1": Decimal("0.35"),
    "low_word_count": Decimal("0.35"),
    "missing_structured_data": Decimal("0.35"),
    "status_4xx": Decimal("0.80"),
    "status_5xx": Decimal("1.00"),
    "slow_response": Decimal("0.35"),
    "duplicate_title": Decimal("0.55"),
    "duplicate_meta": Decimal("0.35"),
    "empty_audit": Decimal("1.00"),
    "unknown": Decimal("0.40"),
}

# Exact SeoFinding.title → rule id (status titles are resolved separately)
FINDING_TITLE_TO_RULE: dict[str, str] = {
    "Missing page title": "missing_title",
    "Page title is very short": "short_title",
    "Page title is long": "long_title",
    "Missing meta description": "missing_meta",
    "Meta description is very short": "short_meta",
    "Meta description is long": "long_meta",
    "Canonical URL missing": "missing_canonical",
    "Canonical URL points outside the site": "external_canonical",
    "Missing H1 heading": "missing_h1",
    "Multiple H1 headings": "multiple_h1",
    "Very little textual content": "low_word_count",
    "No structured data detected": "missing_structured_data",
    "Slow page response": "slow_response",
    "Duplicate page title": "duplicate_title",
    "Duplicate meta description": "duplicate_meta",
    "No pages were successfully crawled": "empty_audit",
}

# Maximum penalty points subtracted from a category before clamping to 0–100
MAX_CATEGORY_PENALTY = Decimal("100")

# Display / persistence quantize
SCORE_QUANTIZE = Decimal("0.01")
