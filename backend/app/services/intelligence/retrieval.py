"""Ownership-scoped reads for Ask Intelligence.

The language model never receives a database session or SQL.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import case

from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.enums import AuditStatus
from app.models.recommendation import Recommendation
from app.models.website import SeoFinding, WebsitePage
from app.services.intelligence.models import OwnedAuditOption


class IntelligenceAuditNotFound(LookupError):
    """The requested audit is missing or not owned by the current user."""


def list_owned_audits(db: Session, owner_id: UUID) -> list[Audit]:
    """Completed audits first, then newest completion, then newest creation."""
    completed_rank = case((Audit.status == AuditStatus.COMPLETED, 0), else_=1)
    return list(
        db.scalars(
            select(Audit)
            .join(Brand, Brand.id == Audit.brand_id)
            .where(Brand.owner_id == owner_id)
            .options(selectinload(Audit.brand))
            .order_by(
                completed_rank.asc(),
                Audit.completed_at.desc().nulls_last(),
                Audit.created_at.desc(),
                Audit.id.desc(),
            )
        ).all()
    )


def get_owned_audit(db: Session, owner_id: UUID, audit_id: UUID) -> Audit | None:
    return db.scalars(
        select(Audit)
        .join(Brand, Brand.id == Audit.brand_id)
        .where(Brand.owner_id == owner_id, Audit.id == audit_id)
        .options(selectinload(Audit.brand))
    ).first()


def select_default_audit(audits: list[Audit]) -> Audit | None:
    """Latest completed owned audit, otherwise the newest owned audit."""
    if not audits:
        return None
    for audit in audits:
        if audit.status == AuditStatus.COMPLETED:
            return audit
    return audits[0]


def resolve_audit(
    db: Session,
    owner_id: UUID,
    audit_id: UUID | None,
) -> tuple[list[Audit], Audit | None]:
    """Return owned audits and the selected row.

    A foreign or unknown audit id raises IntelligenceAuditNotFound.
    No id selects the latest completed audit, else the latest audit, else none.
    """
    audits = list_owned_audits(db, owner_id)
    if audit_id is not None:
        audit = get_owned_audit(db, owner_id, audit_id)
        if audit is None:
            raise IntelligenceAuditNotFound
        return audits, audit
    return audits, select_default_audit(audits)


def to_audit_option(audit: Audit) -> OwnedAuditOption:
    brand = audit.brand
    status = audit.status.value if isinstance(audit.status, AuditStatus) else str(audit.status)
    return OwnedAuditOption(
        id=audit.id,
        brand_id=audit.brand_id,
        brand_name=brand.name if brand is not None else "",
        status=status,
        created_at=audit.created_at,
        completed_at=audit.completed_at,
    )


def load_pages(db: Session, audit_id: UUID) -> list[WebsitePage]:
    return list(
        db.scalars(
            select(WebsitePage)
            .where(WebsitePage.audit_id == audit_id)
            .order_by(WebsitePage.created_at.asc(), WebsitePage.id.asc())
        ).all()
    )


def load_findings(db: Session, audit_id: UUID) -> list[SeoFinding]:
    return list(
        db.scalars(
            select(SeoFinding)
            .where(SeoFinding.audit_id == audit_id)
            .order_by(SeoFinding.created_at.asc(), SeoFinding.id.asc())
        ).all()
    )


def load_queries(db: Session, audit_id: UUID) -> list[AiQuery]:
    return list(
        db.scalars(
            select(AiQuery)
            .where(AiQuery.audit_id == audit_id)
            .options(selectinload(AiQuery.responses))
            .order_by(AiQuery.created_at.asc(), AiQuery.id.asc())
        ).all()
    )


def load_recommendations(db: Session, audit_id: UUID) -> list[Recommendation]:
    from app.services.recommendation_service import list_recommendations

    return list_recommendations(db, audit_id)


def first_response(query: AiQuery) -> AiResponse | None:
    if not query.responses:
        return None

    def sort_key(row: AiResponse) -> tuple:
        created = row.created_at.isoformat() if row.created_at is not None else ""
        return (created, str(row.id))

    return sorted(query.responses, key=sort_key)[0]
