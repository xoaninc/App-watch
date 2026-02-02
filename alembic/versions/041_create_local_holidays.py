"""Create local_holidays table for city-specific holidays

Revision ID: 041
Revises: 040
Create Date: 2026-02-01
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '041'
down_revision = '040'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create local_holidays table for city-specific holidays."""
    op.create_table(
        'local_holidays',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            'province_code',
            sa.String(5),
            sa.ForeignKey('spanish_provinces.code', ondelete='CASCADE'),
            nullable=False,
            index=True
        ),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('month', sa.Integer, nullable=False),
        sa.Column('day', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Create index for fast lookups by province
    op.create_index(
        'ix_local_holidays_province_city',
        'local_holidays',
        ['province_code', 'city']
    )


def downgrade() -> None:
    """Drop local_holidays table."""
    op.drop_index('ix_local_holidays_province_city', table_name='local_holidays')
    op.drop_table('local_holidays')
