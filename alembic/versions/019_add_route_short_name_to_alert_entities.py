"""Add route_short_name to alert entities

Revision ID: 019
Revises: 018
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '019'
down_revision: Union[str, None] = '018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add route_short_name column to store extracted line name (C1, C5, etc.)
    op.add_column(
        'gtfs_rt_alert_entities',
        sa.Column('route_short_name', sa.String(20), nullable=True)
    )
    op.create_index(
        'ix_alert_entities_route_short_name',
        'gtfs_rt_alert_entities',
        ['route_short_name']
    )

    # Update existing entities with extracted route_short_name
    # Pattern: {nucleo}T{code}C{line} -> C{line}
    op.execute("""
        UPDATE gtfs_rt_alert_entities
        SET route_short_name = 'C' || SUBSTRING(route_id FROM 'C([0-9a-zA-Z]+)$')
        WHERE route_id IS NOT NULL
        AND route_id ~ 'C[0-9a-zA-Z]+$'
    """)


def downgrade() -> None:
    op.drop_index('ix_alert_entities_route_short_name', table_name='gtfs_rt_alert_entities')
    op.drop_column('gtfs_rt_alert_entities', 'route_short_name')
