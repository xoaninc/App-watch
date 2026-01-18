"""Expand color columns to support # prefix.

Revision ID: 022
Revises: 021
Create Date: 2026-01-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade():
    """Expand color columns from VARCHAR(6) to VARCHAR(7) to support # prefix."""
    # Routes text_color
    op.alter_column('gtfs_routes', 'text_color',
                    existing_type=sa.VARCHAR(length=6),
                    type_=sa.VARCHAR(length=7),
                    existing_nullable=True)

    # Networks color and text_color
    op.alter_column('gtfs_networks', 'color',
                    existing_type=sa.VARCHAR(length=6),
                    type_=sa.VARCHAR(length=7),
                    existing_nullable=True)

    op.alter_column('gtfs_networks', 'text_color',
                    existing_type=sa.VARCHAR(length=6),
                    type_=sa.VARCHAR(length=7),
                    existing_nullable=True)


def downgrade():
    """Revert color columns to VARCHAR(6)."""
    op.alter_column('gtfs_networks', 'text_color',
                    existing_type=sa.VARCHAR(length=7),
                    type_=sa.VARCHAR(length=6),
                    existing_nullable=True)

    op.alter_column('gtfs_networks', 'color',
                    existing_type=sa.VARCHAR(length=7),
                    type_=sa.VARCHAR(length=6),
                    existing_nullable=True)

    op.alter_column('gtfs_routes', 'text_color',
                    existing_type=sa.VARCHAR(length=7),
                    type_=sa.VARCHAR(length=6),
                    existing_nullable=True)
