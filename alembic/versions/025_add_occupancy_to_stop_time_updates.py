"""Add TMB Metro occupancy and headsign columns to stop_time_updates.

Revision ID: 025
Revises: 024
Create Date: 2026-01-18

This migration adds TMB Metro Barcelona real-time data fields:
- occupancy_percent: Overall train occupancy percentage
- occupancy_per_car: JSON array of per-car occupancy percentages
- headsign: Train destination (desti_trajecte from TMB API)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade():
    # Add TMB Metro specific columns to stop_time_updates
    op.add_column(
        'gtfs_rt_stop_time_updates',
        sa.Column('occupancy_percent', sa.Integer(), nullable=True)
    )
    op.add_column(
        'gtfs_rt_stop_time_updates',
        sa.Column('occupancy_per_car', sa.Text(), nullable=True)
    )
    op.add_column(
        'gtfs_rt_stop_time_updates',
        sa.Column('headsign', sa.String(200), nullable=True)
    )


def downgrade():
    op.drop_column('gtfs_rt_stop_time_updates', 'headsign')
    op.drop_column('gtfs_rt_stop_time_updates', 'occupancy_per_car')
    op.drop_column('gtfs_rt_stop_time_updates', 'occupancy_percent')
