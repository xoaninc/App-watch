"""Create stop_access table for metro station entrances.

This table stores information about physical entrances (bocas) to metro stations,
including location, street address, and operating hours.

Revision ID: 037
Revises: 036_add_platform_history_unique_constraint
Create Date: 2026-01-28
"""
from alembic import op
import sqlalchemy as sa

revision = '037'
down_revision = '036_add_platform_history_unique_constraint'
branch_labels = None
depends_on = None


def upgrade():
    """Create stop_access table for metro station entrances."""
    op.create_table(
        'stop_access',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stop_id', sa.String(100), nullable=False),  # Reference to gtfs_stops
        sa.Column('name', sa.String(255), nullable=False),  # Access/entrance name
        sa.Column('lat', sa.Float(), nullable=False),  # WGS84 latitude
        sa.Column('lon', sa.Float(), nullable=False),  # WGS84 longitude
        sa.Column('street', sa.String(255), nullable=True),  # Street name
        sa.Column('street_number', sa.String(20), nullable=True),  # Street number
        sa.Column('opening_time', sa.Time(), nullable=True),  # Opening time
        sa.Column('closing_time', sa.Time(), nullable=True),  # Closing time
        sa.Column('wheelchair', sa.Boolean(), nullable=True),  # Wheelchair accessible
        sa.Column('level', sa.Integer(), nullable=True),  # Entry level (0, -1, -2...)
        sa.Column('source', sa.String(50), nullable=True),  # Data source ('crtm', 'osm', etc.)
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('ix_stop_access_stop_id', 'stop_access', ['stop_id'])

    print("Created stop_access table")


def downgrade():
    """Drop stop_access table."""
    op.drop_index('ix_stop_access_stop_id', table_name='stop_access')
    op.drop_table('stop_access')
