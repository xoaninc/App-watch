"""Add RENFE_ prefix to RT data stop_ids

This migration adds the RENFE_ prefix to all stop_id values in the
GTFS-RT tables that don't already have it. This is needed to match
the static GTFS data which uses the RENFE_ prefix.

Revision ID: 040
Revises: 039
"""

from alembic import op


# revision identifiers
revision = '040'
down_revision = '039'
branch_labels = None
depends_on = None


def upgrade():
    """Add RENFE_ prefix to stop_ids that don't have it."""

    # Update gtfs_rt_vehicle_positions
    op.execute("""
        UPDATE gtfs_rt_vehicle_positions
        SET stop_id = 'RENFE_' || stop_id
        WHERE stop_id IS NOT NULL
          AND stop_id != ''
          AND stop_id NOT LIKE 'RENFE_%'
          AND stop_id NOT LIKE 'FGC_%'
          AND stop_id NOT LIKE 'EUSKOTREN_%'
          AND stop_id NOT LIKE 'METRO_BILBAO_%'
          AND stop_id NOT LIKE 'TMB_%'
          AND stop_id NOT LIKE 'TRAM_%'
    """)
    print("Updated gtfs_rt_vehicle_positions with RENFE_ prefix")

    # Update gtfs_rt_stop_time_updates
    op.execute("""
        UPDATE gtfs_rt_stop_time_updates
        SET stop_id = 'RENFE_' || stop_id
        WHERE stop_id IS NOT NULL
          AND stop_id != ''
          AND stop_id NOT LIKE 'RENFE_%'
          AND stop_id NOT LIKE 'FGC_%'
          AND stop_id NOT LIKE 'EUSKOTREN_%'
          AND stop_id NOT LIKE 'METRO_BILBAO_%'
          AND stop_id NOT LIKE 'TMB_%'
          AND stop_id NOT LIKE 'TRAM_%'
    """)
    print("Updated gtfs_rt_stop_time_updates with RENFE_ prefix")

    # Update gtfs_rt_platform_history
    op.execute("""
        UPDATE gtfs_rt_platform_history
        SET stop_id = 'RENFE_' || stop_id
        WHERE stop_id IS NOT NULL
          AND stop_id != ''
          AND stop_id NOT LIKE 'RENFE_%'
          AND stop_id NOT LIKE 'FGC_%'
          AND stop_id NOT LIKE 'EUSKOTREN_%'
          AND stop_id NOT LIKE 'METRO_BILBAO_%'
          AND stop_id NOT LIKE 'TMB_%'
          AND stop_id NOT LIKE 'TRAM_%'
    """)
    print("Updated gtfs_rt_platform_history with RENFE_ prefix")

    # Update gtfs_rt_alert_entities
    op.execute("""
        UPDATE gtfs_rt_alert_entities
        SET stop_id = 'RENFE_' || stop_id
        WHERE stop_id IS NOT NULL
          AND stop_id != ''
          AND stop_id NOT LIKE 'RENFE_%'
          AND stop_id NOT LIKE 'FGC_%'
          AND stop_id NOT LIKE 'EUSKOTREN_%'
          AND stop_id NOT LIKE 'METRO_BILBAO_%'
          AND stop_id NOT LIKE 'TMB_%'
          AND stop_id NOT LIKE 'TRAM_%'
    """)
    print("Updated gtfs_rt_alert_entities with RENFE_ prefix")


def downgrade():
    """Remove RENFE_ prefix from stop_ids."""

    # Remove prefix from gtfs_rt_vehicle_positions
    op.execute("""
        UPDATE gtfs_rt_vehicle_positions
        SET stop_id = SUBSTRING(stop_id FROM 7)
        WHERE stop_id LIKE 'RENFE_%'
    """)

    # Remove prefix from gtfs_rt_stop_time_updates
    op.execute("""
        UPDATE gtfs_rt_stop_time_updates
        SET stop_id = SUBSTRING(stop_id FROM 7)
        WHERE stop_id LIKE 'RENFE_%'
    """)

    # Remove prefix from gtfs_rt_platform_history
    op.execute("""
        UPDATE gtfs_rt_platform_history
        SET stop_id = SUBSTRING(stop_id FROM 7)
        WHERE stop_id LIKE 'RENFE_%'
    """)

    # Remove prefix from gtfs_rt_alert_entities
    op.execute("""
        UPDATE gtfs_rt_alert_entities
        SET stop_id = SUBSTRING(stop_id FROM 7)
        WHERE stop_id LIKE 'RENFE_%'
    """)
