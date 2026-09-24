"""Penalty helpers: rule resolution, category mapping, and contribution math."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.services.audit_engine.models import FindingInput, PenaltyContribution
from app.services.audit_engine.weights import (
    FINDING_CATEGORY_TO_COMPONENT,
    FINDING_TITLE_TO_RULE,
    MAX_CATEGORY_PENALTY,
    RULE_WEIGHTS,
    SEVERITY_WEIGHTS,
)


def resolve_component(category: str) -> str | None:
    return FINDING_CATEGORY_TO_COMPONENT.get(category)


def resolve_rule_id(finding: FindingInput) -> str:
    """Map a finding to a stable rule id for weighting."""
    if finding.category == "STATUS":
        if finding.severity == "HIGH" or finding.title.startswith("Server error"):
            return "status_5xx"
        return "status_4xx"
    return FINDING_TITLE_TO_RULE.get(finding.title, "unknown")


def severity_weight(severity: str) -> Decimal:
    return SEVERITY_WEIGHTS.get(severity, Decimal("0"))


def rule_weight(rule_id: str) -> Decimal:
    return RULE_WEIGHTS.get(rule_id, RULE_WEIGHTS["unknown"])


def build_penalties(
    findings: list[FindingInput],
    analyzable_pages: int,
) -> list[PenaltyContribution]:
    """Build per-rule penalty contributions for an audit.

    Page-level findings:
        affected_page_rate = distinct_affected_pages / analyzable_pages

    Audit-level findings (page_id is None):
        treated as rate = 1.0 (full-audit impact)

    Distinct page IDs are used once per rule. Multiple findings of the same
    rule on one page do not inflate the affected-page count.
    """
    if analyzable_pages < 1:
        return []

    # rule_id → aggregated pages / findings / representative severity+category
    groups: dict[str, dict] = {}
    for finding in findings:
        component = resolve_component(finding.category)
        if component is None:
            continue
        rule_id = resolve_rule_id(finding)
        bucket = groups.setdefault(
            rule_id,
            {
                "category": finding.category,
                "component": component,
                "severity": finding.severity,
                "page_ids": set(),
                "finding_ids": [],
                "audit_level": False,
            },
        )
        # Prefer highest severity if mixed (should not happen for same rule)
        if _severity_rank(finding.severity) > _severity_rank(bucket["severity"]):
            bucket["severity"] = finding.severity
            bucket["category"] = finding.category
        bucket["finding_ids"].append(finding.id)
        if finding.page_id is None:
            bucket["audit_level"] = True
        else:
            bucket["page_ids"].add(finding.page_id)

    contributions: list[PenaltyContribution] = []
    pages_decimal = Decimal(analyzable_pages)

    for rule_id, bucket in sorted(groups.items(), key=lambda item: item[0]):
        if bucket["audit_level"] and not bucket["page_ids"]:
            affected = analyzable_pages
            rate = Decimal("1")
            page_ids: tuple[UUID, ...] = ()
        else:
            page_ids = tuple(sorted(bucket["page_ids"], key=str))
            affected = len(page_ids)
            rate = (Decimal(affected) / pages_decimal).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

        sev_w = severity_weight(bucket["severity"])
        r_w = rule_weight(rule_id)
        points = (sev_w * rate * r_w).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        contributions.append(
            PenaltyContribution(
                rule_id=rule_id,
                category=bucket["category"],
                component=bucket["component"],
                severity=bucket["severity"],
                severity_weight=sev_w,
                rule_weight=r_w,
                affected_pages=affected if not (bucket["audit_level"] and not bucket["page_ids"]) else 0,
                analyzable_pages=analyzable_pages,
                affected_page_rate=rate,
                penalty_points=points,
                finding_ids=tuple(bucket["finding_ids"]),
                page_ids=page_ids,
            )
        )
    return contributions


def score_from_penalties(penalties: list[PenaltyContribution]) -> Decimal:
    """Convert summed penalty points into a 0–100 score."""
    total = sum((item.penalty_points for item in penalties), Decimal("0"))
    capped = min(MAX_CATEGORY_PENALTY, total)
    raw = Decimal("100") - capped
    return clamp_score(raw)


def clamp_score(value: Decimal) -> Decimal:
    if value < 0:
        return Decimal("0")
    if value > 100:
        return Decimal("100")
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def group_penalties_by_component(
    penalties: list[PenaltyContribution],
) -> dict[str, list[PenaltyContribution]]:
    grouped: dict[str, list[PenaltyContribution]] = defaultdict(list)
    for item in penalties:
        grouped[item.component].append(item)
    return grouped


def _severity_rank(severity: str) -> int:
    order = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    return order.get(severity, 0)
