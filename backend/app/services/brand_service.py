from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.schemas.brand import BrandCreate, BrandUpdate


def list_user_brands(
    db: Session,
    owner_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Brand], int]:
    owned = Brand.owner_id == owner_id
    total = db.scalar(select(func.count()).select_from(Brand).where(owned)) or 0
    items = list(
        db.scalars(
            select(Brand)
            .where(owned)
            .order_by(Brand.created_at.desc(), Brand.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return items, total


def get_user_brand(db: Session, owner_id: UUID, brand_id: UUID) -> Brand | None:
    """Return the brand only when it belongs to owner_id.

    Missing ids and another user's brands both return None so callers can
    respond with 404 without revealing that the row exists.
    """
    return db.scalar(select(Brand).where(Brand.id == brand_id, Brand.owner_id == owner_id))


def create_brand(db: Session, *, owner_id: UUID, payload: BrandCreate) -> Brand:
    brand = Brand(owner_id=owner_id, **payload.model_dump())
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


def update_brand(db: Session, brand: Brand, payload: BrandUpdate) -> Brand:
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(brand, field, value)
    db.commit()
    db.refresh(brand)
    return brand


def delete_brand(db: Session, brand: Brand) -> None:
    db.delete(brand)
    db.commit()
