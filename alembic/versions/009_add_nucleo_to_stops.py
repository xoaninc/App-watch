"""Add nucleo fields to gtfs_stops table

Revision ID: 009
Revises: 008
Create Date: 2026-01-16

This migration adds nucleo-related fields and Renfe station metadata
to the gtfs_stops table, allowing stops to be associated with regional
networks and enriched with additional amenity information.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nucleo fields to gtfs_stops table."""
    # Add nucleo reference columns
    op.add_column('gtfs_stops', sa.Column('nucleo_id', sa.Integer, nullable=True))
    op.add_column('gtfs_stops', sa.Column('nucleo_name', sa.String(100), nullable=True))

    # Add Renfe station metadata
    op.add_column('gtfs_stops', sa.Column('renfe_codigo_estacion', sa.Integer, nullable=True))
    op.add_column('gtfs_stops', sa.Column('color', sa.String(50), nullable=True))
    op.add_column('gtfs_stops', sa.Column('parking_bicis', sa.Text, nullable=True))
    op.add_column('gtfs_stops', sa.Column('accesibilidad', sa.String(100), nullable=True))
    op.add_column('gtfs_stops', sa.Column('cor_bus', sa.Text, nullable=True))
    op.add_column('gtfs_stops', sa.Column('cor_metro', sa.Text, nullable=True))

    # Create indexes for efficient querying
    op.create_index('idx_stops_nucleo_id', 'gtfs_stops', ['nucleo_id'])
    op.create_index('idx_stops_nucleo_name', 'gtfs_stops', ['nucleo_name'])
    op.create_index('idx_stops_renfe_codigo', 'gtfs_stops', ['renfe_codigo_estacion'])

    # Add foreign key constraint to gtfs_nucleos
    op.create_foreign_key(
        'fk_stops_nucleo',
        'gtfs_stops',
        'gtfs_nucleos',
        ['nucleo_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Remove nucleo fields from gtfs_stops table."""
    # Drop foreign key
    op.drop_constraint('fk_stops_nucleo', 'gtfs_stops', type_='foreignkey')

    # Drop indexes
    op.drop_index('idx_stops_nucleo_id', table_name='gtfs_stops')
    op.drop_index('idx_stops_nucleo_name', table_name='gtfs_stops')
    op.drop_index('idx_stops_renfe_codigo', table_name='gtfs_stops')

    # Drop columns
    op.drop_column('gtfs_stops', 'nucleo_id')
    op.drop_column('gtfs_stops', 'nucleo_name')
    op.drop_column('gtfs_stops', 'renfe_codigo_estacion')
    op.drop_column('gtfs_stops', 'color')
    op.drop_column('gtfs_stops', 'parking_bicis')
    op.drop_column('gtfs_stops', 'accesibilidad')
    op.drop_column('gtfs_stops', 'cor_bus')
    op.drop_column('gtfs_stops', 'cor_metro')
