"""Add nucleo mapping to spanish_provinces table

Revision ID: 011
Revises: 010
Create Date: 2026-01-16

This migration adds nucleo_id column to spanish_provinces table to map
each province to its corresponding Renfe regional network (núcleo).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nucleo_id column to spanish_provinces table."""
    op.add_column('spanish_provinces', sa.Column('nucleo_id', sa.Integer, nullable=True))
    op.add_column('spanish_provinces', sa.Column('nucleo_name', sa.String(100), nullable=True))

    # Create index for efficient lookups
    op.create_index('idx_provinces_nucleo_id', 'spanish_provinces', ['nucleo_id'])
    op.create_index('idx_provinces_nucleo_name', 'spanish_provinces', ['nucleo_name'])

    # Add foreign key constraint to gtfs_nucleos
    op.create_foreign_key(
        'fk_provinces_nucleo',
        'spanish_provinces',
        'gtfs_nucleos',
        ['nucleo_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Remove nucleo mapping from spanish_provinces table."""
    # Drop foreign key
    op.drop_constraint('fk_provinces_nucleo', 'spanish_provinces', type_='foreignkey')

    # Drop indexes
    op.drop_index('idx_provinces_nucleo_id', table_name='spanish_provinces')
    op.drop_index('idx_provinces_nucleo_name', table_name='spanish_provinces')

    # Drop columns
    op.drop_column('spanish_provinces', 'nucleo_id')
    op.drop_column('spanish_provinces', 'nucleo_name')
