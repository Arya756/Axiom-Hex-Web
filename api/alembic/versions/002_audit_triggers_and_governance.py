"""Add PostgreSQL append-only triggers on audit_log and governance columns.

Revision ID: 002_audit_triggers_and_governance
Revises: 001_initial_schema
Create Date: 2026-11-11 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_audit_triggers_and_governance"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "no_external_processing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "revisions",
        sa.Column(
            "created_by",
            sa.String(64),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_log is strictly append-only; % is not permitted', TG_OP;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute("DROP TRIGGER IF EXISTS trg_audit_log_append_only ON audit_log;")
        op.execute(
            """
            CREATE TRIGGER trg_audit_log_append_only
            BEFORE UPDATE OR DELETE ON audit_log
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_modification();
            """
        )
        op.execute("REVOKE UPDATE, DELETE ON audit_log FROM axiom_app;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("GRANT UPDATE, DELETE ON audit_log TO axiom_app;")
        op.execute("DROP TRIGGER IF EXISTS trg_audit_log_append_only ON audit_log;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")

    op.drop_column("revisions", "created_by")
    op.drop_column("tenants", "no_external_processing")
