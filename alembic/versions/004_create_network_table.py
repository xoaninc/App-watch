"""Create network metadata table

Revision ID: 004
Revises: 003
Create Date: 2026-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Network seed data for Spanish Cercanías
NETWORK_DATA = [
    {
        "code": "10T",
        "name": "Cercanías Madrid",
        "city": "Madrid",
        "region": "Comunidad de Madrid",
        "color": "75B6E0",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_Madrid",
        "description": "Red de cercanías de Madrid, la más extensa de España.",
    },
    {
        "code": "20T",
        "name": "Cercanías Asturias",
        "city": "Oviedo",
        "region": "Asturias",
        "color": "EC3541",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_Asturias",
        "description": "Red de cercanías del Principado de Asturias.",
    },
    {
        "code": "30T",
        "name": "Cercanías Sevilla",
        "city": "Sevilla",
        "region": "Andalucía",
        "color": "78B4E1",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_Sevilla",
        "description": "Red de cercanías del área metropolitana de Sevilla.",
    },
    {
        "code": "31T",
        "name": "Cercanías Cádiz",
        "city": "Cádiz",
        "region": "Andalucía",
        "color": "D7001E",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_C%C3%A1diz",
        "description": "Red de cercanías de la Bahía de Cádiz.",
    },
    {
        "code": "32T",
        "name": "Cercanías Málaga",
        "city": "Málaga",
        "region": "Andalucía",
        "color": "4A8CCC",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_M%C3%A1laga",
        "description": "Red de cercanías de la Costa del Sol.",
    },
    {
        "code": "40T",
        "name": "Cercanías Valencia",
        "city": "Valencia",
        "region": "Comunidad Valenciana",
        "color": "7AB3DE",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_Valencia",
        "description": "Red de cercanías del área metropolitana de Valencia.",
    },
    {
        "code": "41T",
        "name": "Cercanías Murcia/Alicante",
        "city": "Murcia",
        "region": "Región de Murcia / Comunidad Valenciana",
        "color": "73B6E0",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_Murcia/Alicante",
        "description": "Red de cercanías de Murcia y Alicante.",
    },
    {
        "code": "51T",
        "name": "Rodalies Barcelona",
        "city": "Barcelona",
        "region": "Cataluña",
        "color": "FF0000",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Rodalies_de_Catalunya",
        "description": "Red de cercanías de Cataluña, operada por Rodalies de Catalunya.",
    },
    {
        "code": "60T",
        "name": "Cercanías Bilbao",
        "city": "Bilbao",
        "region": "País Vasco",
        "color": "D7001E",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_Bilbao",
        "description": "Red de cercanías del área metropolitana de Bilbao.",
    },
    {
        "code": "61T",
        "name": "Cercanías San Sebastián",
        "city": "San Sebastián",
        "region": "País Vasco",
        "color": "DA001C",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_San_Sebasti%C3%A1n",
        "description": "Red de cercanías del área de Donostia-San Sebastián.",
    },
    {
        "code": "62T",
        "name": "Cercanías Santander",
        "city": "Santander",
        "region": "Cantabria",
        "color": "EF3340",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_Santander",
        "description": "Red de cercanías de Cantabria.",
    },
    {
        "code": "70T",
        "name": "Cercanías Zaragoza",
        "city": "Zaragoza",
        "region": "Aragón",
        "color": "D90724",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/Cercan%C3%ADas_Zaragoza",
        "description": "Red de cercanías del área metropolitana de Zaragoza.",
    },
    {
        "code": "90T",
        "name": "Línea C-9 Cotos",
        "city": "Madrid",
        "region": "Comunidad de Madrid",
        "color": "75B6E0",
        "text_color": "FFFFFF",
        "wikipedia_url": "https://es.wikipedia.org/wiki/L%C3%ADnea_C-9_(Cercan%C3%ADas_Madrid)",
        "description": "Línea especial de montaña Cercedilla-Cotos.",
    },
]


def upgrade() -> None:
    # Create networks table
    op.create_table(
        'gtfs_networks',
        sa.Column('code', sa.String(10), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('region', sa.String(100), nullable=False),
        sa.Column('color', sa.String(6), nullable=False),
        sa.Column('text_color', sa.String(6), nullable=False, server_default='FFFFFF'),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('wikipedia_url', sa.String(500), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
    )

    # Seed network data
    networks_table = sa.table(
        'gtfs_networks',
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('city', sa.String),
        sa.column('region', sa.String),
        sa.column('color', sa.String),
        sa.column('text_color', sa.String),
        sa.column('wikipedia_url', sa.String),
        sa.column('description', sa.Text),
    )

    op.bulk_insert(networks_table, NETWORK_DATA)


def downgrade() -> None:
    op.drop_table('gtfs_networks')
