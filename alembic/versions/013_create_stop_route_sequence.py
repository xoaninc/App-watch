"""Create stop_route_sequence table to store stop order in routes

Revision ID: 013
Revises: 012
Create Date: 2026-01-16 01:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create table to store the sequence/position of stops in each route
    op.create_table(
        'gtfs_stop_route_sequence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stop_id', sa.String(100), sa.ForeignKey('gtfs_stops.id'), nullable=False),
        sa.Column('route_id', sa.String(100), sa.ForeignKey('gtfs_routes.id'), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),  # Index of closest point in route geometry
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stop_id', 'route_id', name='uq_stop_route_sequence'),
        sa.Index('idx_route_sequence', 'route_id', 'sequence'),
    )


def downgrade() -> None:
    # Drop the table
    op.drop_table('gtfs_stop_route_sequence')
