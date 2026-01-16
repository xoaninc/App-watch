"""Create ETA tables

Revision ID: 003
Revises: 002
Create Date: 2026-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create track segments table
    op.create_table(
        'gtfs_track_segments',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('route_id', sa.String(50), nullable=False),
        sa.Column('from_stop_id', sa.String(50), nullable=False),
        sa.Column('to_stop_id', sa.String(50), nullable=False),
        sa.Column('sequence', sa.Integer, nullable=False),
        sa.Column('distance_meters', sa.Float, nullable=True),
        sa.Column('scheduled_travel_time_seconds', sa.Integer, nullable=True),
        sa.Column('avg_travel_time_seconds', sa.Float, nullable=True),
        sa.Column('avg_speed_kmh', sa.Float, nullable=True),
        sa.Column('sample_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_gtfs_track_segments_route_id', 'gtfs_track_segments', ['route_id'])
    op.create_index('ix_gtfs_track_segments_from_stop_id', 'gtfs_track_segments', ['from_stop_id'])
    op.create_index('ix_gtfs_track_segments_to_stop_id', 'gtfs_track_segments', ['to_stop_id'])
    op.create_index('ix_track_segments_route_stops', 'gtfs_track_segments', ['route_id', 'from_stop_id', 'to_stop_id'])

    # Create segment stats table (using String for day_type and hour_range for simplicity)
    op.create_table(
        'gtfs_segment_stats',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('segment_id', sa.String(100), sa.ForeignKey('gtfs_track_segments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('day_type', sa.String(20), nullable=False),  # weekday, saturday, sunday
        sa.Column('hour_range', sa.String(20), nullable=False),  # early_morning, morning_peak, etc.
        sa.Column('avg_travel_time_seconds', sa.Float, nullable=False),
        sa.Column('min_travel_time_seconds', sa.Float, nullable=True),
        sa.Column('max_travel_time_seconds', sa.Float, nullable=True),
        sa.Column('std_deviation_seconds', sa.Float, nullable=True),
        sa.Column('sample_count', sa.Integer, default=0),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_gtfs_segment_stats_segment_id', 'gtfs_segment_stats', ['segment_id'])
    op.create_index('ix_segment_stats_lookup', 'gtfs_segment_stats', ['segment_id', 'day_type', 'hour_range'])

    # Create vehicle position history table
    op.create_table(
        'gtfs_vehicle_position_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('vehicle_id', sa.String(50), nullable=False),
        sa.Column('trip_id', sa.String(50), nullable=False),
        sa.Column('route_id', sa.String(50), nullable=True),
        sa.Column('latitude', sa.Float, nullable=False),
        sa.Column('longitude', sa.Float, nullable=False),
        sa.Column('stop_id', sa.String(50), nullable=True),
        sa.Column('current_status', sa.String(20), nullable=True),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('recorded_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_gtfs_vehicle_position_history_vehicle_id', 'gtfs_vehicle_position_history', ['vehicle_id'])
    op.create_index('ix_gtfs_vehicle_position_history_trip_id', 'gtfs_vehicle_position_history', ['trip_id'])
    op.create_index('ix_gtfs_vehicle_position_history_route_id', 'gtfs_vehicle_position_history', ['route_id'])
    op.create_index('ix_gtfs_vehicle_position_history_stop_id', 'gtfs_vehicle_position_history', ['stop_id'])
    op.create_index('ix_gtfs_vehicle_position_history_timestamp', 'gtfs_vehicle_position_history', ['timestamp'])
    op.create_index('ix_position_history_trip_time', 'gtfs_vehicle_position_history', ['trip_id', 'timestamp'])
    op.create_index('ix_position_history_vehicle_time', 'gtfs_vehicle_position_history', ['vehicle_id', 'timestamp'])
    op.create_index('ix_position_history_recorded', 'gtfs_vehicle_position_history', ['recorded_at'])


def downgrade() -> None:
    op.drop_table('gtfs_vehicle_position_history')
    op.drop_table('gtfs_segment_stats')
    op.drop_table('gtfs_track_segments')
