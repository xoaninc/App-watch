"""Add cor_ml and cor_cercanias columns to gtfs_stops.

Revision ID: 027_add_correspondence_columns
Revises: 026_create_line_transfer_table
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa


revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade():
    # Add correspondence columns for Metro Ligero and Cercanías
    op.add_column('gtfs_stops', sa.Column('cor_ml', sa.Text(), nullable=True))
    op.add_column('gtfs_stops', sa.Column('cor_cercanias', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('gtfs_stops', 'cor_cercanias')
    op.drop_column('gtfs_stops', 'cor_ml')
