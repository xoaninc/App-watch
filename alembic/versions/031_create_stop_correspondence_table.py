"""Create stop_correspondence table for walking connections between different stations.

Examples:
- Acacias (L5) ↔ Embajadores (L3, C5)
- Noviciado (L2) ↔ Plaza de España (L3, L10)

Revision ID: 031
Revises: 030
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa

revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'stop_correspondence',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('from_stop_id', sa.String(100), nullable=False),
        sa.Column('to_stop_id', sa.String(100), nullable=False),
        sa.Column('distance_m', sa.Integer(), nullable=True),  # Walking distance in meters
        sa.Column('walk_time_s', sa.Integer(), nullable=True),  # Estimated walk time in seconds
        sa.Column('source', sa.String(50), nullable=True),  # 'manual', 'gtfs', 'proximity'
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_stop_id', 'to_stop_id', name='uq_stop_correspondence')
    )

    op.create_index('ix_stop_correspondence_from', 'stop_correspondence', ['from_stop_id'])
    op.create_index('ix_stop_correspondence_to', 'stop_correspondence', ['to_stop_id'])


def downgrade():
    op.drop_index('ix_stop_correspondence_to')
    op.drop_index('ix_stop_correspondence_from')
    op.drop_table('stop_correspondence')
