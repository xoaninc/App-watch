"""Add color and description columns to stop_platform table.

Revision ID: 032
Revises: 031
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add color column (hex without #, e.g., 'FF0000')
    op.add_column('stop_platform', sa.Column('color', sa.String(6), nullable=True))
    # Add description column (platform direction, e.g., 'Dirección Nuevos Ministerios')
    op.add_column('stop_platform', sa.Column('description', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('stop_platform', 'description')
    op.drop_column('stop_platform', 'color')
