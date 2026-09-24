"""Pure SEO analyzer. Consumes stored page snapshots and returns deterministic findings."""

from __future__ import annotations

from app.services.seo_analyzer.models import AnalyzerThresholds, FindingResult, PageSnapshot
from app.services.seo_analyzer.rules import (
    check_duplicate_meta_descriptions,
    check_duplicate_titles,
    check_empty_audit,
    check_page,
)


class SEOAnalyzer:
    """Analyze WebsitePage-like snapshots without database or network access.

    Given identical page data and thresholds, ``analyze`` returns identical findings.
    """

    def __init__(self, thresholds: AnalyzerThresholds | None = None) -> None:
        self.thresholds = thresholds or AnalyzerThresholds()

    def analyze(
        self,
        pages: list[PageSnapshot],
        *,
        crawl_origin: str | None = None,
    ) -> list[FindingResult]:
        empty = check_empty_audit(pages)
        if empty:
            return empty

        findings: list[FindingResult] = []
        for page in sorted(pages, key=lambda item: str(item.id)):
            findings.extend(check_page(page, self.thresholds, crawl_origin))
        findings.extend(check_duplicate_titles(pages))
        findings.extend(check_duplicate_meta_descriptions(pages))
        return findings
