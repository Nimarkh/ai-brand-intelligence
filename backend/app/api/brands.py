from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.brand import Brand
from app.models.user import User
from app.schemas.brand import BrandCreate, BrandListResponse, BrandResponse, BrandUpdate
from app.services import brand_service

router = APIRouter(prefix="/brands", tags=["brands"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found.")

AUTH_RESPONSES = {
    401: {"description": "Not authenticated"},
}


def _require_brand(db: Session, owner_id: UUID, brand_id: UUID) -> Brand:
    brand = brand_service.get_user_brand(db, owner_id, brand_id)
    if brand is None:
        raise NOT_FOUND
    return brand


@router.get(
    "",
    response_model=BrandListResponse,
    summary="List brands",
    description=(
        "Return brands owned by the authenticated user, newest first. "
        "Requires the session cookie. Brands owned by other users are never included."
    ),
    responses=AUTH_RESPONSES,
)
def list_brands(
    limit: int = Query(default=100, ge=1, le=100, description="Maximum number of brands to return."),
    offset: int = Query(default=0, ge=0, description="Number of owned brands to skip."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BrandListResponse:
    items, total = brand_service.list_user_brands(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
    )
    return BrandListResponse(items=items, total=total)


@router.post(
    "",
    response_model=BrandResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a brand",
    description=(
        "Create a brand owned by the authenticated user. "
        "The owner is taken from the session. The request body cannot set owner_id. "
        "This does not crawl the website."
    ),
    responses=AUTH_RESPONSES,
)
def create_brand(
    payload: BrandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Brand:
    return brand_service.create_brand(db, owner_id=current_user.id, payload=payload)


@router.get(
    "/{brand_id}",
    response_model=BrandResponse,
    summary="Get a brand",
    description=(
        "Return one brand owned by the authenticated user. "
        "Unknown ids and brands owned by someone else both return 404."
    ),
    responses={**AUTH_RESPONSES, 404: {"description": "Brand not found"}},
)
def get_brand(
    brand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Brand:
    return _require_brand(db, current_user.id, brand_id)


@router.patch(
    "/{brand_id}",
    response_model=BrandResponse,
    summary="Update a brand",
    description=(
        "Update fields on a brand owned by the authenticated user. "
        "id, owner_id, and timestamps cannot be changed. "
        "Unknown ids and brands owned by someone else both return 404."
    ),
    responses={**AUTH_RESPONSES, 404: {"description": "Brand not found"}},
)
def update_brand(
    brand_id: UUID,
    payload: BrandUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Brand:
    brand = _require_brand(db, current_user.id, brand_id)
    return brand_service.update_brand(db, brand, payload)


@router.delete(
    "/{brand_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a brand",
    description=(
        "Permanently delete a brand owned by the authenticated user. "
        "Unknown ids and brands owned by someone else both return 404. "
        "Only that brand row is deleted. No audit records are created by this API."
    ),
    responses={**AUTH_RESPONSES, 404: {"description": "Brand not found"}},
)
def delete_brand(
    brand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    brand = _require_brand(db, current_user.id, brand_id)
    brand_service.delete_brand(db, brand)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
