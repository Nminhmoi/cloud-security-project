"""add login security fields

Revision ID: e7b9c2a4d1f0
Revises: d2348789afa3
"""

from alembic import op
import sqlalchemy as sa


revision = "e7b9c2a4d1f0"
down_revision = "d2348789afa3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "failed_login_attempts",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("locked_until", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "session_version",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("session_version")
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_login_attempts")
