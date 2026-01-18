"""Add cor_tranvia field to gtfs_stops table

Revision ID: 020
Revises: 019
Create Date: 2026-01-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add cor_tranvia column for tram correspondences
    op.add_column('gtfs_stops', sa.Column('cor_tranvia', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove cor_tranvia column
    op.drop_column('gtfs_stops', 'cor_tranvia')
