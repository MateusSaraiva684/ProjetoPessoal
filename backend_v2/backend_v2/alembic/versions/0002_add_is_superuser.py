"""add is_superuser to usuarios

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'usuarios',
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade():
    op.drop_column('usuarios', 'is_superuser')
