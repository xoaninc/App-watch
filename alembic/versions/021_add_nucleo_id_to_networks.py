"""Add nucleo_id to gtfs_networks table for route_count calculation

Revision ID: 021
Revises: 020
Create Date: 2026-01-18 04:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None

# Mapping of network codes to nucleo_ids for Cercanías networks
CERCANIAS_NUCLEO_MAPPING = {
    '10T': 10,   # Madrid
    '20T': 20,   # Asturias
    '30T': 30,   # Sevilla
    '31T': 31,   # Cádiz
    '32T': 32,   # Málaga
    '40T': 40,   # Valencia
    '41T': 41,   # Murcia/Alicante
    '51T': 50,   # Rodalies Barcelona (51->50 mapping)
    '60T': 60,   # Bilbao
    '61T': 61,   # San Sebastián
    '62T': 62,   # Santander
    '70T': 70,   # Zaragoza
    '90T': 10,   # C-9 Cotos (90->10, part of Madrid)
}


def upgrade() -> None:
    # Add nucleo_id column
    op.add_column('gtfs_networks', sa.Column('nucleo_id', sa.Integer(), nullable=True))

    # Populate nucleo_id for Cercanías networks
    for network_code, nucleo_id in CERCANIAS_NUCLEO_MAPPING.items():
        op.execute(
            f"UPDATE gtfs_networks SET nucleo_id = {nucleo_id} WHERE code = '{network_code}'"
        )


def downgrade() -> None:
    op.drop_column('gtfs_networks', 'nucleo_id')
