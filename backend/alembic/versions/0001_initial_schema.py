"""Initial database schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website_url", sa.String(length=2048), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=255), nullable=True),
        sa.Column("target_market", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_brands_owner_id"), "brands", ["owner_id"], unique=False)

    op.create_table(
        "audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="audit_status"),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("overall_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("website_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("seo_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("ai_visibility_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("entity_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("semantic_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audits_brand_id"), "audits", ["brand_id"], unique=False)
    op.create_index(op.f("ix_audits_status"), "audits", ["status"], unique=False)

    op.create_table(
        "website_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("h1_count", sa.Integer(), nullable=True),
        sa.Column("h2_count", sa.Integer(), nullable=True),
        sa.Column("has_schema", sa.Boolean(), nullable=True),
        sa.Column("schema_types", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("load_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_website_pages_audit_id"), "website_pages", ["audit_id"], unique=False)

    op.create_table(
        "seo_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("HIGH", "MEDIUM", "LOW", "INFO", name="finding_severity"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["website_pages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_seo_findings_audit_id"), "seo_findings", ["audit_id"], unique=False)
    op.create_index(op.f("ix_seo_findings_page_id"), "seo_findings", ["page_id"], unique=False)

    op.create_table(
        "ai_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "BRAND",
                "PRODUCT",
                "INDUSTRY",
                "COMPETITOR",
                "COMMERCIAL",
                "INFORMATIONAL",
                name="ai_query_category",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_queries_audit_id"), "ai_queries", ["audit_id"], unique=False)
    op.create_index(op.f("ix_ai_queries_category"), "ai_queries", ["category"], unique=False)

    op.create_table(
        "ai_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("query_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("brand_mentioned", sa.Boolean(), nullable=True),
        sa.Column("brand_position", sa.Integer(), nullable=True),
        sa.Column("citation_found", sa.Boolean(), nullable=True),
        sa.Column("semantic_alignment", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["query_id"], ["ai_queries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_responses_query_id"), "ai_responses", ["query_id"], unique=False)

    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column(
            "priority",
            sa.Enum("HIGH", "MEDIUM", "LOW", name="recommendation_priority"),
            nullable=False,
        ),
        sa.Column("impact_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("effort_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recommendations_audit_id"), "recommendations", ["audit_id"], unique=False)
    op.create_index(op.f("ix_recommendations_priority"), "recommendations", ["priority"], unique=False)

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.Enum("GENERATING", "READY", "FAILED", name="report_status"),
            server_default="GENERATING",
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_audit_id"), "reports", ["audit_id"], unique=False)
    op.create_index(op.f("ix_reports_status"), "reports", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reports_status"), table_name="reports")
    op.drop_index(op.f("ix_reports_audit_id"), table_name="reports")
    op.drop_table("reports")

    op.drop_index(op.f("ix_recommendations_priority"), table_name="recommendations")
    op.drop_index(op.f("ix_recommendations_audit_id"), table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index(op.f("ix_ai_responses_query_id"), table_name="ai_responses")
    op.drop_table("ai_responses")

    op.drop_index(op.f("ix_ai_queries_category"), table_name="ai_queries")
    op.drop_index(op.f("ix_ai_queries_audit_id"), table_name="ai_queries")
    op.drop_table("ai_queries")

    op.drop_index(op.f("ix_seo_findings_page_id"), table_name="seo_findings")
    op.drop_index(op.f("ix_seo_findings_audit_id"), table_name="seo_findings")
    op.drop_table("seo_findings")

    op.drop_index(op.f("ix_website_pages_audit_id"), table_name="website_pages")
    op.drop_table("website_pages")

    op.drop_index(op.f("ix_audits_status"), table_name="audits")
    op.drop_index(op.f("ix_audits_brand_id"), table_name="audits")
    op.drop_table("audits")

    op.drop_index(op.f("ix_brands_owner_id"), table_name="brands")
    op.drop_table("brands")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    sa.Enum(name="report_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="recommendation_priority").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ai_query_category").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="finding_severity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="audit_status").drop(op.get_bind(), checkfirst=True)
