"""Create line_transfer table for interchange transfer times.

Revision ID: 026
Revises: 025
Create Date: 2026-01-21
"""
from alembic import op
import sqlalchemy as sa

revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'line_transfer',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('from_stop_id', sa.String(100), nullable=False),
        sa.Column('to_stop_id', sa.String(100), nullable=False),
        sa.Column('from_route_id', sa.String(100), nullable=True),
        sa.Column('to_route_id', sa.String(100), nullable=True),
        sa.Column('transfer_type', sa.Integer(), nullable=False, default=0),
        sa.Column('min_transfer_time', sa.Integer(), nullable=True),  # seconds
        sa.Column('from_stop_name', sa.String(255), nullable=True),
        sa.Column('to_stop_name', sa.String(255), nullable=True),
        sa.Column('from_line', sa.String(50), nullable=True),  # e.g., "L1", "C4a"
        sa.Column('to_line', sa.String(50), nullable=True),
        sa.Column('network_id', sa.String(20), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),  # Walking instructions
        sa.Column('exit_name', sa.String(255), nullable=True),  # Exit to use
        sa.Column('source', sa.String(50), nullable=True),  # 'gtfs', 'manual', etc.
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('ix_line_transfer_from_stop', 'line_transfer', ['from_stop_id'])
    op.create_index('ix_line_transfer_to_stop', 'line_transfer', ['to_stop_id'])
    op.create_index('ix_line_transfer_network', 'line_transfer', ['network_id'])
    op.create_index('ix_line_transfer_from_to', 'line_transfer', ['from_stop_id', 'to_stop_id'])


def downgrade():
    op.drop_index('ix_line_transfer_from_to')
    op.drop_index('ix_line_transfer_network')
    op.drop_index('ix_line_transfer_to_stop')
    op.drop_index('ix_line_transfer_from_stop')
    op.drop_table('line_transfer')
