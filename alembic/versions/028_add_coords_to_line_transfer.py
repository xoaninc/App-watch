"""Add coordinate columns to line_transfer and create discrepancies table.

Revision ID: 028
Revises: 027
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa

revision = '028'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade():
    # Add coordinate columns to line_transfer
    op.add_column('line_transfer', sa.Column('from_lat', sa.Float(), nullable=True))
    op.add_column('line_transfer', sa.Column('from_lon', sa.Float(), nullable=True))
    op.add_column('line_transfer', sa.Column('to_lat', sa.Float(), nullable=True))
    op.add_column('line_transfer', sa.Column('to_lon', sa.Float(), nullable=True))

    # Create table for storing discrepancies for manual review
    op.create_table(
        'correspondence_discrepancies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stop_id', sa.String(100), nullable=False),
        sa.Column('stop_name', sa.String(255), nullable=True),
        sa.Column('field', sa.String(50), nullable=False),  # cor_metro, cor_cercanias, etc.
        sa.Column('value_in_db', sa.Text(), nullable=True),
        sa.Column('value_in_csv', sa.Text(), nullable=True),
        sa.Column('discrepancy_type', sa.String(50), nullable=True),  # 'missing_in_db', 'missing_in_csv', 'different'
        sa.Column('reviewed', sa.Boolean(), default=False),
        sa.Column('resolution', sa.String(50), nullable=True),  # 'keep_db', 'use_csv', 'manual'
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('ix_discrepancies_stop_id', 'correspondence_discrepancies', ['stop_id'])
    op.create_index('ix_discrepancies_reviewed', 'correspondence_discrepancies', ['reviewed'])


def downgrade():
    op.drop_index('ix_discrepancies_reviewed')
    op.drop_index('ix_discrepancies_stop_id')
    op.drop_table('correspondence_discrepancies')

    op.drop_column('line_transfer', 'to_lon')
    op.drop_column('line_transfer', 'to_lat')
    op.drop_column('line_transfer', 'from_lon')
    op.drop_column('line_transfer', 'from_lat')
