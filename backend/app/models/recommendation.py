from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import RecommendationPriority

if TYPE_CHECKING:
    from app.models.audit import Audit


class Recommendation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "recommendations"

    audit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[RecommendationPriority] = mapped_column(
        Enum(
            RecommendationPriority,
            name="recommendation_priority",
            native_enum=True,
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
        index=True,
    )
    impact_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    effort_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    audit: Mapped[Audit] = relationship(back_populates="recommendations")
