"""Enable PostGIS extension

Revision ID: 006
Revises: 005
Create Date: 2026-01-16
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable PostGIS extension."""
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')


def downgrade() -> None:
    """Disable PostGIS extension."""
    op.execute('DROP EXTENSION IF EXISTS postgis')
