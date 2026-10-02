"""add attendance guardians and face embeddings

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "responsaveis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("telefone", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_responsaveis_id"), "responsaveis", ["id"], unique=False)

    op.create_table(
        "aluno_responsaveis",
        sa.Column("aluno_id", sa.Integer(), nullable=False),
        sa.Column("responsavel_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["aluno_id"], ["alunos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responsavel_id"], ["responsaveis.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("aluno_id", "responsavel_id"),
    )

    op.create_table(
        "presencas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aluno_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("origem", sa.String(), nullable=False),
        sa.Column("confianca", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["aluno_id"], ["alunos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_presencas_aluno_id"), "presencas", ["aluno_id"], unique=False)
    op.create_index(op.f("ix_presencas_id"), "presencas", ["id"], unique=False)

    op.create_table(
        "face_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aluno_id", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["aluno_id"], ["alunos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_face_embeddings_aluno_id"), "face_embeddings", ["aluno_id"], unique=False)
    op.create_index(op.f("ix_face_embeddings_id"), "face_embeddings", ["id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_face_embeddings_id"), table_name="face_embeddings")
    op.drop_index(op.f("ix_face_embeddings_aluno_id"), table_name="face_embeddings")
    op.drop_table("face_embeddings")
    op.drop_index(op.f("ix_presencas_id"), table_name="presencas")
    op.drop_index(op.f("ix_presencas_aluno_id"), table_name="presencas")
    op.drop_table("presencas")
    op.drop_table("aluno_responsaveis")
    op.drop_index(op.f("ix_responsaveis_id"), table_name="responsaveis")
    op.drop_table("responsaveis")
