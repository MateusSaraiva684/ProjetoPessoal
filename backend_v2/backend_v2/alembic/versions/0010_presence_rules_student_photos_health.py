"""presence rules student photos health

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("presencas") as batch_op:
        batch_op.add_column(sa.Column("tipo_evento", sa.String(), nullable=False, server_default="entrada"))
        batch_op.add_column(sa.Column("turno", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("camera_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("observacao", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("criado_por_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_presencas_criado_por_id_usuarios",
            "usuarios",
            ["criado_por_id"],
            ["id"],
        )

    with op.batch_alter_table("notification_outbox") as batch_op:
        batch_op.add_column(sa.Column("empresa_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_notification_outbox_empresa_id_usuarios",
            "usuarios",
            ["empresa_id"],
            ["id"],
        )
        batch_op.create_index("ix_notification_outbox_empresa_id", ["empresa_id"])

    op.execute(
        """
        UPDATE notification_outbox
        SET empresa_id = (
            SELECT presencas.empresa_id
            FROM presencas
            WHERE presencas.id = notification_outbox.presenca_id
        )
        WHERE empresa_id IS NULL
        """
    )

    op.create_table(
        "aluno_fotos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aluno_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("storage_public_id", sa.String(), nullable=True),
        sa.Column("tipo", sa.String(), nullable=False, server_default="biometrica"),
        sa.Column("principal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("biometria_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("biometria_error", sa.String(), nullable=True),
        sa.Column("face_sample_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["aluno_id"], ["alunos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["empresa_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_aluno_fotos_id"), "aluno_fotos", ["id"], unique=False)
    op.create_index(op.f("ix_aluno_fotos_aluno_id"), "aluno_fotos", ["aluno_id"], unique=False)
    op.create_index(op.f("ix_aluno_fotos_empresa_id"), "aluno_fotos", ["empresa_id"], unique=False)

    op.execute(
        """
        INSERT INTO aluno_fotos (
            aluno_id,
            empresa_id,
            url,
            tipo,
            principal,
            criada_em,
            biometria_status,
            biometria_error
        )
        SELECT
            id,
            empresa_id,
            foto,
            'principal',
            true,
            COALESCE(criado_em, CURRENT_TIMESTAMP),
            COALESCE(biometria_status, 'pending'),
            biometria_error
        FROM alunos
        WHERE foto IS NOT NULL
        """
    )


def downgrade():
    op.drop_index(op.f("ix_aluno_fotos_empresa_id"), table_name="aluno_fotos")
    op.drop_index(op.f("ix_aluno_fotos_aluno_id"), table_name="aluno_fotos")
    op.drop_index(op.f("ix_aluno_fotos_id"), table_name="aluno_fotos")
    op.drop_table("aluno_fotos")

    with op.batch_alter_table("notification_outbox") as batch_op:
        batch_op.drop_index("ix_notification_outbox_empresa_id")
        batch_op.drop_constraint("fk_notification_outbox_empresa_id_usuarios", type_="foreignkey")
        batch_op.drop_column("empresa_id")

    with op.batch_alter_table("presencas") as batch_op:
        batch_op.drop_constraint("fk_presencas_criado_por_id_usuarios", type_="foreignkey")
        batch_op.drop_column("criado_por_id")
        batch_op.drop_column("observacao")
        batch_op.drop_column("camera_id")
        batch_op.drop_column("turno")
        batch_op.drop_column("tipo_evento")
