"""add document storage security metadata

Revision ID: f3c8a1d9b702
Revises: e7b9c2a4d1f0
"""

from alembic import op
import sqlalchemy as sa


revision = "f3c8a1d9b702"
down_revision = "e7b9c2a4d1f0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("storage_key", sa.String(length=512)))
        batch_op.add_column(sa.Column("content_type", sa.String(length=255)))
        batch_op.add_column(sa.Column("sha256", sa.String(length=64)))
        batch_op.add_column(
            sa.Column(
                "scan_status",
                sa.String(length=32),
                server_default="not_scanned",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime()))
        batch_op.create_index("ix_documents_sha256", ["sha256"], unique=False)
        batch_op.create_check_constraint(
            "ck_documents_scan_status",
            "scan_status IN ('not_scanned', 'pending', 'clean', 'infected', 'failed')",
        )

    # Existing rows used filename as the physical local/S3 key. Keeping that
    # value in storage_key makes the migration backward compatible.
    op.execute("UPDATE documents SET storage_key = filename WHERE storage_key IS NULL")


def downgrade():
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_constraint("ck_documents_scan_status", type_="check")
        batch_op.drop_index("ix_documents_sha256")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("scan_status")
        batch_op.drop_column("sha256")
        batch_op.drop_column("content_type")
        batch_op.drop_column("storage_key")
