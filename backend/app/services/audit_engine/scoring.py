"""Pure score calculation from page counts and findings."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.services.audit_engine.models import (
    AuditScoreResult,
    ComponentScore,
    DimensionScore,
    FindingInput,
    ScoreStatus,
)
from app.services.audit_engine.penalties import (
    build_penalties,
    clamp_score,
    group_penalties_by_component,
    score_from_penalties,
)
from app.services.audit_engine.weights import (
    FINAL_OVERALL_WEIGHTS,
    PROVISIONAL_OVERALL_AVAILABLE,
    WEBSITE_HEALTH_WEIGHTS,
)


class ScoreCalculator:
    """Deterministic score calculator. Identical inputs → identical outputs."""

    def calculate(
        self,
        *,
        analyzable_pages: int,
        findings: list[FindingInput],
    ) -> AuditScoreResult:
        if analyzable_pages < 1:
            return self._unavailable(findings_count=len(findings))

        penalties = build_penalties(findings, analyzable_pages)
        by_component = group_penalties_by_component(penalties)

        technical = self._component("technical", by_component.get("technical", []), findings)
        seo = self._component("seo", by_component.get("seo", []), findings)
        content = self._component("content", by_component.get("content", []), findings)
        structured = self._component(
            "structured_data", by_component.get("structured_data", []), findings
        )

        website_health_value = clamp_score(
            (technical.score or Decimal("0")) * WEBSITE_HEALTH_WEIGHTS["technical"]
            + (seo.score or Decimal("0")) * WEBSITE_HEALTH_WEIGHTS["seo"]
            + (content.score or Decimal("0")) * WEBSITE_HEALTH_WEIGHTS["content"]
            + (structured.score or Decimal("0")) * WEBSITE_HEALTH_WEIGHTS["structured_data"]
        )
        seo_value = seo.score if seo.score is not None else Decimal("100")

        overall_value = self._provisional_overall(website_health_value, seo_value)

        affected = _distinct_affected_pages(findings)

        return AuditScoreResult(
            technical=technical,
            seo=seo,
            content=content,
            structured_data=structured,
            website_health=DimensionScore(score=website_health_value, status=ScoreStatus.AVAILABLE),
            seo_score=DimensionScore(score=seo_value, status=ScoreStatus.AVAILABLE),
            overall=DimensionScore(score=overall_value, status=ScoreStatus.PROVISIONAL),
            analyzable_pages=analyzable_pages,
            findings_count=len(findings),
            affected_pages=affected,
            status=ScoreStatus.PROVISIONAL,
        )

    def _component(
        self,
        name: str,
        penalties: list,
        findings: list[FindingInput],
    ) -> ComponentScore:
        score = score_from_penalties(penalties)
        component_findings = [
            f for f in findings if _finding_component(f.category) == name
        ]
        pages = {
            f.page_id for f in component_findings if f.page_id is not None
        }
        return ComponentScore(
            name=name,
            score=score,
            status=ScoreStatus.AVAILABLE,
            findings_count=len(component_findings),
            affected_pages=len(pages),
            penalties=tuple(penalties),
        )

    def _provisional_overall(self, website_health: Decimal, seo: Decimal) -> Decimal:
        """Renormalize Website Health + SEO over available final weights.

        Final design: WH 25% + SEO 20% + AI 35% + Entity 20%.
        Phase 09 available sum = 25 + 20 = 45.
        Provisional:
            WH * (25/45) + SEO * (20/45)
        """
        available_sum = sum(
            FINAL_OVERALL_WEIGHTS[key] for key in PROVISIONAL_OVERALL_AVAILABLE
        )
        wh_w = FINAL_OVERALL_WEIGHTS["website_health"] / available_sum
        seo_w = FINAL_OVERALL_WEIGHTS["seo"] / available_sum
        raw = website_health * wh_w + seo * seo_w
        return clamp_score(raw)

    def _unavailable(self, *, findings_count: int) -> AuditScoreResult:
        empty = ComponentScore(
            name="technical",
            score=None,
            status=ScoreStatus.UNAVAILABLE,
            findings_count=0,
            affected_pages=0,
        )
        return AuditScoreResult(
            technical=empty,
            seo=ComponentScore(
                name="seo", score=None, status=ScoreStatus.UNAVAILABLE
            ),
            content=ComponentScore(
                name="content", score=None, status=ScoreStatus.UNAVAILABLE
            ),
            structured_data=ComponentScore(
                name="structured_data", score=None, status=ScoreStatus.UNAVAILABLE
            ),
            website_health=DimensionScore(score=None, status=ScoreStatus.UNAVAILABLE),
            seo_score=DimensionScore(score=None, status=ScoreStatus.UNAVAILABLE),
            overall=DimensionScore(score=None, status=ScoreStatus.UNAVAILABLE),
            analyzable_pages=0,
            findings_count=findings_count,
            affected_pages=0,
            status=ScoreStatus.UNAVAILABLE,
        )


def _finding_component(category: str) -> str | None:
    from app.services.audit_engine.weights import FINDING_CATEGORY_TO_COMPONENT

    return FINDING_CATEGORY_TO_COMPONENT.get(category)


def _distinct_affected_pages(findings: list[FindingInput]) -> int:
    return len({f.page_id for f in findings if f.page_id is not None})


def quantize_score(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
