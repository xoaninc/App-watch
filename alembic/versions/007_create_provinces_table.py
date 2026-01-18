"""Create provinces table with PostGIS geometry

Revision ID: 007
Revises: 006
Create Date: 2026-01-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def _postgis_available(connection):
    """Check if PostGIS extension is installed."""
    result = connection.execute(text(
        "SELECT 1 FROM pg_extension WHERE extname = 'postgis'"
    ))
    return result.fetchone() is not None


def upgrade() -> None:
    """Create spanish_provinces table with geometry column."""
    # Create provinces table
    op.create_table(
        'spanish_provinces',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('code', sa.String(5), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False, index=True),
        sa.Column('name_official', sa.String(100), nullable=True),
        sa.Column('autonomous_community', sa.String(100), nullable=True),
        sa.Column('capital', sa.String(100), nullable=True),
        sa.Column('iso_code', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    connection = op.get_bind()
    if _postgis_available(connection):
        # Add geometry column using PostGIS function
        # SRID 4326 = WGS84 (standard lat/lon coordinate system)
        op.execute(
            text("""
                SELECT AddGeometryColumn(
                    'spanish_provinces',
                    'geometry',
                    4326,
                    'MULTIPOLYGON',
                    2
                )
            """)
        )

        # Create spatial index for fast point-in-polygon queries
        op.execute(
            text("""
                CREATE INDEX idx_spanish_provinces_geometry
                ON spanish_provinces
                USING GIST (geometry)
            """)
        )
    else:
        print("PostGIS not available, skipping geometry column for spanish_provinces")


def downgrade() -> None:
    """Drop spanish_provinces table."""
    op.drop_table('spanish_provinces')
