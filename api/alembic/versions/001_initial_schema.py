"""Initial schema with vector(384) and RLS policies

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-10 23:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = [
    "users",
    "sources",
    "source_versions",
    "contents",
    "revisions",
    "content_units",
    "review_runs",
    "findings",
    "finding_decisions",
    "comments",
    "approvals",
    "audit_log",
    "usage_ledger",
    "rule_stats",
]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. Tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ruleset_version", sa.Integer, default=1, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. Users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )

    # 3. Sources table
    op.create_table(
        "sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True, index=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("current_version", sa.Integer, default=1, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 4. Source versions table with vector(384)
    op.create_table(
        "source_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_id", sa.String(64), nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("value", sa.String(255), nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", sa.Integer, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False, index=True),
        sa.Column("lint_flags", sa.JSON, nullable=False),
        sa.Column("collisions", sa.JSON, nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "source_id", "version", name="uq_source_version"),
        sa.UniqueConstraint("tenant_id", "source_id", "content_hash", name="uq_source_version_hash"),
    )

    # 5. Contents table
    op.create_table(
        "contents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("file_type", sa.String(32), nullable=False),
        sa.Column("sensitivity", sa.String(32), default="internal", nullable=False),
        sa.Column("created_by", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 6. Revisions table
    op.create_table(
        "revisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("content_id", sa.String(64), sa.ForeignKey("contents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version_num", sa.Integer, default=1, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("status", sa.String(64), default="draft", nullable=False),
        sa.Column("approval_status", sa.String(32), default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 7. Content units table
    op.create_table(
        "content_units",
        sa.Column("unit_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("revision_id", sa.String(64), sa.ForeignKey("revisions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("start", sa.Integer, nullable=False),
        sa.Column("end", sa.Integer, nullable=False),
        sa.Column("page", sa.Integer, nullable=True),
        sa.Column("bbox_json", sa.JSON, nullable=True),
        sa.Column("style_json", sa.JSON, nullable=True),
        sa.Column("alt_text", sa.Text, nullable=True),
        sa.Column("source_map", sa.JSON, nullable=True),
    )

    # 8. Review runs table
    op.create_table(
        "review_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("revision_id", sa.String(64), sa.ForeignKey("revisions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ruleset_version", sa.Integer, nullable=False),
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), default="queued", nullable=False),
        sa.Column("partial", sa.Boolean, default=False, nullable=False),
        sa.Column("cache_key", sa.String(128), nullable=True, index=True),
        sa.Column("matched_sources", sa.JSON, nullable=False),
        sa.Column("run_progress", sa.JSON, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 9. Findings table
    op.create_table(
        "findings",
        sa.Column("finding_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("revision_id", sa.String(64), sa.ForeignKey("revisions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("review_runs.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("span_json", sa.JSON, nullable=False),
        sa.Column("evidence_json", sa.JSON, nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("suggested_fix_json", sa.JSON, nullable=True),
        sa.Column("route_to", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), default="open", nullable=False),
        sa.Column("abstained", sa.Boolean, default=False, nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=True, index=True),
        sa.Column("disclosure_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 10. Finding decisions table
    op.create_table(
        "finding_decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("finding_id", sa.String(64), sa.ForeignKey("findings.finding_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 11. Comments table
    op.create_table(
        "comments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("revision_id", sa.String(64), sa.ForeignKey("revisions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("finding_id", sa.String(64), nullable=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("span_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 12. Approvals table
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("revision_id", sa.String(64), sa.ForeignKey("revisions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("approver_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "revision_id", "approver_id", "content_hash", name="uq_approval"),
    )

    # 13. Audit log table
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("curr_hash", sa.String(64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )

    # 14. Usage ledger table
    op.create_table(
        "usage_ledger",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("run_id", sa.String(64), nullable=True, index=True),
        sa.Column("node", sa.String(64), nullable=False),
        sa.Column("method", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("external_call", sa.Boolean, default=False, nullable=False),
        sa.Column("data_categories", sa.JSON, nullable=False),
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("tokens", sa.Integer, nullable=True),
        sa.Column("cost", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 15. Rule stats table
    op.create_table(
        "rule_stats",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rule_id", sa.String(64), nullable=False, index=True),
        sa.Column("total_findings", sa.Integer, default=0, nullable=False),
        sa.Column("accepted_count", sa.Integer, default=0, nullable=False),
        sa.Column("disputed_count", sa.Integer, default=0, nullable=False),
        sa.Column("overridden_count", sa.Integer, default=0, nullable=False),
        sa.Column("abstained_count", sa.Integer, default=0, nullable=False),
        sa.Column("low_confidence_count", sa.Integer, default=0, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Row-Level Security & Role configuration (PostgreSQL only)
    if is_postgres:
        # Non-owner role creation and grant
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'axiom_app') THEN
                    CREATE ROLE axiom_app WITH LOGIN PASSWORD 'axiom_secret';
                END IF;
            END
            $$;
            GRANT USAGE ON SCHEMA public TO axiom_app;
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO axiom_app;
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO axiom_app;
        """)

        # Enable RLS on all tenant-scoped tables
        for table in TENANT_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
            op.execute(f"""
                CREATE POLICY {table}_tenant_isolation ON {table}
                    FOR ALL
                    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''));
            """)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        for table in TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    for table in reversed(TENANT_TABLES):
        op.drop_table(table)
    op.drop_table("tenants")

