"""Create GTFS tables

Revision ID: 001
Revises:
Create Date: 2024-01-14
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agency table
    op.create_table(
        'gtfs_agencies',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('timezone', sa.String(100), nullable=False, server_default='Europe/Madrid'),
        sa.Column('lang', sa.String(10), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
    )

    # Routes table
    op.create_table(
        'gtfs_routes',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('agency_id', sa.String(100), sa.ForeignKey('gtfs_agencies.id'), nullable=False),
        sa.Column('short_name', sa.String(50), nullable=False),
        sa.Column('long_name', sa.String(255), nullable=False),
        sa.Column('route_type', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('color', sa.String(6), nullable=True),
        sa.Column('text_color', sa.String(6), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
    )

    # Stops table
    op.create_table(
        'gtfs_stops',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('zone_id', sa.String(100), nullable=True),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('location_type', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parent_station_id', sa.String(100), sa.ForeignKey('gtfs_stops.id'), nullable=True),
        sa.Column('timezone', sa.String(100), nullable=True),
        sa.Column('wheelchair_boarding', sa.Integer(), nullable=True),
        sa.Column('platform_code', sa.String(50), nullable=True),
    )

    # Calendar table
    op.create_table(
        'gtfs_calendar',
        sa.Column('service_id', sa.String(100), primary_key=True),
        sa.Column('monday', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tuesday', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('wednesday', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('thursday', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('friday', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('saturday', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sunday', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
    )

    # Calendar dates (exceptions)
    op.create_table(
        'gtfs_calendar_dates',
        sa.Column('service_id', sa.String(100), sa.ForeignKey('gtfs_calendar.service_id'), primary_key=True),
        sa.Column('date', sa.Date(), primary_key=True),
        sa.Column('exception_type', sa.Integer(), nullable=False),
    )
    op.create_index('ix_calendar_dates_date', 'gtfs_calendar_dates', ['date'])

    # Shapes table
    op.create_table(
        'gtfs_shapes',
        sa.Column('id', sa.String(100), primary_key=True),
    )

    # Shape points table
    op.create_table(
        'gtfs_shape_points',
        sa.Column('shape_id', sa.String(100), sa.ForeignKey('gtfs_shapes.id'), primary_key=True),
        sa.Column('sequence', sa.Integer(), primary_key=True),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('dist_traveled', sa.Float(), nullable=True),
    )
    op.create_index('ix_shape_points_shape_id', 'gtfs_shape_points', ['shape_id'])

    # Trips table
    op.create_table(
        'gtfs_trips',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('route_id', sa.String(100), sa.ForeignKey('gtfs_routes.id'), nullable=False),
        sa.Column('service_id', sa.String(100), sa.ForeignKey('gtfs_calendar.service_id'), nullable=False),
        sa.Column('headsign', sa.String(255), nullable=True),
        sa.Column('short_name', sa.String(100), nullable=True),
        sa.Column('direction_id', sa.Integer(), nullable=True),
        sa.Column('block_id', sa.String(100), nullable=True),
        sa.Column('shape_id', sa.String(100), nullable=True),
        sa.Column('wheelchair_accessible', sa.Integer(), nullable=True),
        sa.Column('bikes_allowed', sa.Integer(), nullable=True),
    )

    # Stop times table
    op.create_table(
        'gtfs_stop_times',
        sa.Column('trip_id', sa.String(100), sa.ForeignKey('gtfs_trips.id'), primary_key=True),
        sa.Column('stop_sequence', sa.Integer(), primary_key=True),
        sa.Column('stop_id', sa.String(100), sa.ForeignKey('gtfs_stops.id'), nullable=False),
        sa.Column('arrival_time', sa.String(10), nullable=False),
        sa.Column('departure_time', sa.String(10), nullable=False),
        sa.Column('arrival_seconds', sa.Integer(), nullable=False),
        sa.Column('departure_seconds', sa.Integer(), nullable=False),
        sa.Column('stop_headsign', sa.String(255), nullable=True),
        sa.Column('pickup_type', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('drop_off_type', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shape_dist_traveled', sa.Float(), nullable=True),
        sa.Column('timepoint', sa.Integer(), nullable=False, server_default='1'),
    )
    op.create_index('ix_stop_times_stop_id', 'gtfs_stop_times', ['stop_id'])
    op.create_index('ix_stop_times_arrival', 'gtfs_stop_times', ['arrival_seconds'])

    # Feed imports tracking table
    op.create_table(
        'gtfs_feed_imports',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('source_url', sa.String(500), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('agencies_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('routes_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('stops_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('trips_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('stop_times_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('gtfs_feed_imports')
    op.drop_table('gtfs_stop_times')
    op.drop_table('gtfs_trips')
    op.drop_table('gtfs_shape_points')
    op.drop_table('gtfs_shapes')
    op.drop_table('gtfs_calendar_dates')
    op.drop_table('gtfs_calendar')
    op.drop_table('gtfs_stops')
    op.drop_table('gtfs_routes')
    op.drop_table('gtfs_agencies')
