"""patch governed evolution memory

Revision ID: 0035_patch_governed_evolution_memory
Revises: 0034_patch_governed_evolution_core
Create Date: 2026-04-20

AO-02 hotfix:
Make this migration additive and idempotent. Production may already have some
columns/tables/indexes because boot-time reconcile ran before Alembic could
record all revisions.
"""

from alembic import op
import sqlalchemy as sa


revision = "0035_patch_governed_evolution_memory"
down_revision = "0034_patch_governed_evolution_core"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return any(col.get("name") == column_name for col in inspector.get_columns(table_name))
    except Exception:
        return False


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))
    except Exception:
        return False


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if _table_exists(table_name) and not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def upgrade():
    _add_column_if_missing("evolution_proposals", sa.Column("domain_scope", sa.String(), nullable=True))
    _add_column_if_missing("evolution_proposals", sa.Column("recurrence_window_count", sa.Integer(), nullable=False, server_default="1"))
    _add_column_if_missing("evolution_proposals", sa.Column("blast_radius_accumulated", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("evolution_proposals", sa.Column("security_accumulated", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("evolution_proposals", sa.Column("last_priority_score", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("evolution_proposals", sa.Column("last_recommendation", sa.String(), nullable=True))
    _add_column_if_missing("evolution_proposals", sa.Column("last_cadence_seconds", sa.Integer(), nullable=False, server_default="0"))

    if not _table_exists("evolution_signal_snapshots"):
        op.create_table(
            "evolution_signal_snapshots",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("org_slug", sa.String(), nullable=False, server_default="system"),
            sa.Column("proposal_id", sa.String(), nullable=False),
            sa.Column("fingerprint", sa.String(), nullable=False),
            sa.Column("code", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("domain_scope", sa.String(), nullable=True),
            sa.Column("recurrence_window_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("blast_radius_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("security_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("priority_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("recommendation", sa.String(), nullable=True),
            sa.Column("cadence_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("policy_version", sa.String(), nullable=True),
            sa.Column("trace_id", sa.String(), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
        )

    if not _index_exists("evolution_signal_snapshots", "ix_evolution_signal_snapshots_proposal_created"):
        op.create_index("ix_evolution_signal_snapshots_proposal_created", "evolution_signal_snapshots", ["proposal_id", "created_at"])
    if not _index_exists("evolution_signal_snapshots", "ix_evolution_signal_snapshots_fingerprint_created"):
        op.create_index("ix_evolution_signal_snapshots_fingerprint_created", "evolution_signal_snapshots", ["fingerprint", "created_at"])

    if not _table_exists("evolution_cycle_logs"):
        op.create_table(
            "evolution_cycle_logs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("org_slug", sa.String(), nullable=False, server_default="system"),
            sa.Column("trace_id", sa.String(), nullable=True),
            sa.Column("findings", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("classified", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("proposals_touched", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("proposals_created", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("proposals_suppressed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_priority_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("avg_priority_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_interval_suggested_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("recommendation_buckets_json", sa.Text(), nullable=True),
            sa.Column("domain_buckets_json", sa.Text(), nullable=True),
            sa.Column("top_queue_json", sa.Text(), nullable=True),
            sa.Column("policy_version", sa.String(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
        )

    if not _index_exists("evolution_cycle_logs", "ix_evolution_cycle_logs_created"):
        op.create_index("ix_evolution_cycle_logs_created", "evolution_cycle_logs", ["created_at"])


def downgrade():
    if _index_exists("evolution_cycle_logs", "ix_evolution_cycle_logs_created"):
        op.drop_index("ix_evolution_cycle_logs_created", table_name="evolution_cycle_logs")
    if _table_exists("evolution_cycle_logs"):
        op.drop_table("evolution_cycle_logs")

    if _index_exists("evolution_signal_snapshots", "ix_evolution_signal_snapshots_fingerprint_created"):
        op.drop_index("ix_evolution_signal_snapshots_fingerprint_created", table_name="evolution_signal_snapshots")
    if _index_exists("evolution_signal_snapshots", "ix_evolution_signal_snapshots_proposal_created"):
        op.drop_index("ix_evolution_signal_snapshots_proposal_created", table_name="evolution_signal_snapshots")
    if _table_exists("evolution_signal_snapshots"):
        op.drop_table("evolution_signal_snapshots")

    for col in [
        "last_cadence_seconds",
        "last_recommendation",
        "last_priority_score",
        "security_accumulated",
        "blast_radius_accumulated",
        "recurrence_window_count",
        "domain_scope",
    ]:
        if _column_exists("evolution_proposals", col):
            op.drop_column("evolution_proposals", col)
