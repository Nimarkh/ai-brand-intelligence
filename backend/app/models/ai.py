from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import AiQueryCategory

if TYPE_CHECKING:
    from app.models.audit import Audit


class AiQuery(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ai_queries"

    audit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[AiQueryCategory] = mapped_column(
        Enum(
            AiQueryCategory,
            name="ai_query_category",
            native_enum=True,
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
        index=True,
    )

    audit: Mapped[Audit] = relationship(back_populates="ai_queries")
    responses: Mapped[list[AiResponse]] = relationship(back_populates="query")


class AiResponse(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ai_responses"

    query_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_queries.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    brand_mentioned: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    brand_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    citation_found: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    semantic_alignment: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    query: Mapped[AiQuery] = relationship(back_populates="responses")
