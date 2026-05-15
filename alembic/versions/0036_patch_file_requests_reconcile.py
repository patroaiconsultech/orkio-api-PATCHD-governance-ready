"""reconcile file_requests schema drift

Revision ID: 0036_patch_file_requests_reconcile
Revises: 0035_patch_governed_evolution_memory
Create Date: 2026-05-15

Purpose:
Production showed SQLAlchemy/psycopg2 UndefinedTable for file_requests on:
GET /api/admin/file-requests

The model and historical migration exist, but the live database may have been
advanced/stamped without the table being created. This migration is intentionally
idempotent and additive-only.
"""

from alembic import op
import sqlalchemy as sa


revision = "0036_patch_file_requests_reconcile"
down_revision = "0035_patch_governed_evolution_memory"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    bind.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS file_requests (
            id VARCHAR PRIMARY KEY,
            org_slug VARCHAR NOT NULL,
            file_id VARCHAR NOT NULL,
            requested_by_user_id VARCHAR NULL,
            requested_by_user_name VARCHAR NULL,
            status VARCHAR NOT NULL DEFAULT 'pending',
            created_at BIGINT NOT NULL,
            resolved_at BIGINT NULL,
            resolved_by_admin_id VARCHAR NULL
        )
    """))

    bind.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_file_requests_org_slug
        ON file_requests (org_slug)
    """))

    bind.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_file_requests_file_id
        ON file_requests (file_id)
    """))

    bind.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_file_requests_status
        ON file_requests (status)
    """))

    bind.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_file_requests_org_status_created
        ON file_requests (org_slug, status, created_at DESC)
    """))


def downgrade():
    # Safety-first downgrade: remove only the composite index introduced here.
    # Do not drop file_requests because it may contain production governance data.
    bind = op.get_bind()
    bind.execute(sa.text("""
        DROP INDEX IF EXISTS ix_file_requests_org_status_created
    """))
