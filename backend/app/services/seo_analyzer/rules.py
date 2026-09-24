"""Deterministic SEO rule checks. Pure functions over PageSnapshot data."""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlsplit
from uuid import UUID

from app.models.enums import FindingSeverity
from app.services.seo_analyzer.models import AnalyzerThresholds, FindingResult, PageSnapshot

# Categories (string values stored on SeoFinding.category)
CATEGORY_TITLE = "TITLE"
CATEGORY_META_DESCRIPTION = "META_DESCRIPTION"
CATEGORY_CANONICAL = "CANONICAL"
CATEGORY_HEADINGS = "HEADINGS"
CATEGORY_CONTENT = "CONTENT"
CATEGORY_STRUCTURED_DATA = "STRUCTURED_DATA"
CATEGORY_STATUS = "STATUS"
CATEGORY_PERFORMANCE = "PERFORMANCE"
CATEGORY_CRAWL = "CRAWL"


def check_title(page: PageSnapshot, thresholds: AnalyzerThresholds) -> list[FindingResult]:
    """Missing title takes precedence over length findings."""
    raw = page.title
    if raw is None or not raw.strip():
        return [
            FindingResult(
                category=CATEGORY_TITLE,
                severity=FindingSeverity.HIGH,
                title="Missing page title",
                description="This page has no HTML title element (or the title is empty).",
                recommendation="Add a descriptive <title> element to this page.",
                page_id=page.id,
            )
        ]

    length = len(raw.strip())
    if length < thresholds.title_min_length:
        return [
            FindingResult(
                category=CATEGORY_TITLE,
                severity=FindingSeverity.LOW,
                title="Page title is very short",
                description=(
                    f"The page title is {length} characters after trimming. "
                    f"As a practical SEO guideline, titles shorter than "
                    f"{thresholds.title_min_length} characters are often less descriptive."
                ),
                recommendation="Expand the title so it clearly describes the page content.",
                page_id=page.id,
            )
        ]
    if length > thresholds.title_max_length:
        return [
            FindingResult(
                category=CATEGORY_TITLE,
                severity=FindingSeverity.MEDIUM,
                title="Page title is long",
                description=(
                    f"The page title is {length} characters. "
                    f"As a practical SEO guideline, titles longer than "
                    f"{thresholds.title_max_length} characters may be truncated in search results. "
                    "This is not a strict search-engine rule."
                ),
                recommendation="Shorten the title while keeping it descriptive.",
                page_id=page.id,
            )
        ]
    return []


def check_meta_description(page: PageSnapshot, thresholds: AnalyzerThresholds) -> list[FindingResult]:
    """Missing meta description takes precedence over length findings."""
    raw = page.meta_description
    if raw is None or not raw.strip():
        return [
            FindingResult(
                category=CATEGORY_META_DESCRIPTION,
                severity=FindingSeverity.MEDIUM,
                title="Missing meta description",
                description="This page has no meta description (or the description is empty).",
                recommendation="Add a concise meta description that summarizes the page.",
                page_id=page.id,
            )
        ]

    length = len(raw.strip())
    if length < thresholds.meta_description_min_length:
        return [
            FindingResult(
                category=CATEGORY_META_DESCRIPTION,
                severity=FindingSeverity.LOW,
                title="Meta description is very short",
                description=(
                    f"The meta description is {length} characters after trimming. "
                    f"As a practical guideline, descriptions shorter than "
                    f"{thresholds.meta_description_min_length} characters may provide little context."
                ),
                recommendation="Expand the meta description with a clearer page summary.",
                page_id=page.id,
            )
        ]
    if length > thresholds.meta_description_max_length:
        return [
            FindingResult(
                category=CATEGORY_META_DESCRIPTION,
                severity=FindingSeverity.LOW,
                title="Meta description is long",
                description=(
                    f"The meta description is {length} characters. "
                    f"As a practical guideline, descriptions longer than "
                    f"{thresholds.meta_description_max_length} characters may be truncated in search results. "
                    "This is not a strict search-engine requirement."
                ),
                recommendation="Shorten the meta description while keeping the main message.",
                page_id=page.id,
            )
        ]
    return []


def check_canonical(page: PageSnapshot, crawl_origin: str | None) -> list[FindingResult]:
    """Canonical checks. Missing and outside-site are mutually exclusive.

    Canonical policy:
    - Same host (case-insensitive) and same effective port are acceptable.
    - http and https are treated as equivalent for the same host and port.
    - Subdomains do not match (www.example.com ≠ example.com).
    - The canonical URL does not need to equal the page URL.
    """
    if page.canonical_url is None or not page.canonical_url.strip():
        return [
            FindingResult(
                category=CATEGORY_CANONICAL,
                severity=FindingSeverity.MEDIUM,
                title="Canonical URL missing",
                description="No canonical link was detected on this page.",
                recommendation="Consider adding a canonical URL where appropriate.",
                page_id=page.id,
            )
        ]

    if crawl_origin is None:
        return []

    if not _canonical_matches_site(page.canonical_url.strip(), crawl_origin):
        return [
            FindingResult(
                category=CATEGORY_CANONICAL,
                severity=FindingSeverity.MEDIUM,
                title="Canonical URL points outside the site",
                description=(
                    "The canonical URL points to a different host or non-equivalent port "
                    "than the crawl origin. http and https for the same host with default "
                    "web ports (80/443) are treated as the same site."
                ),
                recommendation="Review the canonical URL and point it at the intended on-site page.",
                page_id=page.id,
            )
        ]
    return []


def check_headings(page: PageSnapshot) -> list[FindingResult]:
    if page.h1_count is None:
        return []
    if page.h1_count == 0:
        return [
            FindingResult(
                category=CATEGORY_HEADINGS,
                severity=FindingSeverity.MEDIUM,
                title="Missing H1 heading",
                description="No H1 heading was detected on this page.",
                recommendation="Add a single clear H1 that describes the main topic of the page.",
                page_id=page.id,
            )
        ]
    if page.h1_count > 1:
        return [
            FindingResult(
                category=CATEGORY_HEADINGS,
                severity=FindingSeverity.MEDIUM,
                title="Multiple H1 headings",
                description=(
                    f"This page has {page.h1_count} H1 headings. "
                    "Multiple H1 elements are not always technically invalid, "
                    "but they can make page structure less clear and should be reviewed."
                ),
                recommendation="Review heading structure and prefer a single primary H1 where practical.",
                page_id=page.id,
            )
        ]
    return []


def check_content(page: PageSnapshot, thresholds: AnalyzerThresholds) -> list[FindingResult]:
    if page.word_count is None:
        return []
    if page.word_count < thresholds.low_word_count:
        return [
            FindingResult(
                category=CATEGORY_CONTENT,
                severity=FindingSeverity.LOW,
                title="Very little textual content",
                description=(
                    f"Very little textual content was detected on this page "
                    f"({page.word_count} words). "
                    f"This is a heuristic threshold ({thresholds.low_word_count} words); "
                    "not every page needs that much text."
                ),
                recommendation="Review whether the page needs more meaningful textual content.",
                page_id=page.id,
            )
        ]
    return []


def check_structured_data(page: PageSnapshot) -> list[FindingResult]:
    if page.has_schema is False:
        return [
            FindingResult(
                category=CATEGORY_STRUCTURED_DATA,
                severity=FindingSeverity.LOW,
                title="No structured data detected",
                description=(
                    "No structured data was detected on this page. "
                    "Structured data is not mandatory for every page."
                ),
                recommendation="Consider adding relevant structured data where it helps machines understand the page.",
                page_id=page.id,
            )
        ]
    return []


def check_status(page: PageSnapshot) -> list[FindingResult]:
    """HTTP error statuses only. Null status (e.g. network failure) is not flagged here."""
    code = page.status_code
    if code is None or code < 400:
        return []
    if code >= 500:
        severity = FindingSeverity.HIGH
        title = f"Server error status ({code})"
    else:
        severity = FindingSeverity.MEDIUM
        title = f"Client error status ({code})"
    return [
        FindingResult(
            category=CATEGORY_STATUS,
            severity=severity,
            title=title,
            description=f"This page returned HTTP status code {code}.",
            recommendation="Investigate the response and restore a successful page response where intended.",
            page_id=page.id,
        )
    ]


def check_performance(page: PageSnapshot, thresholds: AnalyzerThresholds) -> list[FindingResult]:
    """Request/load time from the crawler only — not Core Web Vitals or full browser rendering."""
    if page.load_time_ms is None:
        return []
    if page.load_time_ms > thresholds.slow_response_ms:
        return [
            FindingResult(
                category=CATEGORY_PERFORMANCE,
                severity=FindingSeverity.MEDIUM,
                title="Slow page response",
                description=(
                    f"The crawler measured a load time of {page.load_time_ms} ms "
                    f"(threshold {thresholds.slow_response_ms} ms). "
                    "This is request/load time only and does not represent Core Web Vitals "
                    "or full browser rendering performance."
                ),
                recommendation="Investigate server response time and page weight for this URL.",
                page_id=page.id,
            )
        ]
    return []


def check_page(page: PageSnapshot, thresholds: AnalyzerThresholds, crawl_origin: str | None) -> list[FindingResult]:
    """Run all page-level checks. Order is stable for determinism."""
    findings: list[FindingResult] = []
    findings.extend(check_title(page, thresholds))
    findings.extend(check_meta_description(page, thresholds))
    findings.extend(check_canonical(page, crawl_origin))
    findings.extend(check_headings(page))
    findings.extend(check_content(page, thresholds))
    findings.extend(check_structured_data(page))
    findings.extend(check_status(page))
    findings.extend(check_performance(page, thresholds))
    return findings


def check_empty_audit(pages: list[PageSnapshot]) -> list[FindingResult]:
    if pages:
        return []
    return [
        FindingResult(
            category=CATEGORY_CRAWL,
            severity=FindingSeverity.HIGH,
            title="No pages were successfully crawled",
            description=(
                "This audit has no WebsitePage records. "
                "There is no page data available for SEO analysis."
            ),
            recommendation="Run a successful website crawl before analyzing SEO findings.",
            page_id=None,
        )
    ]


def check_duplicate_titles(pages: list[PageSnapshot]) -> list[FindingResult]:
    """One finding per affected page for shared non-empty titles."""
    groups: dict[str, list[UUID]] = defaultdict(list)
    for page in pages:
        if page.title is None:
            continue
        key = page.title.strip()
        if not key:
            continue
        groups[key].append(page.id)

    findings: list[FindingResult] = []
    for title_text, page_ids in sorted(groups.items(), key=lambda item: item[0]):
        if len(page_ids) < 2:
            continue
        count = len(page_ids)
        for page_id in sorted(page_ids, key=str):
            findings.append(
                FindingResult(
                    category=CATEGORY_TITLE,
                    severity=FindingSeverity.MEDIUM,
                    title="Duplicate page title",
                    description=(
                        f'The title "{_truncate(title_text, 80)}" is shared by {count} pages in this audit.'
                    ),
                    recommendation="Give each important page a unique, descriptive title.",
                    page_id=page_id,
                )
            )
    return findings


def check_duplicate_meta_descriptions(pages: list[PageSnapshot]) -> list[FindingResult]:
    """One finding per affected page. Empty/null descriptions are handled by the missing rule."""
    groups: dict[str, list[UUID]] = defaultdict(list)
    for page in pages:
        if page.meta_description is None:
            continue
        key = page.meta_description.strip()
        if not key:
            continue
        groups[key].append(page.id)

    findings: list[FindingResult] = []
    for text, page_ids in sorted(groups.items(), key=lambda item: item[0]):
        if len(page_ids) < 2:
            continue
        count = len(page_ids)
        for page_id in sorted(page_ids, key=str):
            findings.append(
                FindingResult(
                    category=CATEGORY_META_DESCRIPTION,
                    severity=FindingSeverity.MEDIUM,
                    title="Duplicate meta description",
                    description=(
                        f'The meta description "{_truncate(text, 80)}" is shared by '
                        f"{count} pages in this audit."
                    ),
                    recommendation="Write a unique meta description for each important page.",
                    page_id=page_id,
                )
            )
    return findings


def _canonical_matches_site(canonical_url: str, crawl_origin: str) -> bool:
    """True when host matches; http/https with default ports are interchangeable.

    Policy:
    - Hostname must match (case-insensitive). Subdomains do not match.
    - If effective ports are equal, the canonical is on-site.
    - If both sides use a default web port (80 or 443), http↔https is allowed.
    - Explicit non-default ports must match exactly.
    """
    left = urlsplit(canonical_url.strip())
    right = urlsplit(crawl_origin.strip())
    if not left.hostname or not right.hostname:
        return False
    if left.hostname.lower() != right.hostname.lower():
        return False
    left_port = _effective_port(left.scheme, left.port)
    right_port = _effective_port(right.scheme, right.port)
    if left_port == right_port:
        return True
    return _is_default_web_port(left_port) and _is_default_web_port(right_port)


def _effective_port(scheme: str, port: int | None) -> int | None:
    if port is not None:
        return port
    lowered = (scheme or "").lower()
    if lowered == "http":
        return 80
    if lowered == "https":
        return 443
    return None


def _is_default_web_port(port: int | None) -> bool:
    return port in {80, 443}


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"
