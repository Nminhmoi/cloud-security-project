"""Bổ sung siêu dữ liệu bảo mật lưu trữ tài liệu

Mã phiên bản: f3c8a1d9b702
Phiên bản trước: e7b9c2a4d1f0
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

    # Các bản ghi cũ dùng filename làm khóa lưu trữ thực tế ở cục bộ hoặc trên S3.
    # Giữ giá trị này trong storage_key giúp bản di chuyển tương thích ngược.
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
