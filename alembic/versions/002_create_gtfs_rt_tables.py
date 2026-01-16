"""Create GTFS-RT tables

Revision ID: 002
Revises: 001
Create Date: 2026-01-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create vehicle positions table
    op.create_table(
        'gtfs_rt_vehicle_positions',
        sa.Column('vehicle_id', sa.String(50), primary_key=True),
        sa.Column('trip_id', sa.String(50), nullable=False),
        sa.Column('latitude', sa.Float, nullable=False),
        sa.Column('longitude', sa.Float, nullable=False),
        sa.Column('current_status', sa.Enum('INCOMING_AT', 'STOPPED_AT', 'IN_TRANSIT_TO', name='vehiclestatusenum'), nullable=False),
        sa.Column('stop_id', sa.String(50), nullable=True),
        sa.Column('label', sa.String(100), nullable=True),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_gtfs_rt_vehicle_positions_trip_id', 'gtfs_rt_vehicle_positions', ['trip_id'])
    op.create_index('ix_gtfs_rt_vehicle_positions_stop_id', 'gtfs_rt_vehicle_positions', ['stop_id'])
    op.create_index('ix_vehicle_positions_trip_stop', 'gtfs_rt_vehicle_positions', ['trip_id', 'stop_id'])

    # Create trip updates table
    op.create_table(
        'gtfs_rt_trip_updates',
        sa.Column('trip_id', sa.String(50), primary_key=True),
        sa.Column('delay', sa.Integer, nullable=False, default=0),
        sa.Column('vehicle_id', sa.String(50), nullable=True),
        sa.Column('wheelchair_accessible', sa.Boolean, nullable=True),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_trip_updates_delay', 'gtfs_rt_trip_updates', ['delay'])

    # Create stop time updates table
    op.create_table(
        'gtfs_rt_stop_time_updates',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('trip_id', sa.String(50), sa.ForeignKey('gtfs_rt_trip_updates.trip_id', ondelete='CASCADE'), nullable=False),
        sa.Column('stop_id', sa.String(50), nullable=False),
        sa.Column('arrival_delay', sa.Integer, nullable=True),
        sa.Column('arrival_time', sa.DateTime, nullable=True),
        sa.Column('departure_delay', sa.Integer, nullable=True),
        sa.Column('departure_time', sa.DateTime, nullable=True),
    )
    op.create_index('ix_gtfs_rt_stop_time_updates_trip_id', 'gtfs_rt_stop_time_updates', ['trip_id'])
    op.create_index('ix_gtfs_rt_stop_time_updates_stop_id', 'gtfs_rt_stop_time_updates', ['stop_id'])
    op.create_index('ix_stop_time_updates_trip_stop', 'gtfs_rt_stop_time_updates', ['trip_id', 'stop_id'])


def downgrade() -> None:
    op.drop_table('gtfs_rt_stop_time_updates')
    op.drop_table('gtfs_rt_trip_updates')
    op.drop_table('gtfs_rt_vehicle_positions')
    op.execute('DROP TYPE IF EXISTS vehiclestatusenum')
