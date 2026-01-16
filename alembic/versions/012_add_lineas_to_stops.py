"""Add lineas field to gtfs_stops table

Revision ID: 012
Revises: 011
Create Date: 2026-01-16 01:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add lineas column to store lines serving each stop
    op.add_column('gtfs_stops', sa.Column('lineas', sa.String(500), nullable=True))


def downgrade() -> None:
    # Remove lineas column
    op.drop_column('gtfs_stops', 'lineas')
