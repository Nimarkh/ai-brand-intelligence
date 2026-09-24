from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import AiQueryCategory
from app.models.user import User
from app.schemas.query_explorer import QueryExplorerView, serialize_query_explorer
from app.services.query_explorer import QueryExplorerAuditNotFound, get_query_explorer

router = APIRouter(prefix="/query-explorer", tags=["query-explorer"])

ALLOWED_PAGE_SIZES = frozenset({10, 20, 50, 100})

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
INVALID_PAGE_SIZE = HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    detail="page_size must be one of 10, 20, 50, 100.",
)


@router.get(
    "",
    response_model=QueryExplorerView,
    summary="Inspect persisted AI queries and responses",
    description=(
        "Return a read-only view of AI queries and responses for one owned audit. "
        "When audit_id is omitted, the latest completed owned audit is used, "
        "otherwise the latest owned audit. An audit owned by someone else returns 404. "
        "This endpoint does not execute queries or recalculate scores. "
        "Mention rate and citation rate are null when the audit has no responses."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Not found"},
        422: {"description": "Invalid filter or pagination parameter"},
    },
)
def read_query_explorer(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_id: Annotated[UUID | None, Query()] = None,
    category: Annotated[AiQueryCategory | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    has_response: Annotated[bool | None, Query()] = None,
    brand_mentioned: Annotated[bool | None, Query()] = None,
    citation_found: Annotated[bool | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> QueryExplorerView:
    if page_size not in ALLOWED_PAGE_SIZES:
        raise INVALID_PAGE_SIZE
    try:
        result = get_query_explorer(
            current_user,
            db,
            audit_id=audit_id,
            category=category,
            search=search,
            has_response=has_response,
            brand_mentioned=brand_mentioned,
            citation_found=citation_found,
            page=page,
            page_size=page_size,
        )
    except QueryExplorerAuditNotFound:
        raise NOT_FOUND from None
    return serialize_query_explorer(result)
