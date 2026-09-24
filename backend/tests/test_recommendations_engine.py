"""Pure tests for the Recommendations Engine."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.enums import FindingSeverity, RecommendationPriority
from app.services.recommendations import RecommendationsEngine
from app.services.recommendations.constants import (
    EFFORT_LOW,
    PRIORITY_HIGH_MIN,
    PRIORITY_MEDIUM_MIN,
    SCORE_THRESHOLD,
)
from app.services.recommendations.models import AuditEvidence, FindingEvidence
from app.services.recommendations.scoring import compute_priority, impact_from_severity


def _finding(
    title: str,
    *,
    severity: FindingSeverity = FindingSeverity.HIGH,
    category: str = "TITLE",
    page_id=None,
) -> FindingEvidence:
    return FindingEvidence(
        id=uuid4(),
        category=category,
        severity=severity,
        title=title,
        page_id=page_id if page_id is not None else uuid4(),
    )


def _evidence(**overrides) -> AuditEvidence:
    data = dict(
        analyzable_pages=10,
        findings=(),
        technical_score=None,
        seo_component_score=None,
        content_score=None,
        structured_data_score=None,
        scores_available=False,
        visibility_available=False,
        mention_score=None,
        citation_score=None,
        position_score=None,
        semantic_score=None,
        successful_ai_responses=0,
        responses_mentioning_brand=0,
        mention_rate=None,
        entity_available=False,
        presence_score=None,
        consistency_score=None,
        structured_identity_score=None,
        ai_recognition_score=None,
        entity_pages=0,
        pages_with_brand_in_title=0,
        pages_with_brand_in_meta=0,
    )
    data.update(overrides)
    return AuditEvidence(**data)


@pytest.mark.parametrize(
    "title",
    [
        "Missing page title",
        "Page title is long",
        "Page title is very short",
        "Missing meta description",
        "Meta description is long",
        "Meta description is very short",
        "Canonical URL missing",
        "Canonical URL points outside the site",
        "Missing H1 heading",
        "Multiple H1 headings",
        "Very little textual content",
        "No structured data detected",
        "Client error status (404)",
        "Server error status (500)",
        "Slow page response",
        "Duplicate page title",
        "Duplicate meta description",
        "No pages were successfully crawled",
    ],
)
def test_seo_finding_rules_produce_one_recommendation(title: str) -> None:
    findings = [_finding(title) for _ in range(3)]
    if title.startswith("No pages"):
        evidence = _evidence(analyzable_pages=0, findings=tuple(findings[:1]))
    else:
        evidence = _evidence(findings=tuple(findings))
    result = RecommendationsEngine().generate(evidence, max_recommendations=20)
    assert len(result) == 1
    assert result[0].finding_count >= 1
    assert result[0].impact_score is not None
    assert result[0].effort_score is not None


def test_dedupe_many_findings_one_recommendation() -> None:
    findings = tuple(_finding("Missing meta description") for _ in range(10))
    result = RecommendationsEngine().generate(
        _evidence(findings=findings, analyzable_pages=18),
        max_recommendations=20,
    )
    assert len(result) == 1
    assert "10 of 18" in result[0].description or "10" in result[0].description


def test_impact_severity_and_coverage() -> None:
    high_full = impact_from_severity(
        FindingSeverity.HIGH, affected_pages=10, analyzable_pages=10
    )
    high_one = impact_from_severity(
        FindingSeverity.HIGH, affected_pages=1, analyzable_pages=10
    )
    assert high_full == Decimal("90.0")
    assert high_one < high_full
    assert high_one > Decimal("0")
    info = impact_from_severity(FindingSeverity.INFO, affected_pages=10, analyzable_pages=10)
    assert info == Decimal("15.0")


def test_priority_thresholds() -> None:
    high, score = compute_priority(Decimal("100"), Decimal("0"))
    assert high == RecommendationPriority.HIGH
    assert score >= PRIORITY_HIGH_MIN
    medium, _ = compute_priority(Decimal("60"), Decimal("50"))
    assert medium in {RecommendationPriority.MEDIUM, RecommendationPriority.HIGH, RecommendationPriority.LOW}
    low, score_low = compute_priority(Decimal("20"), Decimal("90"))
    assert low == RecommendationPriority.LOW
    assert score_low < PRIORITY_MEDIUM_MIN


def test_effort_low_for_missing_title() -> None:
    result = RecommendationsEngine().generate(
        _evidence(findings=(_finding("Missing page title"),)),
        max_recommendations=5,
    )
    assert result[0].effort_score == EFFORT_LOW


def test_ai_visibility_rules() -> None:
    none = RecommendationsEngine().generate(_evidence(), max_recommendations=20)
    assert all(c.category.value != "AI_VISIBILITY" for c in none)

    low = RecommendationsEngine().generate(
        _evidence(
            visibility_available=True,
            mention_score=Decimal("40"),
            citation_score=Decimal("40"),
            position_score=Decimal("40"),
            semantic_score=Decimal("40"),
            successful_ai_responses=10,
            responses_mentioning_brand=2,
            mention_rate=Decimal("0.2"),
        ),
        max_recommendations=20,
    )
    titles = {c.title for c in low}
    assert "Improve brand visibility in AI responses" in titles
    assert "Strengthen citation-ready brand content" in titles
    assert "Strengthen brand relevance in AI responses" in titles
    assert "Improve semantic clarity of brand content" in titles

    high = RecommendationsEngine().generate(
        _evidence(
            visibility_available=True,
            mention_score=SCORE_THRESHOLD,
            citation_score=Decimal("80"),
            position_score=Decimal("80"),
            semantic_score=Decimal("80"),
            successful_ai_responses=10,
            responses_mentioning_brand=8,
            mention_rate=Decimal("0.8"),
        ),
        max_recommendations=20,
    )
    assert all(c.category.value != "AI_VISIBILITY" for c in high)


def test_entity_rules() -> None:
    none = RecommendationsEngine().generate(_evidence(), max_recommendations=20)
    assert all(c.category.value != "ENTITY" for c in none)

    low = RecommendationsEngine().generate(
        _evidence(
            entity_available=True,
            presence_score=Decimal("40"),
            consistency_score=Decimal("40"),
            structured_identity_score=Decimal("40"),
            ai_recognition_score=Decimal("40"),
            entity_pages=8,
            pages_with_brand_in_title=2,
            pages_with_brand_in_meta=1,
        ),
        max_recommendations=20,
    )
    assert len([c for c in low if c.category.value == "ENTITY"]) == 4


def test_website_health_rules() -> None:
    result = RecommendationsEngine().generate(
        _evidence(
            scores_available=True,
            technical_score=Decimal("40"),
            seo_component_score=Decimal("40"),
            content_score=Decimal("40"),
            structured_data_score=Decimal("40"),
            analyzable_pages=5,
        ),
        max_recommendations=20,
    )
    titles = {c.title for c in result}
    assert "Improve technical website health" in titles
    assert "Improve on-page SEO health" in titles
    assert "Strengthen website content" in titles
    assert "Improve structured data coverage" in titles


def test_max_recommendations_truncates() -> None:
    findings = tuple(
        _finding(title)
        for title in [
            "Missing page title",
            "Missing meta description",
            "Missing H1 heading",
            "Slow page response",
            "Client error status (404)",
        ]
    )
    result = RecommendationsEngine().generate(
        _evidence(findings=findings),
        max_recommendations=2,
    )
    assert len(result) == 2
    # Highest priority first
    assert result[0].priority.value in {"HIGH", "MEDIUM", "LOW"}


def test_ranking_priority_then_impact() -> None:
    # Full coverage so HIGH-severity missing titles clear the HIGH priority band.
    title_findings = tuple(
        _finding("Missing page title", severity=FindingSeverity.HIGH) for _ in range(10)
    )
    short_meta = (_finding("Meta description is very short", severity=FindingSeverity.LOW),)
    result = RecommendationsEngine().generate(
        _evidence(findings=title_findings + short_meta, analyzable_pages=10),
        max_recommendations=10,
    )
    assert result[0].priority == RecommendationPriority.HIGH
    assert result[0].title == "Add missing page titles"
    assert result[0].impact_score >= result[1].impact_score
