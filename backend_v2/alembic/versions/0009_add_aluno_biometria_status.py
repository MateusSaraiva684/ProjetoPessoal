"""add aluno biometria status

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("alunos") as batch_op:
        batch_op.add_column(
            sa.Column(
                "biometria_status",
                sa.String(),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(sa.Column("biometria_error", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("biometria_atualizada_em", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "face_samples_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

    op.execute("UPDATE alunos SET biometria_status = 'no_photo' WHERE foto IS NULL")


def downgrade():
    with op.batch_alter_table("alunos") as batch_op:
        batch_op.drop_column("face_samples_count")
        batch_op.drop_column("biometria_atualizada_em")
        batch_op.drop_column("biometria_error")
        batch_op.drop_column("biometria_status")
