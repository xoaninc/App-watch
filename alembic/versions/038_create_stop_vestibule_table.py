"""Create stop_vestibule table for metro station vestibules.

This table stores information about internal vestibules (lobbies) within
metro stations, including their location, type, and operating hours.

Revision ID: 038
Revises: 037
Create Date: 2026-01-28
"""
from alembic import op
import sqlalchemy as sa

revision = '038'
down_revision = '037'
branch_labels = None
depends_on = None


def upgrade():
    """Create stop_vestibule table for metro station vestibules."""
    op.create_table(
        'stop_vestibule',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stop_id', sa.String(100), nullable=False),  # Reference to gtfs_stops
        sa.Column('name', sa.String(255), nullable=False),  # Vestibule name
        sa.Column('lat', sa.Float(), nullable=False),  # WGS84 latitude
        sa.Column('lon', sa.Float(), nullable=False),  # WGS84 longitude
        sa.Column('level', sa.Integer(), nullable=True),  # Underground level (-1, -2, etc.)
        sa.Column('vestibule_type', sa.String(50), nullable=True),  # Type of vestibule
        sa.Column('turnstile_type', sa.String(50), nullable=True),  # Type of turnstile
        sa.Column('opening_time', sa.Time(), nullable=True),  # Opening time
        sa.Column('closing_time', sa.Time(), nullable=True),  # Closing time
        sa.Column('wheelchair', sa.Boolean(), nullable=True),  # Wheelchair accessible
        sa.Column('source', sa.String(50), nullable=True),  # Data source ('crtm', 'osm', etc.)
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('ix_stop_vestibule_stop_id', 'stop_vestibule', ['stop_id'])

    print("Created stop_vestibule table")


def downgrade():
    """Drop stop_vestibule table."""
    op.drop_index('ix_stop_vestibule_stop_id', table_name='stop_vestibule')
    op.drop_table('stop_vestibule')
