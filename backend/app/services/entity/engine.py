"""Entity Intelligence Engine — pure scoring over persisted page/AI snapshots."""

from __future__ import annotations

from app.services.entity.extraction import normalize_brand_name, origin_of
from app.services.entity.metrics import compute_entity_metrics
from app.services.entity.models import (
    AiResponseInput,
    EntityStrengthScore,
    PageInput,
)
from app.services.entity.scoring import assemble_result


class EntityIntelligenceEngine:
    """Deterministic entity scoring. No database or network access."""

    def score(
        self,
        *,
        brand_name: str,
        pages: list[PageInput],
        responses: list[AiResponseInput],
        website_url: str | None = None,
    ) -> EntityStrengthScore:
        normalized = normalize_brand_name(brand_name)
        site_origin = origin_of(website_url) if website_url else None
        if site_origin is None and pages:
            site_origin = origin_of(pages[0].url)
        metrics, evidence = compute_entity_metrics(
            brand_name=brand_name.strip(),
            normalized_brand=normalized,
            pages=pages,
            responses=responses,
            site_origin=site_origin,
        )
        return assemble_result(metrics=metrics, evidence=evidence)
