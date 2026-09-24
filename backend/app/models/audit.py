from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import AuditStatus

if TYPE_CHECKING:
    from app.models.ai import AiQuery
    from app.models.brand import Brand
    from app.models.recommendation import Recommendation
    from app.models.report import Report
    from app.models.website import SeoFinding, WebsitePage


class Audit(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "audits"

    brand_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[AuditStatus] = mapped_column(
        Enum(
            AuditStatus,
            name="audit_status",
            native_enum=True,
            values_callable=lambda items: [item.value for item in items],
        ),
        default=AuditStatus.PENDING,
        server_default=AuditStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    website_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    seo_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    ai_visibility_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    entity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    semantic_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    brand: Mapped[Brand] = relationship(back_populates="audits")
    website_pages: Mapped[list[WebsitePage]] = relationship(back_populates="audit")
    seo_findings: Mapped[list[SeoFinding]] = relationship(back_populates="audit")
    ai_queries: Mapped[list[AiQuery]] = relationship(back_populates="audit")
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="audit")
    reports: Mapped[list[Report]] = relationship(back_populates="audit")
