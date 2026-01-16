"""Create nucleos table for Renfe regional networks

Revision ID: 008
Revises: 007
Create Date: 2026-01-16

This migration creates the gtfs_nucleos table to store information about
Renfe's 12 regional networks (núcleos). Each núcleo represents a geographic
region served by Renfe with its own set of stations and routes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create gtfs_nucleos table with geographic boundaries."""
    # Create nucleos table
    op.create_table(
        'gtfs_nucleos',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=False),
        sa.Column('name', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('color', sa.String(50), nullable=True),
        sa.Column('bounding_box_min_lat', sa.Float, nullable=True),
        sa.Column('bounding_box_max_lat', sa.Float, nullable=True),
        sa.Column('bounding_box_min_lon', sa.Float, nullable=True),
        sa.Column('bounding_box_max_lon', sa.Float, nullable=True),
        sa.Column('center_lat', sa.Float, nullable=True),
        sa.Column('center_lon', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create index on name for fast lookups
    op.create_index('idx_nucleos_name', 'gtfs_nucleos', ['name'])


def downgrade() -> None:
    """Drop gtfs_nucleos table."""
    op.drop_table('gtfs_nucleos')
