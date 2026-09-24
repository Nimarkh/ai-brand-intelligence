"""Pure SEO analyzer unit tests. No database."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.models.enums import FindingSeverity
from app.services.seo_analyzer import AnalyzerThresholds, SEOAnalyzer
from app.services.seo_analyzer.models import PageSnapshot
from app.services.seo_analyzer.rules import (
    CATEGORY_CANONICAL,
    CATEGORY_CONTENT,
    CATEGORY_CRAWL,
    CATEGORY_HEADINGS,
    CATEGORY_META_DESCRIPTION,
    CATEGORY_PERFORMANCE,
    CATEGORY_STATUS,
    CATEGORY_STRUCTURED_DATA,
    CATEGORY_TITLE,
)

THRESHOLDS = AnalyzerThresholds(
    title_max_length=60,
    title_min_length=10,
    meta_description_max_length=160,
    meta_description_min_length=50,
    low_word_count=300,
    slow_response_ms=2000,
)
ORIGIN = "https://example.com"


def _page(
    *,
    page_id: UUID | None = None,
    url: str = "https://example.com/page",
    status_code: int | None = 200,
    title: str | None = "A solid page title here",
    meta_description: str | None = "A meta description that is long enough to pass the minimum length heuristic for tests.",
    canonical_url: str | None = "https://example.com/page",
    word_count: int | None = 500,
    h1_count: int | None = 1,
    has_schema: bool | None = True,
    load_time_ms: int | None = 400,
) -> PageSnapshot:
    return PageSnapshot(
        id=page_id or uuid4(),
        url=url,
        status_code=status_code,
        title=title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        word_count=word_count,
        h1_count=h1_count,
        has_schema=has_schema,
        load_time_ms=load_time_ms,
    )


def _titles(findings) -> list[str]:
    return [finding.title for finding in findings]


def _by_category(findings, category: str):
    return [finding for finding in findings if finding.category == category]


def test_missing_title() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(title=None)], crawl_origin=ORIGIN)
    title_findings = _by_category(findings, CATEGORY_TITLE)
    assert len(title_findings) == 1
    assert title_findings[0].title == "Missing page title"
    assert title_findings[0].severity == FindingSeverity.HIGH
    assert "title too" not in title_findings[0].title.lower()


def test_missing_title_empty_string() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(title="   ")], crawl_origin=ORIGIN)
    assert any(f.title == "Missing page title" for f in findings)


def test_short_title() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(title="Short")], crawl_origin=ORIGIN)
    match = [f for f in findings if f.title == "Page title is very short"]
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.LOW


def test_long_title() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    long_title = "T" * 61
    findings = analyzer.analyze([_page(title=long_title)], crawl_origin=ORIGIN)
    match = [f for f in findings if f.title == "Page title is long"]
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.MEDIUM
    assert "guideline" in match[0].description.lower()


def test_missing_title_does_not_also_flag_length() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(title=None)], crawl_origin=ORIGIN)
    titles = _titles(_by_category(findings, CATEGORY_TITLE))
    assert titles == ["Missing page title"]


def test_missing_meta_description() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(meta_description=None)], crawl_origin=ORIGIN)
    match = _by_category(findings, CATEGORY_META_DESCRIPTION)
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.MEDIUM
    assert match[0].title == "Missing meta description"


def test_short_meta_description() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(meta_description="Too short")], crawl_origin=ORIGIN)
    match = [f for f in findings if f.title == "Meta description is very short"]
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.LOW


def test_long_meta_description() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(meta_description="M" * 161)], crawl_origin=ORIGIN)
    match = [f for f in findings if f.title == "Meta description is long"]
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.LOW


def test_missing_canonical() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(canonical_url=None)], crawl_origin=ORIGIN)
    match = _by_category(findings, CATEGORY_CANONICAL)
    assert len(match) == 1
    assert match[0].title == "Canonical URL missing"
    assert match[0].severity == FindingSeverity.MEDIUM


def test_external_canonical() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze(
        [_page(canonical_url="https://other.example/page")],
        crawl_origin=ORIGIN,
    )
    match = [f for f in findings if f.title == "Canonical URL points outside the site"]
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.MEDIUM


def test_canonical_http_https_same_host_is_allowed() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze(
        [_page(canonical_url="http://example.com/page")],
        crawl_origin="https://example.com",
    )
    assert _by_category(findings, CATEGORY_CANONICAL) == []


def test_missing_h1() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(h1_count=0)], crawl_origin=ORIGIN)
    match = [f for f in findings if f.title == "Missing H1 heading"]
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.MEDIUM


def test_multiple_h1() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(h1_count=3)], crawl_origin=ORIGIN)
    match = [f for f in findings if f.title == "Multiple H1 headings"]
    assert len(match) == 1
    assert "less clear" in match[0].description


def test_low_word_count() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(word_count=50)], crawl_origin=ORIGIN)
    match = [f for f in findings if f.category == CATEGORY_CONTENT]
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.LOW
    assert "Very little textual content" in match[0].description


def test_missing_structured_data() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(has_schema=False)], crawl_origin=ORIGIN)
    match = _by_category(findings, CATEGORY_STRUCTURED_DATA)
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.LOW
    assert "not mandatory" in match[0].description.lower()


def test_status_404() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(status_code=404)], crawl_origin=ORIGIN)
    match = _by_category(findings, CATEGORY_STATUS)
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.MEDIUM
    assert "404" in match[0].title
    assert "404" in match[0].description


def test_status_500() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(status_code=500)], crawl_origin=ORIGIN)
    match = _by_category(findings, CATEGORY_STATUS)
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.HIGH
    assert "500" in match[0].description


def test_null_status_not_flagged() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(status_code=None)], crawl_origin=ORIGIN)
    assert _by_category(findings, CATEGORY_STATUS) == []


def test_slow_response() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(load_time_ms=2500)], crawl_origin=ORIGIN)
    match = _by_category(findings, CATEGORY_PERFORMANCE)
    assert len(match) == 1
    assert match[0].severity == FindingSeverity.MEDIUM
    assert "Core Web Vitals" not in match[0].title
    assert "request/load time" in match[0].description.lower()


def test_healthy_page_produces_no_unnecessary_findings() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page()], crawl_origin=ORIGIN)
    assert findings == []


def test_duplicate_titles() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    a = _page(page_id=UUID("11111111-1111-4111-8111-111111111111"), title="Products", url="https://example.com/a")
    b = _page(page_id=UUID("22222222-2222-4222-8222-222222222222"), title="Products", url="https://example.com/b")
    findings = analyzer.analyze([a, b], crawl_origin=ORIGIN)
    dupes = [f for f in findings if f.title == "Duplicate page title"]
    assert len(dupes) == 2
    assert {f.page_id for f in dupes} == {a.id, b.id}
    assert all(f.severity == FindingSeverity.MEDIUM for f in dupes)


def test_duplicate_meta_descriptions() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    meta = "A shared meta description that is long enough for the minimum length heuristic."
    a = _page(page_id=UUID("11111111-1111-4111-8111-111111111111"), meta_description=meta, title="Title Alpha Page")
    b = _page(page_id=UUID("22222222-2222-4222-8222-222222222222"), meta_description=meta, title="Title Beta Page")
    findings = analyzer.analyze([a, b], crawl_origin=ORIGIN)
    dupes = [f for f in findings if f.title == "Duplicate meta description"]
    assert len(dupes) == 2
    assert all(f.severity == FindingSeverity.MEDIUM for f in dupes)
    assert all(f.category == CATEGORY_META_DESCRIPTION for f in dupes)


def test_empty_audit() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([], crawl_origin=ORIGIN)
    assert len(findings) == 1
    assert findings[0].category == CATEGORY_CRAWL
    assert findings[0].severity == FindingSeverity.HIGH
    assert findings[0].title == "No pages were successfully crawled"
    assert findings[0].page_id is None


def test_multiple_issues_on_same_page() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze(
        [
            _page(
                title=None,
                meta_description=None,
                h1_count=0,
                has_schema=False,
                word_count=10,
                status_code=404,
                load_time_ms=5000,
                canonical_url=None,
            )
        ],
        crawl_origin=ORIGIN,
    )
    categories = {f.category for f in findings}
    assert CATEGORY_TITLE in categories
    assert CATEGORY_META_DESCRIPTION in categories
    assert CATEGORY_HEADINGS in categories
    assert CATEGORY_STRUCTURED_DATA in categories
    assert CATEGORY_CONTENT in categories
    assert CATEGORY_STATUS in categories
    assert CATEGORY_PERFORMANCE in categories
    assert CATEGORY_CANONICAL in categories
    assert len(findings) >= 8


def test_deterministic_output() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    page_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    page = _page(
        page_id=page_id,
        title=None,
        meta_description="x" * 20,
        h1_count=2,
        has_schema=False,
    )
    first = analyzer.analyze([page], crawl_origin=ORIGIN)
    second = analyzer.analyze([page], crawl_origin=ORIGIN)
    assert [
        (f.category, f.severity, f.title, f.description, f.recommendation, f.page_id) for f in first
    ] == [
        (f.category, f.severity, f.title, f.description, f.recommendation, f.page_id) for f in second
    ]


def test_every_finding_has_recommendation() -> None:
    analyzer = SEOAnalyzer(THRESHOLDS)
    findings = analyzer.analyze([_page(title=None, meta_description=None)], crawl_origin=ORIGIN)
    assert findings
    assert all(f.recommendation for f in findings)
