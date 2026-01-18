"""Add nucleo fields and geometry to gtfs_routes table

Revision ID: 010
Revises: 009
Create Date: 2026-01-16

This migration adds nucleo-related fields and route geometry to the gtfs_routes
table, enabling routes to be associated with regional networks and storing their
actual geographic paths as LineString geometries.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def _postgis_available(connection):
    """Check if PostGIS extension is installed."""
    result = connection.execute(text(
        "SELECT 1 FROM pg_extension WHERE extname = 'postgis'"
    ))
    return result.fetchone() is not None


def upgrade() -> None:
    """Add nucleo fields and geometry to gtfs_routes table."""
    # Add nucleo reference columns
    op.add_column('gtfs_routes', sa.Column('nucleo_id', sa.Integer, nullable=True))
    op.add_column('gtfs_routes', sa.Column('nucleo_name', sa.String(100), nullable=True))

    # Add Renfe line metadata
    op.add_column('gtfs_routes', sa.Column('renfe_idlinea', sa.Integer, nullable=True))

    # Create indexes for efficient querying
    op.create_index('idx_routes_nucleo_id', 'gtfs_routes', ['nucleo_id'])
    op.create_index('idx_routes_nucleo_name', 'gtfs_routes', ['nucleo_name'])
    op.create_index('idx_routes_renfe_idlinea', 'gtfs_routes', ['renfe_idlinea'])

    # Add foreign key constraint to gtfs_nucleos
    op.create_foreign_key(
        'fk_routes_nucleo',
        'gtfs_routes',
        'gtfs_nucleos',
        ['nucleo_id'],
        ['id'],
        ondelete='SET NULL'
    )

    connection = op.get_bind()
    if _postgis_available(connection):
        # Add geometry column using PostGIS function
        # SRID 4326 = WGS84 (standard lat/lon coordinate system)
        op.execute(
            text("""
                SELECT AddGeometryColumn(
                    'gtfs_routes',
                    'geometry',
                    4326,
                    'LINESTRING',
                    2
                )
            """)
        )

        # Create spatial index for geometry queries
        op.execute(
            text("""
                CREATE INDEX idx_routes_geometry
                ON gtfs_routes
                USING GIST (geometry)
            """)
        )
    else:
        print("PostGIS not available, skipping geometry column for gtfs_routes")


def downgrade() -> None:
    """Remove nucleo fields and geometry from gtfs_routes table."""
    # Drop foreign key
    op.drop_constraint('fk_routes_nucleo', 'gtfs_routes', type_='foreignkey')

    # Drop indexes
    op.drop_index('idx_routes_nucleo_id', table_name='gtfs_routes')
    op.drop_index('idx_routes_nucleo_name', table_name='gtfs_routes')
    op.drop_index('idx_routes_renfe_idlinea', table_name='gtfs_routes')

    connection = op.get_bind()
    if _postgis_available(connection):
        # Drop spatial index
        op.drop_index('idx_routes_geometry', table_name='gtfs_routes')

        # Drop geometry column
        op.execute(
            text("""
                SELECT DropGeometryColumn('gtfs_routes', 'geometry')
            """)
        )

    # Drop columns
    op.drop_column('gtfs_routes', 'nucleo_id')
    op.drop_column('gtfs_routes', 'nucleo_name')
    op.drop_column('gtfs_routes', 'renfe_idlinea')
