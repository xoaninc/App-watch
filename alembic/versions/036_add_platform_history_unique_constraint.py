"""Add unique constraint to platform_history for upsert support.

This allows using ON CONFLICT DO UPDATE instead of check-then-insert
pattern, which is prone to race conditions.

Revision ID: 036_add_platform_history_unique_constraint
Revises: 035_add_query_optimization_indexes
Create Date: 2026-01-28
"""

from alembic import op

# revision identifiers
revision = '036_add_platform_history_unique_constraint'
down_revision = '035_add_query_optimization_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """Add unique constraint for upsert operations."""

    # First, delete any duplicate rows keeping only the one with highest count
    # This is needed before we can add the unique constraint
    op.execute("""
        DELETE FROM gtfs_rt_platform_history a
        USING gtfs_rt_platform_history b
        WHERE a.id < b.id
        AND a.stop_id = b.stop_id
        AND a.route_short_name = b.route_short_name
        AND a.headsign = b.headsign
        AND a.platform = b.platform
        AND a.observation_date = b.observation_date
    """)

    # Add unique constraint on the business key
    op.execute("""
        ALTER TABLE gtfs_rt_platform_history
        ADD CONSTRAINT uq_platform_history_business_key
        UNIQUE (stop_id, route_short_name, headsign, platform, observation_date)
    """)

    print("Added unique constraint uq_platform_history_business_key")


def downgrade():
    """Remove unique constraint."""
    op.execute("""
        ALTER TABLE gtfs_rt_platform_history
        DROP CONSTRAINT IF EXISTS uq_platform_history_business_key
    """)
