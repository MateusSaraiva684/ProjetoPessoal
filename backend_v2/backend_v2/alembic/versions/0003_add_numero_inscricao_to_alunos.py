"""add numero_inscricao to alunos

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-10
"""
from collections import defaultdict
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("alunos") as batch_op:
        batch_op.add_column(sa.Column("numero_inscricao", sa.String(), nullable=True))

    bind = op.get_bind()
    alunos = sa.table(
        "alunos",
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.Integer()),
        sa.column("numero_inscricao", sa.String()),
    )

    contadores_por_usuario = defaultdict(int)
    registros = bind.execute(
        sa.select(alunos.c.id, alunos.c.user_id).order_by(alunos.c.user_id, alunos.c.id)
    ).fetchall()

    for registro in registros:
        contadores_por_usuario[registro.user_id] += 1
        bind.execute(
            sa.update(alunos)
            .where(alunos.c.id == registro.id)
            .values(numero_inscricao=f"{contadores_por_usuario[registro.user_id]:04d}")
        )

    with op.batch_alter_table("alunos") as batch_op:
        batch_op.alter_column(
            "numero_inscricao",
            existing_type=sa.String(),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_alunos_user_numero_inscricao",
            ["user_id", "numero_inscricao"],
        )


def downgrade() -> None:
    with op.batch_alter_table("alunos") as batch_op:
        batch_op.drop_constraint("uq_alunos_user_numero_inscricao", type_="unique")
        batch_op.drop_column("numero_inscricao")
