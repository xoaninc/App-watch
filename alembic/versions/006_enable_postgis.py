"""Enable PostGIS extension

Revision ID: 006
Revises: 005
Create Date: 2026-01-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable PostGIS extension if available."""
    # Check if PostGIS is available before trying to create it
    connection = op.get_bind()
    result = connection.execute(text(
        "SELECT * FROM pg_available_extensions WHERE name = 'postgis'"
    ))
    if result.fetchone():
        op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    else:
        print("PostGIS not available, skipping extension creation")


def downgrade() -> None:
    """Disable PostGIS extension if exists."""
    op.execute('DROP EXTENSION IF EXISTS postgis')
