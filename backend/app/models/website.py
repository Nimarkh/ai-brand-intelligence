from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import FindingSeverity

if TYPE_CHECKING:
    from app.models.audit import Audit


class WebsitePage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "website_pages"

    audit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    h1_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    h2_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_schema: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    schema_types: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    load_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    audit: Mapped[Audit] = relationship(back_populates="website_pages")
    seo_findings: Mapped[list[SeoFinding]] = relationship(back_populates="page")


class SeoFinding(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "seo_findings"

    audit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    page_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("website_pages.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(
            FindingSeverity,
            name="finding_severity",
            native_enum=True,
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)

    audit: Mapped[Audit] = relationship(back_populates="seo_findings")
    page: Mapped[WebsitePage | None] = relationship(back_populates="seo_findings")
