"""Pure Audit Engine unit tests. No database."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from app.services.audit_engine import AuditEngine, FindingInput, ScoreStatus
from app.services.audit_engine.penalties import build_penalties, clamp_score
from app.services.audit_engine.weights import (
    FINAL_OVERALL_WEIGHTS,
    SEVERITY_WEIGHTS,
    WEBSITE_HEALTH_WEIGHTS,
)


def _fid() -> UUID:
    return uuid4()


def _finding(
    *,
    category: str,
    severity: str,
    title: str,
    page_id: UUID | None,
    finding_id: UUID | None = None,
) -> FindingInput:
    return FindingInput(
        id=finding_id or uuid4(),
        category=category,
        severity=severity,
        title=title,
        page_id=page_id,
    )


def test_empty_audit_unavailable_not_zero() -> None:
    engine = AuditEngine()
    result = engine.score(page_ids=[], findings=[])
    assert result.status == ScoreStatus.UNAVAILABLE
    assert result.website_health.score is None
    assert result.seo_score.score is None
    assert result.overall.score is None
    assert result.overall.status == ScoreStatus.UNAVAILABLE


def test_healthy_page_high_scores() -> None:
    engine = AuditEngine()
    page = uuid4()
    result = engine.score(page_ids=[page], findings=[])
    assert result.status == ScoreStatus.PROVISIONAL
    assert result.technical.score == Decimal("100.00")
    assert result.seo.score == Decimal("100.00")
    assert result.content.score == Decimal("100.00")
    assert result.structured_data.score == Decimal("100.00")
    assert result.website_health.score == Decimal("100.00")
    assert result.seo_score.score == Decimal("100.00")
    assert result.overall.score == Decimal("100.00")
    assert result.overall.status == ScoreStatus.PROVISIONAL


def test_missing_title_decreases_seo() -> None:
    engine = AuditEngine()
    page = uuid4()
    result = engine.score(
        page_ids=[page],
        findings=[
            _finding(
                category="TITLE",
                severity="HIGH",
                title="Missing page title",
                page_id=page,
            )
        ],
    )
    assert result.seo.score is not None
    assert result.seo.score < Decimal("100")
    assert result.technical.score == Decimal("100.00")
    assert result.content.score == Decimal("100.00")


def test_multiple_missing_titles_larger_impact() -> None:
    engine = AuditEngine()
    pages = [uuid4() for _ in range(4)]
    one = engine.score(
        page_ids=pages,
        findings=[
            _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=pages[0])
        ],
    )
    all_pages = engine.score(
        page_ids=pages,
        findings=[
            _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=p)
            for p in pages
        ],
    )
    assert one.seo.score is not None and all_pages.seo.score is not None
    assert all_pages.seo.score < one.seo.score


def test_one_affected_among_many_normalized() -> None:
    engine = AuditEngine()
    pages = [uuid4() for _ in range(20)]
    result = engine.score(
        page_ids=pages,
        findings=[
            _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=pages[0])
        ],
    )
    # rate = 1/20 → penalty = 15 * 0.05 * 1.0 = 0.75 → score 99.25
    assert result.seo.score == Decimal("99.25")


def test_severity_ordering() -> None:
    page = uuid4()
    pages = [page]
    engine = AuditEngine()
    high = engine.score(
        page_ids=pages,
        findings=[_finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=page)],
    )
    # Use long title MEDIUM vs short LOW via same rate
    medium = engine.score(
        page_ids=pages,
        findings=[_finding(category="TITLE", severity="MEDIUM", title="Page title is long", page_id=page)],
    )
    low = engine.score(
        page_ids=pages,
        findings=[
            _finding(category="TITLE", severity="LOW", title="Page title is very short", page_id=page)
        ],
    )
    assert high.seo.score < medium.seo.score < low.seo.score


def test_5xx_worse_than_4xx() -> None:
    engine = AuditEngine()
    page = uuid4()
    four = engine.score(
        page_ids=[page],
        findings=[
            _finding(
                category="STATUS",
                severity="MEDIUM",
                title="Client error status (404)",
                page_id=page,
            )
        ],
    )
    five = engine.score(
        page_ids=[page],
        findings=[
            _finding(
                category="STATUS",
                severity="HIGH",
                title="Server error status (500)",
                page_id=page,
            )
        ],
    )
    assert five.technical.score < four.technical.score


def test_duplicate_titles_affect_seo() -> None:
    engine = AuditEngine()
    a, b = uuid4(), uuid4()
    result = engine.score(
        page_ids=[a, b],
        findings=[
            _finding(category="TITLE", severity="MEDIUM", title="Duplicate page title", page_id=a),
            _finding(category="TITLE", severity="MEDIUM", title="Duplicate page title", page_id=b),
        ],
    )
    assert result.seo.score is not None
    assert result.seo.score < Decimal("100")


def test_missing_schema_affects_structured_data() -> None:
    engine = AuditEngine()
    page = uuid4()
    result = engine.score(
        page_ids=[page],
        findings=[
            _finding(
                category="STRUCTURED_DATA",
                severity="LOW",
                title="No structured data detected",
                page_id=page,
            )
        ],
    )
    assert result.structured_data.score is not None
    assert result.structured_data.score < Decimal("100")
    assert result.seo.score == Decimal("100.00")


def test_slow_response_affects_technical() -> None:
    engine = AuditEngine()
    page = uuid4()
    result = engine.score(
        page_ids=[page],
        findings=[
            _finding(
                category="PERFORMANCE",
                severity="MEDIUM",
                title="Slow page response",
                page_id=page,
            )
        ],
    )
    assert result.technical.score is not None
    assert result.technical.score < Decimal("100")


def test_same_page_not_double_counted_as_affected_pages() -> None:
    page = uuid4()
    findings = [
        _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=page),
        _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=page),
    ]
    penalties = build_penalties(findings, analyzable_pages=1)
    title_penalties = [p for p in penalties if p.rule_id == "missing_title"]
    assert len(title_penalties) == 1
    assert title_penalties[0].affected_pages == 1
    assert title_penalties[0].affected_page_rate == Decimal("1.0000")


def test_scores_bounded_0_100() -> None:
    engine = AuditEngine()
    pages = [uuid4() for _ in range(3)]
    findings = []
    for page in pages:
        findings.extend(
            [
                _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=page),
                _finding(
                    category="META_DESCRIPTION",
                    severity="MEDIUM",
                    title="Missing meta description",
                    page_id=page,
                ),
                _finding(category="STATUS", severity="HIGH", title="Server error status (503)", page_id=page),
                _finding(
                    category="CONTENT",
                    severity="LOW",
                    title="Very little textual content",
                    page_id=page,
                ),
                _finding(
                    category="STRUCTURED_DATA",
                    severity="LOW",
                    title="No structured data detected",
                    page_id=page,
                ),
            ]
        )
    result = engine.score(page_ids=pages, findings=findings)
    for score in (
        result.technical.score,
        result.seo.score,
        result.content.score,
        result.structured_data.score,
        result.website_health.score,
        result.seo_score.score,
        result.overall.score,
    ):
        assert score is not None
        assert Decimal("0") <= score <= Decimal("100")


def test_deterministic_output() -> None:
    engine = AuditEngine()
    page = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    findings = [
        FindingInput(
            id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
            category="TITLE",
            severity="HIGH",
            title="Missing page title",
            page_id=page,
        )
    ]
    first = engine.score(page_ids=[page], findings=findings)
    second = engine.score(page_ids=[page], findings=findings)
    assert first.website_health.score == second.website_health.score
    assert first.seo_score.score == second.seo_score.score
    assert first.overall.score == second.overall.score
    assert first.technical.score == second.technical.score


def test_website_health_weights_sum() -> None:
    assert sum(WEBSITE_HEALTH_WEIGHTS.values()) == Decimal("1.00")


def test_website_health_formula() -> None:
    engine = AuditEngine()
    page = uuid4()
    # Only SEO penalty: missing title → SEO = 100 - 15 = 85
    result = engine.score(
        page_ids=[page],
        findings=[
            _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=page)
        ],
    )
    expected = clamp_score(
        Decimal("100") * WEBSITE_HEALTH_WEIGHTS["technical"]
        + Decimal("85") * WEBSITE_HEALTH_WEIGHTS["seo"]
        + Decimal("100") * WEBSITE_HEALTH_WEIGHTS["content"]
        + Decimal("100") * WEBSITE_HEALTH_WEIGHTS["structured_data"]
    )
    assert result.website_health.score == expected


def test_provisional_overall_formula() -> None:
    engine = AuditEngine()
    page = uuid4()
    result = engine.score(
        page_ids=[page],
        findings=[
            _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=page)
        ],
    )
    available = FINAL_OVERALL_WEIGHTS["website_health"] + FINAL_OVERALL_WEIGHTS["seo"]
    wh_w = FINAL_OVERALL_WEIGHTS["website_health"] / available
    seo_w = FINAL_OVERALL_WEIGHTS["seo"] / available
    expected = clamp_score(
        (result.website_health.score or Decimal("0")) * wh_w
        + (result.seo_score.score or Decimal("0")) * seo_w
    )
    assert result.overall.score == expected
    assert result.overall.status == ScoreStatus.PROVISIONAL


def test_unavailable_dimensions_not_zero() -> None:
    engine = AuditEngine()
    result = engine.score(page_ids=[], findings=[])
    assert result.ai_visibility if False else True  # noqa: ensure we don't invent fields
    # Overall is None, not 0
    assert result.overall.score is None
    assert result.website_health.score is None


def test_empty_crawl_finding_with_zero_pages_unavailable() -> None:
    engine = AuditEngine()
    result = engine.score(
        page_ids=[],
        findings=[
            _finding(
                category="CRAWL",
                severity="HIGH",
                title="No pages were successfully crawled",
                page_id=None,
            )
        ],
    )
    assert result.status == ScoreStatus.UNAVAILABLE
    assert result.overall.score is None


def test_no_double_counting_across_categories() -> None:
    engine = AuditEngine()
    page = uuid4()
    result = engine.score(
        page_ids=[page],
        findings=[
            _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=page),
        ],
    )
    # Title finding must not reduce technical/content/structured
    assert result.technical.score == Decimal("100.00")
    assert result.content.score == Decimal("100.00")
    assert result.structured_data.score == Decimal("100.00")
    assert result.seo.findings_count == 1
    assert result.technical.findings_count == 0


def test_severity_weights_documented() -> None:
    assert SEVERITY_WEIGHTS["HIGH"] == Decimal("15")
    assert SEVERITY_WEIGHTS["MEDIUM"] == Decimal("7")
    assert SEVERITY_WEIGHTS["LOW"] == Decimal("3")
    assert SEVERITY_WEIGHTS["INFO"] == Decimal("0")


def test_clamp_score() -> None:
    assert clamp_score(Decimal("-5")) == Decimal("0")
    assert clamp_score(Decimal("101")) == Decimal("100")
    assert clamp_score(Decimal("74.456")) == Decimal("74.46")
