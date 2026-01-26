"""Rename line to lines in stop_platform table.

Allows grouping multiple lines that share the same platform coordinates.
Example: "C2, C3, C4a, C4b" for lines sharing the same platform.

Revision ID: 030
Revises: 029
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa

revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade():
    # Rename column line to lines
    op.alter_column('stop_platform', 'line', new_column_name='lines')

    # Increase size to accommodate multiple lines
    op.alter_column('stop_platform', 'lines', type_=sa.String(255))

    # Drop old unique constraint and create new one
    op.drop_constraint('uq_stop_platform_stop_line', 'stop_platform', type_='unique')
    op.create_unique_constraint('uq_stop_platform_stop_lines', 'stop_platform', ['stop_id', 'lines'])

    # Drop old index and create new one
    op.drop_index('ix_stop_platform_line', table_name='stop_platform')
    op.create_index('ix_stop_platform_lines', 'stop_platform', ['lines'])


def downgrade():
    # Revert index
    op.drop_index('ix_stop_platform_lines', table_name='stop_platform')
    op.create_index('ix_stop_platform_line', 'stop_platform', ['lines'])

    # Revert unique constraint
    op.drop_constraint('uq_stop_platform_stop_lines', 'stop_platform', type_='unique')
    op.create_unique_constraint('uq_stop_platform_stop_line', 'stop_platform', ['stop_id', 'lines'])

    # Revert column type and name
    op.alter_column('stop_platform', 'lines', type_=sa.String(50))
    op.alter_column('stop_platform', 'lines', new_column_name='line')
