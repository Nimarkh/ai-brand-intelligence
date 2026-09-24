from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardOverview, serialize_dashboard
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/overview",
    response_model=DashboardOverview,
    summary="Main Intelligence Dashboard overview",
    description=(
        "Return the Main Intelligence Dashboard for the authenticated user. "
        "Scores are read from persisted audit columns only and are never recalculated. "
        "Audit selection: most recently completed owned audit; if none, most recent "
        "owned audit; empty when there are no audits. Optional brand_id must be owned "
        "or it is ignored. Null scores mean unavailable, not zero."
    ),
    responses={401: {"description": "Not authenticated"}},
)
def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    brand_id: UUID | None = Query(
        default=None,
        description="Optional owned brand filter for selected audit selection.",
    ),
) -> DashboardOverview:
    aggregate = dashboard_service.get_dashboard_overview(
        current_user,
        db,
        brand_id=brand_id,
    )
    return serialize_dashboard(aggregate)
