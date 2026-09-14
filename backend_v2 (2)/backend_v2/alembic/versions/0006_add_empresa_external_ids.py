"""add empresa and external ids

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("alunos") as batch_op:
        batch_op.add_column(sa.Column("empresa_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("external_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_alunos_empresa_id_usuarios",
            "usuarios",
            ["empresa_id"],
            ["id"],
        )

    bind = op.get_bind()
    alunos = sa.table(
        "alunos",
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.Integer()),
        sa.column("empresa_id", sa.Integer()),
        sa.column("external_id", sa.String()),
    )
    bind.execute(
        sa.update(alunos).values(
            empresa_id=alunos.c.user_id,
            external_id=sa.cast(alunos.c.id, sa.String()),
        )
    )

    with op.batch_alter_table("alunos") as batch_op:
        batch_op.alter_column("empresa_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("external_id", existing_type=sa.String(), nullable=False)
        batch_op.create_unique_constraint(
            "uq_alunos_empresa_external_id",
            ["empresa_id", "external_id"],
        )

    op.create_index(op.f("ix_alunos_empresa_id"), "alunos", ["empresa_id"], unique=False)

    with op.batch_alter_table("presencas") as batch_op:
        batch_op.add_column(sa.Column("empresa_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_presencas_empresa_id_usuarios",
            "usuarios",
            ["empresa_id"],
            ["id"],
        )

    presencas = sa.table(
        "presencas",
        sa.column("id", sa.Integer()),
        sa.column("aluno_id", sa.Integer()),
        sa.column("empresa_id", sa.Integer()),
    )

    registros = bind.execute(
        sa.select(presencas.c.id, alunos.c.empresa_id).select_from(
            presencas.join(alunos, presencas.c.aluno_id == alunos.c.id)
        )
    ).fetchall()
    for registro in registros:
        bind.execute(
            sa.update(presencas)
            .where(presencas.c.id == registro.id)
            .values(empresa_id=registro.empresa_id)
        )

    with op.batch_alter_table("presencas") as batch_op:
        batch_op.alter_column("empresa_id", existing_type=sa.Integer(), nullable=False)

    op.create_index(op.f("ix_presencas_empresa_id"), "presencas", ["empresa_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_presencas_empresa_id"), table_name="presencas")
    with op.batch_alter_table("presencas") as batch_op:
        batch_op.drop_constraint("fk_presencas_empresa_id_usuarios", type_="foreignkey")
        batch_op.drop_column("empresa_id")

    op.drop_index(op.f("ix_alunos_empresa_id"), table_name="alunos")
    with op.batch_alter_table("alunos") as batch_op:
        batch_op.drop_constraint("uq_alunos_empresa_external_id", type_="unique")
        batch_op.drop_constraint("fk_alunos_empresa_id_usuarios", type_="foreignkey")
        batch_op.drop_column("external_id")
        batch_op.drop_column("empresa_id")
