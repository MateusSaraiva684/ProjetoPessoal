"""add notification outbox

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("canal", sa.String(), nullable=False),
        sa.Column("presenca_id", sa.Integer(), nullable=False),
        sa.Column("aluno_id", sa.Integer(), nullable=False),
        sa.Column("responsavel_id", sa.Integer(), nullable=False),
        sa.Column("telefone_destino", sa.String(), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("provider_message_id", sa.String(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["aluno_id"], ["alunos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["presenca_id"], ["presencas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responsavel_id"], ["responsaveis.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tipo",
            "presenca_id",
            "responsavel_id",
            "canal",
            name="uq_notification_outbox_presence_recipient_channel",
        ),
    )
    op.create_index(op.f("ix_notification_outbox_id"), "notification_outbox", ["id"], unique=False)
    op.create_index(
        "ix_notification_outbox_status_next_attempt_at",
        "notification_outbox",
        ["status", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_outbox_presenca_id"),
        "notification_outbox",
        ["presenca_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_outbox_responsavel_id"),
        "notification_outbox",
        ["responsavel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_outbox_aluno_id"),
        "notification_outbox",
        ["aluno_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_outbox_status"),
        "notification_outbox",
        ["status"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_notification_outbox_status"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_aluno_id"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_responsavel_id"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_presenca_id"), table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_status_next_attempt_at", table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_id"), table_name="notification_outbox")
    op.drop_table("notification_outbox")
