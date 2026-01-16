"""Add province field to gtfs_stops

Revision ID: 005
Revises: 004
Create Date: 2025-01-15
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add province column to gtfs_stops table."""
    op.add_column(
        'gtfs_stops',
        sa.Column('province', sa.String(50), nullable=True)
    )


def downgrade() -> None:
    """Remove province column from gtfs_stops table."""
    op.drop_column('gtfs_stops', 'province')
