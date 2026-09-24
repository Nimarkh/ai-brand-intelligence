"""Deterministic recommendation rules evaluated against audit evidence."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.models.enums import FindingSeverity
from app.services.recommendations.categories import RecommendationCategory, RecommendationSource
from app.services.recommendations.constants import (
    COMPONENT_HEALTH_THRESHOLD,
    EFFORT_HIGH,
    EFFORT_LOW,
    EFFORT_LOW_MED,
    EFFORT_MEDIUM,
    EFFORT_MEDIUM_HIGH,
    EFFORT_VERY_HIGH,
    SCORE_THRESHOLD,
)
from app.services.recommendations.models import (
    AuditEvidence,
    FindingEvidence,
    RecommendationCandidate,
)
from app.services.recommendations.scoring import compute_priority, fixed_impact, impact_from_severity

# SEO finding title → rule definition
# (rule_key, rec_category, title, effort, noun)
_SEO_TITLE_RULES: dict[str, tuple[str, RecommendationCategory, str, Decimal, str]] = {
    "Missing page title": (
        "seo_missing_title",
        RecommendationCategory.SEO,
        "Add missing page titles",
        EFFORT_LOW,
        "page",
    ),
    "Page title is long": (
        "seo_long_title",
        RecommendationCategory.SEO,
        "Shorten overly long page titles",
        EFFORT_LOW_MED,
        "page",
    ),
    "Page title is very short": (
        "seo_short_title",
        RecommendationCategory.SEO,
        "Strengthen short page titles",
        EFFORT_LOW,
        "page",
    ),
    "Missing meta description": (
        "seo_missing_meta",
        RecommendationCategory.SEO,
        "Add missing meta descriptions",
        EFFORT_LOW,
        "page",
    ),
    "Meta description is long": (
        "seo_long_meta",
        RecommendationCategory.SEO,
        "Shorten overly long meta descriptions",
        EFFORT_LOW_MED,
        "page",
    ),
    "Meta description is very short": (
        "seo_short_meta",
        RecommendationCategory.SEO,
        "Expand thin meta descriptions",
        EFFORT_LOW,
        "page",
    ),
    "Canonical URL missing": (
        "seo_missing_canonical",
        RecommendationCategory.SEO,
        "Add canonical URLs",
        EFFORT_MEDIUM,
        "page",
    ),
    "Canonical URL points outside the site": (
        "seo_external_canonical",
        RecommendationCategory.SEO,
        "Correct canonical URLs",
        EFFORT_MEDIUM,
        "page",
    ),
    "Missing H1 heading": (
        "seo_missing_h1",
        RecommendationCategory.CONTENT,
        "Add a primary H1 heading",
        EFFORT_LOW,
        "page",
    ),
    "Multiple H1 headings": (
        "seo_multiple_h1",
        RecommendationCategory.CONTENT,
        "Simplify multiple H1 headings",
        EFFORT_MEDIUM,
        "page",
    ),
    "Very little textual content": (
        "seo_low_word_count",
        RecommendationCategory.CONTENT,
        "Expand thin page content",
        EFFORT_MEDIUM_HIGH,
        "page",
    ),
    "No structured data detected": (
        "seo_missing_schema",
        RecommendationCategory.STRUCTURED_DATA,
        "Add relevant structured data",
        EFFORT_MEDIUM,
        "page",
    ),
    "Slow page response": (
        "seo_slow_response",
        RecommendationCategory.PERFORMANCE,
        "Improve page response performance",
        EFFORT_HIGH,
        "page",
    ),
    "Duplicate page title": (
        "seo_duplicate_title",
        RecommendationCategory.SEO,
        "Resolve duplicate page titles",
        EFFORT_LOW_MED,
        "page",
    ),
    "Duplicate meta description": (
        "seo_duplicate_meta",
        RecommendationCategory.SEO,
        "Resolve duplicate meta descriptions",
        EFFORT_LOW_MED,
        "page",
    ),
    "No pages were successfully crawled": (
        "seo_empty_crawl",
        RecommendationCategory.TECHNICAL,
        "Run a successful website crawl",
        EFFORT_LOW,
        "audit",
    ),
}


def evaluate_all_rules(evidence: AuditEvidence) -> list[RecommendationCandidate]:
    """Evaluate SEO, website-health, AI visibility, and entity rules."""
    candidates: list[RecommendationCandidate] = []
    candidates.extend(_seo_finding_rules(evidence))
    candidates.extend(_website_health_rules(evidence))
    candidates.extend(_ai_visibility_rules(evidence))
    candidates.extend(_entity_rules(evidence))
    return _dedupe_by_rule_key(candidates)


def _seo_finding_rules(evidence: AuditEvidence) -> list[RecommendationCandidate]:
    groups: dict[str, list[FindingEvidence]] = defaultdict(list)
    for finding in evidence.findings:
        key = _match_seo_rule_key(finding)
        if key is None:
            continue
        groups[key].append(finding)

    results: list[RecommendationCandidate] = []
    for rule_key, findings in groups.items():
        meta = _SEO_TITLE_RULES.get(findings[0].title) or _lookup_by_rule_key(rule_key)
        if meta is None:
            continue
        _rk, category, title, effort, noun = meta
        pages = {f.page_id for f in findings if f.page_id is not None}
        affected = len(pages) if pages else (1 if noun == "audit" else len(findings))
        # Worst severity drives base impact
        severity = max((f.severity for f in findings), key=_severity_rank)
        impact = impact_from_severity(
            severity,
            affected_pages=affected,
            analyzable_pages=max(evidence.analyzable_pages, 1 if noun == "audit" else 0),
        )
        if noun == "audit":
            impact = impact_from_severity(
                FindingSeverity.HIGH,
                affected_pages=1,
                analyzable_pages=1,
            )
            evidence_text = (
                "This audit has no crawled WebsitePage records. "
                "Run a successful website crawl before analyzing SEO findings."
            )
        else:
            page_noun = "page" if affected == 1 else "pages"
            finding_noun = "finding" if len(findings) == 1 else "findings"
            if evidence.analyzable_pages > 0:
                evidence_text = (
                    f"{affected} of {evidence.analyzable_pages} analyzed {page_noun} "
                    f"triggered this issue ({len(findings)} {finding_noun})."
                )
            else:
                evidence_text = f"{len(findings)} {finding_noun} were recorded for this issue."

        action = _action_hint(rule_key)
        description = f"{evidence_text} {action}"
        priority, priority_score = compute_priority(impact, effort)
        results.append(
            RecommendationCandidate(
                rule_key=rule_key,
                source=RecommendationSource.SEO_FINDING,
                category=category,
                title=title,
                description=description,
                impact_score=impact,
                effort_score=effort,
                priority=priority,
                priority_score=priority_score,
                affected_pages=affected,
                finding_count=len(findings),
            )
        )
    return results


def _match_seo_rule_key(finding: FindingEvidence) -> str | None:
    if finding.title in _SEO_TITLE_RULES:
        return _SEO_TITLE_RULES[finding.title][0]
    if finding.title.startswith("Server error status"):
        return "seo_5xx"
    if finding.title.startswith("Client error status"):
        return "seo_4xx"
    return None


def _lookup_by_rule_key(
    rule_key: str,
) -> tuple[str, RecommendationCategory, str, Decimal, str] | None:
    for title, meta in _SEO_TITLE_RULES.items():
        if meta[0] == rule_key:
            return meta
    if rule_key == "seo_5xx":
        return (
            "seo_5xx",
            RecommendationCategory.TECHNICAL,
            "Resolve server errors",
            EFFORT_VERY_HIGH,
            "page",
        )
    if rule_key == "seo_4xx":
        return (
            "seo_4xx",
            RecommendationCategory.TECHNICAL,
            "Fix broken pages",
            EFFORT_HIGH,
            "page",
        )
    return None


def _action_hint(rule_key: str) -> str:
    hints = {
        "seo_missing_title": "Add a unique, descriptive HTML title to each affected page.",
        "seo_long_title": "Shorten titles while keeping them descriptive.",
        "seo_short_title": "Expand titles so they clearly describe each page.",
        "seo_missing_meta": "Add unique meta descriptions that accurately summarize each page.",
        "seo_long_meta": "Shorten meta descriptions while keeping the main message.",
        "seo_short_meta": "Expand thin meta descriptions with clearer page summaries.",
        "seo_missing_canonical": "Add canonical URLs where appropriate.",
        "seo_external_canonical": "Point canonical URLs at the intended on-site pages.",
        "seo_missing_h1": "Add a single clear H1 that describes the main topic of each page.",
        "seo_multiple_h1": "Prefer a single primary H1 and review heading structure.",
        "seo_low_word_count": "Review whether each page needs more meaningful textual content.",
        "seo_missing_schema": "Add relevant structured data where it helps machines understand the page.",
        "seo_slow_response": "Investigate server response time and page weight for affected URLs.",
        "seo_duplicate_title": "Give each important page a unique, descriptive title.",
        "seo_duplicate_meta": "Write a unique meta description for each important page.",
        "seo_empty_crawl": "Configure the brand website URL and run a successful crawl.",
        "seo_4xx": "Investigate client error responses and restore successful pages where intended.",
        "seo_5xx": "Investigate server errors and restore successful page responses.",
    }
    return hints.get(rule_key, "Address the underlying findings based on analyzed evidence.")


def _website_health_rules(evidence: AuditEvidence) -> list[RecommendationCandidate]:
    if not evidence.scores_available:
        return []
    results: list[RecommendationCandidate] = []
    specs = [
        (
            "health_technical",
            evidence.technical_score,
            RecommendationCategory.TECHNICAL,
            "Improve technical website health",
            EFFORT_HIGH,
            "Technical website health is below the recommended threshold.",
        ),
        (
            "health_seo",
            evidence.seo_component_score,
            RecommendationCategory.SEO,
            "Improve on-page SEO health",
            EFFORT_MEDIUM,
            "On-page SEO health is below the recommended threshold.",
        ),
        (
            "health_content",
            evidence.content_score,
            RecommendationCategory.CONTENT,
            "Strengthen website content",
            EFFORT_MEDIUM_HIGH,
            "Content health is below the recommended threshold.",
        ),
        (
            "health_structured",
            evidence.structured_data_score,
            RecommendationCategory.STRUCTURED_DATA,
            "Improve structured data coverage",
            EFFORT_MEDIUM,
            "Structured data health is below the recommended threshold.",
        ),
    ]
    for rule_key, score, category, title, effort, lead in specs:
        if score is None or score >= COMPONENT_HEALTH_THRESHOLD:
            continue
        # Skip structured health if no related findings/pages evidence
        if rule_key == "health_structured" and evidence.analyzable_pages < 1:
            continue
        impact = fixed_impact(Decimal("100") - score)
        priority, priority_score = compute_priority(impact, effort)
        description = (
            f"{lead} Component score: {score}/100 "
            f"(threshold {COMPONENT_HEALTH_THRESHOLD}). "
            "This is a high-level signal based on analyzed audit evidence."
        )
        results.append(
            RecommendationCandidate(
                rule_key=rule_key,
                source=RecommendationSource.WEBSITE_SCORE,
                category=category,
                title=title,
                description=description,
                impact_score=impact,
                effort_score=effort,
                priority=priority,
                priority_score=priority_score,
            )
        )
    return results


def _ai_visibility_rules(evidence: AuditEvidence) -> list[RecommendationCandidate]:
    if not evidence.visibility_available:
        return []
    results: list[RecommendationCandidate] = []
    specs = [
        (
            "ai_low_mention",
            evidence.mention_score,
            "Improve brand visibility in AI responses",
            EFFORT_MEDIUM_HIGH,
            (
                f"{evidence.responses_mentioning_brand} of {evidence.successful_ai_responses} "
                f"successful AI responses mentioned the brand"
                + (
                    f" (mention rate {evidence.mention_rate})."
                    if evidence.mention_rate is not None
                    else "."
                )
                + " Strengthen clear brand naming and positioning in public content."
            ),
        ),
        (
            "ai_low_citation",
            evidence.citation_score,
            "Strengthen citation-ready brand content",
            EFFORT_MEDIUM_HIGH,
            (
                "Citation-like references were infrequently detected in AI responses "
                f"(citation score {evidence.citation_score}/100). "
                "Improve the availability and clarity of authoritative brand information. "
                "Citations cannot be directly controlled."
            ),
        ),
        (
            "ai_weak_position",
            evidence.position_score,
            "Strengthen brand relevance in AI responses",
            EFFORT_MEDIUM,
            (
                f"Average response mention-position score is {evidence.position_score}/100. "
                "This reflects where the brand appears inside AI answers, not search ranking. "
                "Clarify brand relevance in content that answers common queries."
            ),
        ),
        (
            "ai_weak_semantic",
            evidence.semantic_score,
            "Improve semantic clarity of brand content",
            EFFORT_MEDIUM,
            (
                f"Lexical semantic match score is {evidence.semantic_score}/100. "
                "This measures token overlap between analyzed queries and responses, "
                "not model-level semantic optimization."
            ),
        ),
    ]
    for rule_key, score, title, effort, description in specs:
        if score is None or score >= SCORE_THRESHOLD:
            continue
        impact = fixed_impact(Decimal("100") - score)
        priority, priority_score = compute_priority(impact, effort)
        results.append(
            RecommendationCandidate(
                rule_key=rule_key,
                source=RecommendationSource.AI_VISIBILITY,
                category=RecommendationCategory.AI_VISIBILITY,
                title=title,
                description=description,
                impact_score=impact,
                effort_score=effort,
                priority=priority,
                priority_score=priority_score,
            )
        )
    return results


def _entity_rules(evidence: AuditEvidence) -> list[RecommendationCandidate]:
    if not evidence.entity_available:
        return []
    results: list[RecommendationCandidate] = []
    specs = [
        (
            "entity_low_presence",
            evidence.presence_score,
            "Strengthen consistent brand identification",
            EFFORT_MEDIUM,
            (
                f"{evidence.pages_with_brand_in_title} of {evidence.entity_pages} analyzed pages "
                f"include the brand in the title; "
                f"{evidence.pages_with_brand_in_meta} include it in the meta description. "
                "This does not verify external entity databases."
            ),
        ),
        (
            "entity_low_consistency",
            evidence.consistency_score,
            "Improve brand consistency across pages",
            EFFORT_MEDIUM,
            (
                f"Entity consistency score is {evidence.consistency_score}/100 across "
                f"{evidence.entity_pages} analyzed pages. Align titles, canonicals, and schema usage."
            ),
        ),
        (
            "entity_weak_structured",
            evidence.structured_identity_score,
            "Strengthen organization structured data",
            EFFORT_MEDIUM,
            (
                f"Structured identity score is {evidence.structured_identity_score}/100. "
                "Add or improve Organization/Brand structured data on key pages."
            ),
        ),
        (
            "entity_weak_ai",
            evidence.ai_recognition_score,
            "Improve clarity of brand identity in content",
            EFFORT_MEDIUM,
            (
                f"AI entity recognition score is {evidence.ai_recognition_score}/100. "
                "Clarify brand naming so AI responses more consistently recognize the brand. "
                "This is not Knowledge Graph verification."
            ),
        ),
    ]
    for rule_key, score, title, effort, description in specs:
        if score is None or score >= SCORE_THRESHOLD:
            continue
        impact = fixed_impact(Decimal("100") - score)
        priority, priority_score = compute_priority(impact, effort)
        results.append(
            RecommendationCandidate(
                rule_key=rule_key,
                source=RecommendationSource.ENTITY_INTELLIGENCE,
                category=RecommendationCategory.ENTITY,
                title=title,
                description=description,
                impact_score=impact,
                effort_score=effort,
                priority=priority,
                priority_score=priority_score,
            )
        )
    return results


def _dedupe_by_rule_key(
    candidates: list[RecommendationCandidate],
) -> list[RecommendationCandidate]:
    by_key: dict[str, RecommendationCandidate] = {}
    for item in candidates:
        existing = by_key.get(item.rule_key)
        if existing is None or item.priority_score > existing.priority_score:
            by_key[item.rule_key] = item
    return list(by_key.values())


def _severity_rank(severity: FindingSeverity) -> int:
    order = {
        FindingSeverity.INFO: 0,
        FindingSeverity.LOW: 1,
        FindingSeverity.MEDIUM: 2,
        FindingSeverity.HIGH: 3,
    }
    return order[severity]
