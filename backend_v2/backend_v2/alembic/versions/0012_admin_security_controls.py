"""add admin security controls

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("role", sa.String(length=30), nullable=True))
    op.add_column("usuarios", sa.Column("mfa_secret", sa.String(length=64), nullable=True))
    op.add_column("usuarios", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("usuarios", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("usuarios", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE usuarios SET role = CASE WHEN is_superuser THEN 'superadmin' ELSE 'operator' END")
    op.create_index("ix_usuarios_role", "usuarios", ["role"], unique=False)


def downgrade():
    op.drop_index("ix_usuarios_role", table_name="usuarios")
    op.drop_column("usuarios", "locked_until")
    op.drop_column("usuarios", "failed_login_attempts")
    op.drop_column("usuarios", "mfa_enabled")
    op.drop_column("usuarios", "mfa_secret")
    op.drop_column("usuarios", "role")
