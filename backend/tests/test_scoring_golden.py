"""Phase 20 — golden scoring regression (formulas must not drift)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from app.services.audit_engine import AuditEngine, FindingInput, ScoreStatus


def _finding(
    *,
    category: str,
    severity: str,
    title: str,
    page_id: UUID | None,
) -> FindingInput:
    return FindingInput(
        id=uuid4(),
        category=category,
        severity=severity,
        title=title,
        page_id=page_id,
    )


def test_golden_no_findings_scores_are_full() -> None:
    page = uuid4()
    result = AuditEngine().score(page_ids=[page], findings=[])
    assert result.status == ScoreStatus.PROVISIONAL
    assert result.website_health.score == Decimal("100.00")
    assert result.seo_score.score == Decimal("100.00")
    assert result.overall.score == Decimal("100.00")


def test_golden_one_high_finding_reduces_seo() -> None:
    page = uuid4()
    engine = AuditEngine()
    clean = engine.score(page_ids=[page], findings=[])
    penalized = engine.score(
        page_ids=[page],
        findings=[_finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=page)],
    )
    assert clean.seo_score.score == Decimal("100.00")
    assert penalized.seo_score.score is not None
    assert penalized.seo_score.score < clean.seo_score.score


def test_golden_duplicate_affected_pages_do_not_double_count_page_list() -> None:
    page = uuid4()
    result = AuditEngine().score(
        page_ids=[page],
        findings=[
            _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=page),
            _finding(category="META", severity="MEDIUM", title="Missing meta", page_id=page),
        ],
    )
    assert result.affected_pages == 1


def test_golden_scores_clamp_to_0_100() -> None:
    pages = [uuid4() for _ in range(12)]
    findings = [
        _finding(category="HTTP_ERROR", severity="HIGH", title="Server error", page_id=page)
        for page in pages
    ] + [
        _finding(category="TITLE", severity="HIGH", title="Missing page title", page_id=page)
        for page in pages
    ]
    result = AuditEngine().score(page_ids=pages, findings=findings)
    for score in (result.website_health.score, result.seo_score.score, result.overall.score):
        assert score is not None
        assert Decimal("0") <= score <= Decimal("100")


def test_golden_empty_crawl_is_unavailable_not_zero() -> None:
    result = AuditEngine().score(page_ids=[], findings=[])
    assert result.status == ScoreStatus.UNAVAILABLE
    assert result.website_health.score is None
    assert result.seo_score.score is None
    assert result.overall.score is None
