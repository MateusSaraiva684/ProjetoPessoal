"""add recognition event id to presencas

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("presencas") as batch_op:
        batch_op.add_column(sa.Column("recognition_event_id", sa.String(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_presencas_recognition_event_id",
            ["recognition_event_id"],
        )


def downgrade():
    with op.batch_alter_table("presencas") as batch_op:
        batch_op.drop_constraint("uq_presencas_recognition_event_id", type_="unique")
        batch_op.drop_column("recognition_event_id")
