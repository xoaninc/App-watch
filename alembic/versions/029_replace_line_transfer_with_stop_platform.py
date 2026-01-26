"""Replace line_transfer with stop_platform table.

line_transfer was designed for transfer times between stops, but the new
requirement is to store platform coordinates per line at each stop.

Revision ID: 029
Revises: 028
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa

revision = '029'
down_revision = '028'
branch_labels = None
depends_on = None


def upgrade():
    # Drop line_transfer table and its indexes
    op.drop_index('ix_line_transfer_from_to', table_name='line_transfer')
    op.drop_index('ix_line_transfer_network', table_name='line_transfer')
    op.drop_index('ix_line_transfer_to_stop', table_name='line_transfer')
    op.drop_index('ix_line_transfer_from_stop', table_name='line_transfer')
    op.drop_table('line_transfer')

    # Drop correspondence_discrepancies table (from migration 028)
    op.drop_table('correspondence_discrepancies')

    # Create new stop_platform table
    op.create_table(
        'stop_platform',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stop_id', sa.String(100), nullable=False),
        sa.Column('line', sa.String(50), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('source', sa.String(50), nullable=True),  # 'gtfs', 'osm', 'manual'
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stop_id', 'line', name='uq_stop_platform_stop_line')
    )

    # Create indexes
    op.create_index('ix_stop_platform_stop_id', 'stop_platform', ['stop_id'])
    op.create_index('ix_stop_platform_line', 'stop_platform', ['line'])


def downgrade():
    # Drop stop_platform
    op.drop_index('ix_stop_platform_line', table_name='stop_platform')
    op.drop_index('ix_stop_platform_stop_id', table_name='stop_platform')
    op.drop_table('stop_platform')

    # Recreate correspondence_discrepancies
    op.create_table(
        'correspondence_discrepancies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stop_id', sa.String(100), nullable=False),
        sa.Column('stop_name', sa.String(255), nullable=True),
        sa.Column('field', sa.String(50), nullable=False),
        sa.Column('value_in_db', sa.Text(), nullable=True),
        sa.Column('value_in_csv', sa.Text(), nullable=True),
        sa.Column('discrepancy_type', sa.String(50), nullable=True),
        sa.Column('reviewed', sa.Boolean(), default=False),
        sa.Column('resolution', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # Recreate line_transfer
    op.create_table(
        'line_transfer',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('from_stop_id', sa.String(100), nullable=False),
        sa.Column('to_stop_id', sa.String(100), nullable=False),
        sa.Column('from_route_id', sa.String(100), nullable=True),
        sa.Column('to_route_id', sa.String(100), nullable=True),
        sa.Column('from_lat', sa.Float(), nullable=True),
        sa.Column('from_lon', sa.Float(), nullable=True),
        sa.Column('to_lat', sa.Float(), nullable=True),
        sa.Column('to_lon', sa.Float(), nullable=True),
        sa.Column('transfer_type', sa.Integer(), nullable=False, default=0),
        sa.Column('min_transfer_time', sa.Integer(), nullable=True),
        sa.Column('from_stop_name', sa.String(255), nullable=True),
        sa.Column('to_stop_name', sa.String(255), nullable=True),
        sa.Column('from_line', sa.String(50), nullable=True),
        sa.Column('to_line', sa.String(50), nullable=True),
        sa.Column('network_id', sa.String(20), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('exit_name', sa.String(255), nullable=True),
        sa.Column('source', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_line_transfer_from_stop', 'line_transfer', ['from_stop_id'])
    op.create_index('ix_line_transfer_to_stop', 'line_transfer', ['to_stop_id'])
    op.create_index('ix_line_transfer_network', 'line_transfer', ['network_id'])
    op.create_index('ix_line_transfer_from_to', 'line_transfer', ['from_stop_id', 'to_stop_id'])
