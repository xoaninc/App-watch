"""Replace nucleos with network_provinces

Revision ID: 024
Revises: 023
Create Date: 2026-01-18

Changes:
- Create network_provinces table (N:M relationship)
- Add network_id to gtfs_routes
- Migrate nucleo_id to network_id in routes
- Remove nucleo_id and nucleo_name from gtfs_stops and gtfs_routes
- Drop gtfs_nucleos table
"""
from alembic import op
import sqlalchemy as sa


revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


# =============================================================================
# MAPEO NUCLEO_ID → NETWORK_ID (de migración 023)
# =============================================================================
NUCLEO_TO_NETWORK = {
    10: '10T',    # Madrid
    20: '20T',    # Asturias
    30: '30T',    # Sevilla
    31: '33T',    # Cádiz
    32: '34T',    # Málaga
    33: 'METRO_GRANADA',  # Granada
    40: '40T',    # Valencia
    42: '41T',    # Alicante
    43: '41T',    # Murcia
    51: '51T',    # Barcelona
    52: '51T',    # Lleida
    53: '51T',    # Girona
    54: '51T',    # Tarragona
    59: 'TRANVIA_VITORIA',  # Vitoria
    60: '60T',    # Bilbao
    61: '61T',    # San Sebastián
    62: '62T',    # Cantabria
    70: '70T',    # Zaragoza
    80: 'METRO_TENERIFE',  # Tenerife
    81: 'SFM_MALLORCA',    # Mallorca
}

# =============================================================================
# NETWORK → PROVINCIAS DONDE OPERA
# =============================================================================
NETWORK_PROVINCES = [
    # Cercanías Renfe
    ('10T', 'MAD'),       # Cercanías Madrid
    ('20T', 'AST'),       # Cercanías Asturias
    ('30T', 'SEV'),       # Cercanías Sevilla
    ('33T', 'CÁD'),       # Cercanías Cádiz
    ('34T', 'MÁL'),       # Cercanías Málaga
    ('40T', 'VAL'),       # Cercanías Valencia
    ('41T', 'ALI'),       # Cercanías Murcia/Alicante - Alicante
    ('41T', 'MUR'),       # Cercanías Murcia/Alicante - Murcia
    ('51T', 'BAR'),       # Rodalies Catalunya - Barcelona
    ('51T', 'LLE'),       # Rodalies Catalunya - Lleida
    ('51T', 'GIR'),       # Rodalies Catalunya - Girona
    ('51T', 'TAR'),       # Rodalies Catalunya - Tarragona
    ('60T', 'VIZ'),       # Cercanías Bilbao
    ('61T', 'GUI'),       # Cercanías San Sebastián
    ('62T', 'CAN'),       # Cercanías Santander
    ('70T', 'ZAR'),       # Cercanías Zaragoza
    ('90T', 'MAD'),       # Línea C-9 Cotos
    # Metro
    ('11T', 'MAD'),       # Metro de Madrid
    ('12T', 'MAD'),       # Metro Ligero de Madrid
    ('32T', 'SEV'),       # Metro de Sevilla
    ('METRO_BILBAO', 'VIZ'),      # Metro Bilbao
    ('TMB_METRO', 'BAR'),         # Metro de Barcelona
    ('METRO_VALENCIA', 'VAL'),    # Metrovalencia
    ('METRO_MALAGA', 'MÁL'),      # Metro de Málaga
    ('METRO_GRANADA', 'GRA'),     # Metro de Granada
    ('METRO_TENERIFE', 'SAN'),    # Metrotenerife
    # Tranvía
    ('31T', 'SEV'),               # Tranvía de Sevilla
    ('TRAM_BCN', 'BAR'),          # TRAM Barcelona
    ('TRAM_ALICANTE', 'ALI'),     # TRAM Alicante
    ('TRANVIA_ZARAGOZA', 'ZAR'),  # Tranvía de Zaragoza
    ('TRANVIA_MURCIA', 'MUR'),    # Tranvía de Murcia
    ('TRANVIA_VITORIA', 'ÁLA'),   # Tranvía de Vitoria
    # Ferrocarril Regional
    ('FGC', 'BAR'),       # FGC - Barcelona
    ('FGC', 'LLE'),       # FGC - Lleida (Línea Llobregat-Anoia llega hasta allí)
    ('EUSKOTREN', 'VIZ'), # Euskotren - Vizcaya
    ('EUSKOTREN', 'GUI'), # Euskotren - Guipúzcoa
    ('SFM_MALLORCA', 'BAL'),  # SFM Mallorca
]


def upgrade() -> None:
    # =========================================================================
    # PARTE 1: Crear tabla network_provinces
    # =========================================================================
    op.create_table(
        'network_provinces',
        sa.Column('network_id', sa.String(20), sa.ForeignKey('gtfs_networks.code', ondelete='CASCADE'), primary_key=True),
        sa.Column('province_code', sa.String(5), sa.ForeignKey('spanish_provinces.code', ondelete='CASCADE'), primary_key=True),
    )
    op.create_index('idx_network_provinces_network', 'network_provinces', ['network_id'])
    op.create_index('idx_network_provinces_province', 'network_provinces', ['province_code'])

    # Poblar network_provinces
    network_provinces_table = sa.table(
        'network_provinces',
        sa.column('network_id', sa.String),
        sa.column('province_code', sa.String),
    )
    op.bulk_insert(network_provinces_table, [
        {'network_id': np[0], 'province_code': np[1]} for np in NETWORK_PROVINCES
    ])

    # =========================================================================
    # PARTE 2: Añadir network_id a gtfs_routes y migrar datos
    # =========================================================================
    op.add_column('gtfs_routes', sa.Column('network_id', sa.String(20), nullable=True))

    # Migrar nucleo_id a network_id
    for nucleo_id, network_id in NUCLEO_TO_NETWORK.items():
        op.execute(f"""
            UPDATE gtfs_routes
            SET network_id = '{network_id}'
            WHERE nucleo_id = {nucleo_id}
        """)

    # Crear FK y índice
    op.create_foreign_key(
        'fk_routes_network',
        'gtfs_routes',
        'gtfs_networks',
        ['network_id'],
        ['code'],
        ondelete='SET NULL'
    )
    op.create_index('idx_routes_network_id', 'gtfs_routes', ['network_id'])

    # =========================================================================
    # PARTE 3: Eliminar referencias a nucleos
    # =========================================================================

    # Quitar FK de stops a nucleos
    op.drop_constraint('fk_stops_nucleo', 'gtfs_stops', type_='foreignkey')

    # Quitar FK de routes a nucleos
    op.drop_constraint('fk_routes_nucleo', 'gtfs_routes', type_='foreignkey')

    # Quitar columnas de gtfs_stops
    op.drop_column('gtfs_stops', 'nucleo_id')
    op.drop_column('gtfs_stops', 'nucleo_name')

    # Quitar columnas de gtfs_routes
    op.drop_column('gtfs_routes', 'nucleo_id')
    op.drop_column('gtfs_routes', 'nucleo_name')

    # =========================================================================
    # PARTE 4: Eliminar tabla gtfs_nucleos
    # =========================================================================

    # Primero quitar las FKs y constraints de gtfs_nucleos
    op.drop_index('idx_nucleos_network_id', table_name='gtfs_nucleos')
    op.drop_index('idx_nucleos_province_code', table_name='gtfs_nucleos')
    op.drop_constraint('fk_nucleos_network', 'gtfs_nucleos', type_='foreignkey')
    op.drop_constraint('fk_nucleos_province', 'gtfs_nucleos', type_='foreignkey')

    # Eliminar la tabla
    op.drop_table('gtfs_nucleos')


def downgrade() -> None:
    # =========================================================================
    # Recrear gtfs_nucleos
    # =========================================================================
    op.create_table(
        'gtfs_nucleos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('color', sa.String(50), nullable=True),
        sa.Column('network_id', sa.String(15), nullable=True),
        sa.Column('province_code', sa.String(5), nullable=True),
        sa.Column('bounding_box_min_lat', sa.Float(), nullable=True),
        sa.Column('bounding_box_max_lat', sa.Float(), nullable=True),
        sa.Column('bounding_box_min_lon', sa.Float(), nullable=True),
        sa.Column('bounding_box_max_lon', sa.Float(), nullable=True),
        sa.Column('center_lat', sa.Float(), nullable=True),
        sa.Column('center_lon', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # Recrear índices y FKs de nucleos
    op.create_index('idx_nucleos_network_id', 'gtfs_nucleos', ['network_id'])
    op.create_index('idx_nucleos_province_code', 'gtfs_nucleos', ['province_code'])
    op.create_foreign_key('fk_nucleos_network', 'gtfs_nucleos', 'gtfs_networks', ['network_id'], ['code'], ondelete='SET NULL')
    op.create_foreign_key('fk_nucleos_province', 'gtfs_nucleos', 'spanish_provinces', ['province_code'], ['code'], ondelete='SET NULL')

    # =========================================================================
    # Recrear columnas en stops y routes
    # =========================================================================
    op.add_column('gtfs_stops', sa.Column('nucleo_id', sa.Integer(), nullable=True))
    op.add_column('gtfs_stops', sa.Column('nucleo_name', sa.String(100), nullable=True))
    op.add_column('gtfs_routes', sa.Column('nucleo_id', sa.Integer(), nullable=True))
    op.add_column('gtfs_routes', sa.Column('nucleo_name', sa.String(100), nullable=True))

    # Recrear FKs
    op.create_foreign_key('fk_stops_nucleo', 'gtfs_stops', 'gtfs_nucleos', ['nucleo_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_routes_nucleo', 'gtfs_routes', 'gtfs_nucleos', ['nucleo_id'], ['id'], ondelete='SET NULL')

    # =========================================================================
    # Quitar network_id de routes
    # =========================================================================
    op.drop_index('idx_routes_network_id', table_name='gtfs_routes')
    op.drop_constraint('fk_routes_network', 'gtfs_routes', type_='foreignkey')
    op.drop_column('gtfs_routes', 'network_id')

    # =========================================================================
    # Eliminar network_provinces
    # =========================================================================
    op.drop_index('idx_network_provinces_province', table_name='network_provinces')
    op.drop_index('idx_network_provinces_network', table_name='network_provinces')
    op.drop_table('network_provinces')
