"""Read-only inspection of persisted AI queries and responses.

Does not execute queries, call providers, or recalculate Phase 09/12/13/14 scores.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import case

from app.models.ai import AiQuery, AiResponse
from app.models.audit import Audit
from app.models.brand import Brand
from app.models.enums import AiQueryCategory, AuditStatus
from app.models.user import User
from app.services.query_explorer.models import (
    ExplorerAudit,
    ExplorerItem,
    ExplorerPagination,
    ExplorerResponse,
    ExplorerResult,
    ExplorerSummary,
)

SEARCH_MAX_LENGTH = 200


class QueryExplorerAuditNotFound(LookupError):
    """The requested audit is missing or not owned by the current user."""


def get_query_explorer(
    current_user: User,
    db: Session,
    *,
    audit_id: UUID | None = None,
    category: AiQueryCategory | None = None,
    search: str | None = None,
    has_response: bool | None = None,
    brand_mentioned: bool | None = None,
    citation_found: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ExplorerResult:
    """Return one owned audit's queries, filtered and paginated in the database."""
    owner_id = current_user.id
    audits = _owned_audits(db, owner_id)
    audit_options = tuple(_to_audit(row) for row in audits)

    if audit_id is not None:
        audit = _owned_audit(db, owner_id, audit_id)
        if audit is None:
            raise QueryExplorerAuditNotFound
    else:
        audit = _select_latest_audit(audits)

    pagination = ExplorerPagination(
        page=page,
        page_size=page_size,
        total=0,
        pages=0,
    )
    if audit is None:
        return ExplorerResult(
            audit=None,
            audits=audit_options,
            summary=None,
            items=(),
            pagination=pagination,
        )

    summary = _summary(db, audit.id)
    criteria = _criteria(
        audit.id,
        category=category,
        search=search,
        has_response=has_response,
        brand_mentioned=brand_mentioned,
        citation_found=citation_found,
    )
    total = int(
        db.scalar(select(func.count()).select_from(AiQuery).where(*criteria)) or 0
    )
    pages = 0 if total == 0 else (total + page_size - 1) // page_size
    offset = (page - 1) * page_size
    items = _page_items(db, criteria, limit=page_size, offset=offset)

    return ExplorerResult(
        audit=_to_audit(audit),
        audits=audit_options,
        summary=summary,
        items=tuple(items),
        pagination=ExplorerPagination(
            page=page,
            page_size=page_size,
            total=total,
            pages=pages,
        ),
    )


def _owned_audits(db: Session, owner_id: UUID) -> list[Audit]:
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


def _owned_audit(db: Session, owner_id: UUID, audit_id: UUID) -> Audit | None:
    return db.scalars(
        select(Audit)
        .join(Brand, Brand.id == Audit.brand_id)
        .where(Brand.owner_id == owner_id, Audit.id == audit_id)
        .options(selectinload(Audit.brand))
    ).first()


def _select_latest_audit(audits: list[Audit]) -> Audit | None:
    """Latest completed owned audit, otherwise the newest owned audit.

    ``audits`` is already ordered completed-first, then newest completion,
    then newest creation.
    """
    if not audits:
        return None
    for audit in audits:
        if audit.status == AuditStatus.COMPLETED:
            return audit
    return audits[0]


def _summary(db: Session, audit_id: UUID) -> ExplorerSummary:
    total_queries = int(
        db.scalar(
            select(func.count()).select_from(AiQuery).where(AiQuery.audit_id == audit_id)
        )
        or 0
    )
    responses, mentioned, cited = db.execute(
        select(
            func.count(AiResponse.id),
            func.coalesce(
                func.sum(case((AiResponse.brand_mentioned.is_(True), 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((AiResponse.citation_found.is_(True), 1), else_=0)),
                0,
            ),
        )
        .select_from(AiResponse)
        .join(AiQuery, AiQuery.id == AiResponse.query_id)
        .where(AiQuery.audit_id == audit_id)
    ).one()
    response_count = int(responses or 0)
    mention_rate = None
    citation_rate = None
    if response_count > 0:
        mention_rate = _rate(int(mentioned or 0), response_count)
        citation_rate = _rate(int(cited or 0), response_count)
    return ExplorerSummary(
        total_queries=total_queries,
        responses=response_count,
        failed=total_queries - response_count,
        mention_rate=mention_rate,
        citation_rate=citation_rate,
    )


def _criteria(
    audit_id: UUID,
    *,
    category: AiQueryCategory | None,
    search: str | None,
    has_response: bool | None,
    brand_mentioned: bool | None,
    citation_found: bool | None,
) -> list:
    criteria: list = [AiQuery.audit_id == audit_id]
    if category is not None:
        criteria.append(AiQuery.category == category)

    term = (search or "").strip()
    if term:
        if len(term) > SEARCH_MAX_LENGTH:
            term = term[:SEARCH_MAX_LENGTH]
        escaped = (
            term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        criteria.append(AiQuery.query_text.ilike(f"%{escaped}%", escape="\\"))

    if has_response is True:
        criteria.append(_response_exists())
    elif has_response is False:
        criteria.append(~_response_exists())

    if brand_mentioned is not None:
        criteria.append(_first_response_value(AiResponse.brand_mentioned).is_(brand_mentioned))
    if citation_found is not None:
        criteria.append(_first_response_value(AiResponse.citation_found).is_(citation_found))
    return criteria


def _response_exists():
    return (
        select(AiResponse.id)
        .where(AiResponse.query_id == AiQuery.id)
        .correlate(AiQuery)
        .exists()
    )


def _first_response_value(column):
    return (
        select(column)
        .where(AiResponse.query_id == AiQuery.id)
        .correlate(AiQuery)
        .order_by(AiResponse.created_at.asc(), AiResponse.id.asc())
        .limit(1)
        .scalar_subquery()
    )


def _page_items(db: Session, criteria: list, *, limit: int, offset: int) -> list[ExplorerItem]:
    page_ids = list(
        db.scalars(
            select(AiQuery.id)
            .where(*criteria)
            .order_by(
                AiQuery.created_at.asc(),
                AiQuery.category.asc(),
                AiQuery.query_text.asc(),
                AiQuery.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )
    if not page_ids:
        return []

    queries = list(db.scalars(select(AiQuery).where(AiQuery.id.in_(page_ids))).all())
    responses = list(
        db.scalars(
            select(AiResponse)
            .where(AiResponse.query_id.in_(page_ids))
            .order_by(
                AiResponse.query_id.asc(),
                AiResponse.created_at.asc(),
                AiResponse.id.asc(),
            )
        ).all()
    )
    first_by_query: dict[UUID, AiResponse] = {}
    for response in responses:
        first_by_query.setdefault(response.query_id, response)

    order = {query_id: index for index, query_id in enumerate(page_ids)}
    queries.sort(key=lambda query: order[query.id])

    items: list[ExplorerItem] = []
    for query in queries:
        response = first_by_query.get(query.id)
        items.append(
            ExplorerItem(
                query_id=query.id,
                query_text=query.query_text,
                category=query.category,
                created_at=query.created_at,
                has_response=response is not None,
                response=_to_response(response) if response is not None else None,
            )
        )
    return items


def _to_audit(audit: Audit) -> ExplorerAudit:
    brand = audit.brand
    return ExplorerAudit(
        id=audit.id,
        brand_id=audit.brand_id,
        brand_name=brand.name if brand is not None else "",
        created_at=audit.created_at,
        completed_at=audit.completed_at,
        status=audit.status,
    )


def _to_response(row: AiResponse) -> ExplorerResponse:
    return ExplorerResponse(
        text=row.response_text,
        provider=row.provider,
        model=row.model,
        brand_mentioned=row.brand_mentioned,
        brand_position=row.brand_position,
        citation_found=row.citation_found,
        semantic_alignment=row.semantic_alignment,
        latency_ms=row.latency_ms,
    )


def _rate(numerator: int, denominator: int) -> Decimal:
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.0001"),
        rounding=ROUND_HALF_UP,
    )
