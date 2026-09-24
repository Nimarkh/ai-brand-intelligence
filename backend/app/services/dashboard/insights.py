"""Deterministic key insights from persisted dashboard snapshot data.

No LLM. Insights are factual and traceable to stored metrics.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.dashboard.models import InsightItem, InsightSource, SnapshotMetrics

MAX_INSIGHTS = 4
MIN_INSIGHTS = 0


def build_insights(snapshot: SnapshotMetrics) -> tuple[InsightItem, ...]:
    """Generate up to four concise insights from snapshot counts.

    Order is fixed so results stay deterministic for the same input.
    """
    items: list[InsightItem] = []

    mentions = snapshot.ai_mentions
    successful = snapshot.ai_successful_responses
    if (
        mentions is not None
        and successful is not None
        and successful > 0
    ):
        items.append(
            InsightItem(
                text=(
                    f"{mentions} of {successful} analyzed AI responses "
                    f"mentioned the brand."
                ),
                source=InsightSource.AI_VISIBILITY,
            )
        )

    high = snapshot.high_severity_findings
    seo_total = snapshot.seo_findings
    if high is not None and high > 0:
        items.append(
            InsightItem(
                text=(
                    f"{high} high-severity SEO "
                    f"{'finding' if high == 1 else 'findings'} "
                    f"{'affects' if high == 1 else 'affect'} the site."
                ),
                source=InsightSource.SEO_FINDINGS,
            )
        )
    elif seo_total is not None and seo_total > 0:
        items.append(
            InsightItem(
                text=f"{seo_total} SEO findings were recorded for the latest audit.",
                source=InsightSource.SEO_FINDINGS,
            )
        )

    pages = snapshot.entity_pages_analyzed or snapshot.pages_crawled
    with_schema = snapshot.pages_with_schema
    if pages is not None and pages > 0 and with_schema is not None:
        items.append(
            InsightItem(
                text=(
                    f"Structured identity signals are present on "
                    f"{with_schema} of {pages} crawled pages."
                ),
                source=InsightSource.ENTITY,
            )
        )

    rec_high = snapshot.recommendations_high
    rec_total = snapshot.recommendations_total
    if rec_high is not None and rec_high > 0:
        items.append(
            InsightItem(
                text=(
                    f"{rec_high} high-priority "
                    f"{'recommendation is' if rec_high == 1 else 'recommendations are'} "
                    f"available."
                ),
                source=InsightSource.RECOMMENDATIONS,
            )
        )
    elif rec_total is not None and rec_total > 0:
        items.append(
            InsightItem(
                text=f"{rec_total} recommendations are available.",
                source=InsightSource.RECOMMENDATIONS,
            )
        )

    pages_crawled = snapshot.pages_crawled
    if (
        len(items) < 2
        and pages_crawled is not None
        and pages_crawled > 0
        and not any(item.source == InsightSource.WEBSITE for item in items)
    ):
        items.append(
            InsightItem(
                text=f"{pages_crawled} pages were crawled in the latest audit.",
                source=InsightSource.WEBSITE,
            )
        )

    coverage = snapshot.ai_response_coverage
    if (
        len(items) < 2
        and coverage is not None
        and snapshot.ai_queries is not None
        and snapshot.ai_queries > 0
        and not any(item.source == InsightSource.AI_VISIBILITY for item in items)
    ):
        pct = int((coverage * Decimal("100")).quantize(Decimal("1")))
        items.append(
            InsightItem(
                text=(
                    f"AI response coverage is {pct}% "
                    f"({snapshot.ai_successful_responses or 0} of {snapshot.ai_queries} queries)."
                ),
                source=InsightSource.AI_VISIBILITY,
            )
        )

    return tuple(items[:MAX_INSIGHTS])
