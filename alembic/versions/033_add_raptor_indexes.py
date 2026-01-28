"""Add indexes for RAPTOR route planner optimization.

These indexes improve query performance for:
- Loading trips by service_id (calendar filtering)
- Loading stop_times by trip_id (building trip data)
- Transfer lookups (stop_correspondence)

Revision ID: 033_add_raptor_indexes
Revises: 032_add_color_description_to_platform
Create Date: 2026-01-27
"""

from alembic import op

# revision identifiers
revision = '033_add_raptor_indexes'
down_revision = '032_add_color_description_to_platform'
branch_labels = None
depends_on = None


def upgrade():
    """Add indexes for RAPTOR performance."""

    # Index on trips.service_id for calendar filtering
    # RAPTOR filters trips by active service_ids based on calendar
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_trips_service_id
        ON gtfs_trips (service_id)
    """)

    # Composite index on stop_times for trip loading
    # RAPTOR loads all stop_times for a trip ordered by sequence
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_stop_times_trip_sequence
        ON gtfs_stop_times (trip_id, stop_sequence)
    """)

    # Index on stop_correspondence for transfer lookups
    # RAPTOR loads transfers by from_stop_id
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_stop_correspondence_from_stop
        ON stop_correspondence (from_stop_id)
    """)

    # Index on calendar dates for exception lookups
    # RAPTOR checks calendar_dates for service exceptions
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_calendar_dates_service
        ON gtfs_calendar_dates (service_id)
    """)

    # Index on stop_times.stop_id for departures queries
    # Already exists as ix_stop_times_stop_id, but add composite for better perf
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_stop_times_stop_departure
        ON gtfs_stop_times (stop_id, departure_seconds)
    """)

    print("Created 5 RAPTOR optimization indexes")


def downgrade():
    """Remove RAPTOR indexes."""
    op.execute("DROP INDEX IF EXISTS ix_trips_service_id")
    op.execute("DROP INDEX IF EXISTS ix_stop_times_trip_sequence")
    op.execute("DROP INDEX IF EXISTS ix_stop_correspondence_from_stop")
    op.execute("DROP INDEX IF EXISTS ix_calendar_dates_service")
    op.execute("DROP INDEX IF EXISTS ix_stop_times_stop_departure")
