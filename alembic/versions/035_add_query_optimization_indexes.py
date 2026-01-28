"""Add indexes for API query optimization.

These indexes optimize the most frequent queries:
- Departures endpoint (1000+ requests/day)
- Routes filtering and ordering
- Calendar date filtering
- Platform history lookups
- Real-time updates lookups

Based on query analysis of:
- adapters/http/api/gtfs/routers/query_router.py
- src/gtfs_bc/realtime/infrastructure/services/estimated_positions.py

Revision ID: 035_add_query_optimization_indexes
Revises: 034_add_walking_shape_to_correspondence
Create Date: 2026-01-28
"""

from alembic import op

# revision identifiers
revision = '035_add_query_optimization_indexes'
down_revision = '034_add_walking_shape_to_correspondence'
branch_labels = None
depends_on = None


def upgrade():
    """Add indexes for API query optimization."""

    # =================================================================
    # CRITICAL INDEXES (High impact, high frequency)
    # =================================================================

    # 1. Composite index for departures query - MOST IMPORTANT
    # Covers: stop_id filtering + departure_seconds range + trip_id join
    # Used in: GET /stops/{stop_id}/departures (1000+ times/day)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_stop_times_stop_departure_trip
        ON gtfs_stop_times (stop_id, departure_seconds, trip_id)
    """)

    # 2. Index for routes filtering + ordering
    # Covers: WHERE network_id IN (...) ORDER BY short_name
    # Used in: GET /routes, GET /networks/{code} (100+ times/day)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_routes_network_short_name
        ON gtfs_routes (network_id, short_name)
    """)

    # 3. Index for route frequency lookups
    # Covers: WHERE route_id = ? AND day_type = ? AND start_time <= ?
    # Used in: Metro/static departures frequency calculation (500+ times/day)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_route_frequency_route_day_time
        ON gtfs_route_frequency (route_id, day_type, start_time)
    """)

    # 4. Index for platform history (without headsign fallback)
    # Covers: WHERE stop_id = ? AND route_short_name = ? AND observation_date = ?
    # Used in: Platform prediction fallback (100+ times/day)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_platform_history_stop_route_date
        ON gtfs_rt_platform_history (stop_id, route_short_name, observation_date)
    """)

    # 5. Index for real-time stop updates by stop+trip
    # Covers: WHERE stop_id = ? AND trip_id IN (...)
    # Used in: Delay lookups per stop (100+ times/day)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_stop_time_updates_stop_trip
        ON gtfs_rt_stop_time_updates (stop_id, trip_id)
    """)

    # =================================================================
    # IMPORTANT INDEXES (Medium impact, high frequency)
    # =================================================================

    # 6. Index for trips by route+service
    # Covers: WHERE route_id = ? AND service_id IN (...)
    # Used in: Estimated positions, operating hours (50+ times/day)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_trips_route_service
        ON gtfs_trips (route_id, service_id)
    """)

    # 7. Index for stop route sequence reverse lookup
    # Covers: WHERE stop_id IN (...) - find routes serving a stop
    # Used in: Departures route filtering (100+ times/day)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_stop_route_sequence_stop
        ON gtfs_stop_route_sequence (stop_id, route_id, sequence)
    """)

    # 8. Index for calendar date range filtering
    # Covers: WHERE start_date <= ? AND end_date >= ?
    # Used in: Active service_ids calculation (1000+ times/day)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_calendar_date_range
        ON gtfs_calendar (start_date, end_date)
    """)

    # 9. Index for calendar dates with exception type
    # Covers: WHERE date = ? AND exception_type = ?
    # Used in: Service exceptions lookup (1000+ times/day)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_calendar_dates_date_exception
        ON gtfs_calendar_dates (date, exception_type)
    """)

    # 10. Index for stops by location type and parent
    # Covers: WHERE location_type = 1 OR parent_station_id IS NULL
    # Used in: Station filtering in departures (100+ times/day)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_stops_location_parent
        ON gtfs_stops (location_type, parent_station_id)
    """)

    print("Created 10 query optimization indexes")


def downgrade():
    """Remove query optimization indexes."""
    op.execute("DROP INDEX IF EXISTS ix_stop_times_stop_departure_trip")
    op.execute("DROP INDEX IF EXISTS ix_routes_network_short_name")
    op.execute("DROP INDEX IF EXISTS ix_route_frequency_route_day_time")
    op.execute("DROP INDEX IF EXISTS ix_platform_history_stop_route_date")
    op.execute("DROP INDEX IF EXISTS ix_stop_time_updates_stop_trip")
    op.execute("DROP INDEX IF EXISTS ix_trips_route_service")
    op.execute("DROP INDEX IF EXISTS ix_stop_route_sequence_stop")
    op.execute("DROP INDEX IF EXISTS ix_calendar_date_range")
    op.execute("DROP INDEX IF EXISTS ix_calendar_dates_date_exception")
    op.execute("DROP INDEX IF EXISTS ix_stops_location_parent")
