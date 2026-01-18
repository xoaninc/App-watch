"""Restructure nucleos, provinces and networks

Revision ID: 023
Revises: 022
Create Date: 2026-01-18

Changes:
- gtfs_nucleos: borrar datos antiguos, insertar nuevos 20 núcleos
- gtfs_nucleos: añadir network_id (FK a gtfs_networks) y province_code (FK a spanish_provinces)
- spanish_provinces: quitar nucleo_id y nucleo_name
- gtfs_networks: quitar city, renombrar nucleo_id a nucleo_id_renfe, actualizar datos
"""
from alembic import op
import sqlalchemy as sa


revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


# =============================================================================
# NUEVOS NÚCLEOS (1 núcleo = 1 provincia/ciudad)
# =============================================================================
NEW_NUCLEOS = [
    {'id': 10, 'name': 'Madrid'},
    {'id': 20, 'name': 'Asturias'},
    {'id': 30, 'name': 'Sevilla'},
    {'id': 31, 'name': 'Cádiz'},
    {'id': 32, 'name': 'Málaga'},
    {'id': 33, 'name': 'Granada'},
    {'id': 40, 'name': 'Valencia'},
    {'id': 42, 'name': 'Alicante'},
    {'id': 43, 'name': 'Murcia'},
    {'id': 51, 'name': 'Barcelona'},
    {'id': 52, 'name': 'Lleida'},
    {'id': 53, 'name': 'Girona'},
    {'id': 54, 'name': 'Tarragona'},
    {'id': 59, 'name': 'Vitoria'},
    {'id': 60, 'name': 'Bilbao'},
    {'id': 61, 'name': 'San Sebastián'},
    {'id': 62, 'name': 'Cantabria'},
    {'id': 70, 'name': 'Zaragoza'},
    {'id': 80, 'name': 'Tenerife'},
    {'id': 81, 'name': 'Mallorca'},
]

# Mapeo de IDs antiguos a nuevos (para migrar stops/routes)
OLD_TO_NEW_NUCLEO_ID = {
    50: 51,  # Barcelona: 50 -> 51
    41: 43,  # Murcia/Alicante -> Murcia (se dividió)
    63: 59,  # Vitoria: 63 -> 59
}

# =============================================================================
# MAPEO NÚCLEO → NETWORK + PROVINCIA
# province_code = primeras 3 letras del nombre de provincia en spanish_provinces
# =============================================================================
NUCLEO_MAPPING = {
    # nucleo_id: (network_id, province_code)
    10: ('10T', 'MAD'),       # Madrid → Cercanías Madrid, provincia Madrid
    20: ('20T', 'AST'),       # Asturias → Cercanías Asturias, provincia Asturias
    30: ('30T', 'SEV'),       # Sevilla → Cercanías Sevilla, provincia Sevilla
    31: ('33T', 'CÁD'),       # Cádiz → Cercanías Cádiz, provincia Cádiz
    32: ('34T', 'MÁL'),       # Málaga → Cercanías Málaga, provincia Málaga
    33: ('METRO_GRANADA', 'GRA'),  # Granada → Metro Granada, provincia Granada
    40: ('40T', 'VAL'),       # Valencia → Cercanías Valencia, provincia Valencia
    42: ('41T', 'ALI'),       # Alicante → Cercanías Murcia/Alicante, provincia Alicante
    43: ('41T', 'MUR'),       # Murcia → Cercanías Murcia/Alicante, provincia Murcia
    51: ('51T', 'BAR'),       # Barcelona → Rodalies Catalunya, provincia Barcelona
    52: ('51T', 'LLE'),       # Lleida → Rodalies Catalunya, provincia Lleida
    53: ('51T', 'GIR'),       # Girona → Rodalies Catalunya, provincia Girona
    54: ('51T', 'TAR'),       # Tarragona → Rodalies Catalunya, provincia Tarragona
    59: ('TRANVIA_VITORIA', 'ÁLA'),  # Vitoria → Tranvía Vitoria, provincia Álava
    60: ('60T', 'VIZ'),       # Bilbao → Cercanías Bilbao, provincia Vizcaya
    61: ('61T', 'GUI'),       # San Sebastián → Cercanías San Sebastián, provincia Guipúzcoa
    62: ('62T', 'CAN'),       # Cantabria → Cercanías Santander, provincia Cantabria
    70: ('70T', 'ZAR'),       # Zaragoza → Cercanías Zaragoza, provincia Zaragoza
    80: ('METRO_TENERIFE', 'SAN'),  # Tenerife → Metrotenerife, provincia Santa Cruz de Tenerife
    81: ('SFM_MALLORCA', 'BAL'),    # Mallorca → SFM Mallorca, provincia Baleares
}


# =============================================================================
# PROVINCIAS NECESARIAS (para FK constraints)
# =============================================================================
REQUIRED_PROVINCES = [
    {'code': 'MAD', 'name': 'Madrid', 'autonomous_community': 'Comunidad de Madrid'},
    {'code': 'AST', 'name': 'Asturias', 'autonomous_community': 'Principado de Asturias'},
    {'code': 'SEV', 'name': 'Sevilla', 'autonomous_community': 'Andalucía'},
    {'code': 'CÁD', 'name': 'Cádiz', 'autonomous_community': 'Andalucía'},
    {'code': 'MÁL', 'name': 'Málaga', 'autonomous_community': 'Andalucía'},
    {'code': 'GRA', 'name': 'Granada', 'autonomous_community': 'Andalucía'},
    {'code': 'VAL', 'name': 'Valencia', 'autonomous_community': 'Comunidad Valenciana'},
    {'code': 'ALI', 'name': 'Alicante', 'autonomous_community': 'Comunidad Valenciana'},
    {'code': 'MUR', 'name': 'Murcia', 'autonomous_community': 'Región de Murcia'},
    {'code': 'BAR', 'name': 'Barcelona', 'autonomous_community': 'Cataluña'},
    {'code': 'LLE', 'name': 'Lleida', 'autonomous_community': 'Cataluña'},
    {'code': 'GIR', 'name': 'Girona', 'autonomous_community': 'Cataluña'},
    {'code': 'TAR', 'name': 'Tarragona', 'autonomous_community': 'Cataluña'},
    {'code': 'ÁLA', 'name': 'Álava', 'autonomous_community': 'País Vasco'},
    {'code': 'VIZ', 'name': 'Vizcaya', 'autonomous_community': 'País Vasco'},
    {'code': 'GUI', 'name': 'Guipúzcoa', 'autonomous_community': 'País Vasco'},
    {'code': 'CAN', 'name': 'Cantabria', 'autonomous_community': 'Cantabria'},
    {'code': 'ZAR', 'name': 'Zaragoza', 'autonomous_community': 'Aragón'},
    {'code': 'SAN', 'name': 'Santa Cruz de Tenerife', 'autonomous_community': 'Canarias'},
    {'code': 'BAL', 'name': 'Illes Balears', 'autonomous_community': 'Illes Balears'},
]


# =============================================================================
# NUEVOS NETWORKS (completo)
# =============================================================================
NEW_NETWORKS = [
    # Cercanías Renfe
    {'code': '10T', 'name': 'Cercanías Madrid', 'region': 'Comunidad de Madrid', 'color': '#75B6E0', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de Madrid', 'nucleo_id_renfe': 10},
    {'code': '20T', 'name': 'Cercanías Asturias', 'region': 'Asturias', 'color': '#EC3541', 'text_color': '#FFFFFF', 'description': 'Red de cercanías del Principado de Asturias', 'nucleo_id_renfe': 20},
    {'code': '30T', 'name': 'Cercanías Sevilla', 'region': 'Sevilla', 'color': '#78B4E1', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de Sevilla', 'nucleo_id_renfe': 30},
    {'code': '33T', 'name': 'Cercanías Cádiz', 'region': 'Cádiz', 'color': '#D7001E', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de la Bahía de Cádiz', 'nucleo_id_renfe': 31},
    {'code': '34T', 'name': 'Cercanías Málaga', 'region': 'Málaga', 'color': '#4A8CCC', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de Málaga', 'nucleo_id_renfe': 32},
    {'code': '40T', 'name': 'Cercanías Valencia', 'region': 'Comunidad Valenciana', 'color': '#7AB3DE', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de Valencia', 'nucleo_id_renfe': 40},
    {'code': '41T', 'name': 'Cercanías Murcia/Alicante', 'region': 'Región de Murcia / Alicante', 'color': '#73B6E0', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de Murcia y Alicante', 'nucleo_id_renfe': 41},
    {'code': '51T', 'name': 'Rodalies de Catalunya', 'region': 'Cataluña', 'color': '#FF0000', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de Cataluña', 'nucleo_id_renfe': 50},
    {'code': '60T', 'name': 'Cercanías Bilbao', 'region': 'Bizkaia', 'color': '#D7001E', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de Bilbao', 'nucleo_id_renfe': 60},
    {'code': '61T', 'name': 'Cercanías San Sebastián', 'region': 'Gipuzkoa', 'color': '#DA001C', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de San Sebastián', 'nucleo_id_renfe': 61},
    {'code': '62T', 'name': 'Cercanías Santander', 'region': 'Cantabria', 'color': '#EF3340', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de Cantabria', 'nucleo_id_renfe': 62},
    {'code': '70T', 'name': 'Cercanías Zaragoza', 'region': 'Aragón', 'color': '#D90724', 'text_color': '#FFFFFF', 'description': 'Red de cercanías de Zaragoza', 'nucleo_id_renfe': 70},
    {'code': '90T', 'name': 'Línea C-9 Cotos', 'region': 'Comunidad de Madrid', 'color': '#75B6E0', 'text_color': '#FFFFFF', 'description': 'Línea de montaña Cercedilla-Cotos', 'nucleo_id_renfe': 10},
    # Metro
    {'code': '11T', 'name': 'Metro de Madrid', 'region': 'Comunidad de Madrid', 'color': '#255B9D', 'text_color': '#FFFFFF', 'description': 'Red de metro de Madrid', 'nucleo_id_renfe': None},
    {'code': '12T', 'name': 'Metro Ligero de Madrid', 'region': 'Comunidad de Madrid', 'color': '#6BBE45', 'text_color': '#FFFFFF', 'description': 'Red de metro ligero de Madrid', 'nucleo_id_renfe': None},
    {'code': '32T', 'name': 'Metro de Sevilla', 'region': 'Sevilla', 'color': '#0D6928', 'text_color': '#000000', 'description': 'Red de metro de Sevilla', 'nucleo_id_renfe': None},
    {'code': 'METRO_BILBAO', 'name': 'Metro Bilbao', 'region': 'País Vasco', 'color': '#E30613', 'text_color': '#FFFFFF', 'description': 'Red de metro de Bilbao', 'nucleo_id_renfe': None},
    {'code': 'TMB_METRO', 'name': 'Metro de Barcelona', 'region': 'Cataluña', 'color': '#E30613', 'text_color': '#FFFFFF', 'description': 'Red de metro de Barcelona (TMB)', 'nucleo_id_renfe': None},
    {'code': 'METRO_VALENCIA', 'name': 'Metrovalencia', 'region': 'Comunidad Valenciana', 'color': '#E30613', 'text_color': '#FFFFFF', 'description': 'Red de metro de Valencia', 'nucleo_id_renfe': None},
    {'code': 'METRO_MALAGA', 'name': 'Metro de Málaga', 'region': 'Andalucía', 'color': '#E30613', 'text_color': '#FFFFFF', 'description': 'Red de metro de Málaga', 'nucleo_id_renfe': None},
    {'code': 'METRO_GRANADA', 'name': 'Metro de Granada', 'region': 'Andalucía', 'color': '#E30613', 'text_color': '#FFFFFF', 'description': 'Red de metro de Granada', 'nucleo_id_renfe': None},
    {'code': 'METRO_TENERIFE', 'name': 'Metrotenerife', 'region': 'Canarias', 'color': '#E30613', 'text_color': '#FFFFFF', 'description': 'Tranvía ligero de Tenerife', 'nucleo_id_renfe': None},
    # Tranvía
    {'code': '31T', 'name': 'Tranvía de Sevilla', 'region': 'Sevilla', 'color': '#E4002B', 'text_color': '#FFFFFF', 'description': 'MetroCentro de Sevilla', 'nucleo_id_renfe': None},
    {'code': 'TRAM_BCN', 'name': 'TRAM Barcelona', 'region': 'Cataluña', 'color': '#00A650', 'text_color': '#FFFFFF', 'description': 'Trambaix y Trambesòs', 'nucleo_id_renfe': None},
    {'code': 'TRAM_ALICANTE', 'name': 'TRAM Alicante', 'region': 'Comunidad Valenciana', 'color': '#E30613', 'text_color': '#FFFFFF', 'description': 'TRAM Metropolitano de Alicante', 'nucleo_id_renfe': None},
    {'code': 'TRANVIA_ZARAGOZA', 'name': 'Tranvía de Zaragoza', 'region': 'Aragón', 'color': '#009640', 'text_color': '#FFFFFF', 'description': 'Tranvía de Zaragoza', 'nucleo_id_renfe': None},
    {'code': 'TRANVIA_MURCIA', 'name': 'Tranvía de Murcia', 'region': 'Región de Murcia', 'color': '#E30613', 'text_color': '#FFFFFF', 'description': 'Tranvía de Murcia', 'nucleo_id_renfe': None},
    {'code': 'TRANVIA_VITORIA', 'name': 'Tranvía de Vitoria', 'region': 'País Vasco', 'color': '#009640', 'text_color': '#FFFFFF', 'description': 'Tranvía de Vitoria-Gasteiz', 'nucleo_id_renfe': None},
    # Ferrocarril Regional
    {'code': 'FGC', 'name': 'FGC', 'region': 'Cataluña', 'color': '#F26522', 'text_color': '#FFFFFF', 'description': 'Ferrocarrils de la Generalitat de Catalunya', 'nucleo_id_renfe': None},
    {'code': 'EUSKOTREN', 'name': 'Euskotren', 'region': 'País Vasco', 'color': '#009640', 'text_color': '#FFFFFF', 'description': 'Red de Euskotren', 'nucleo_id_renfe': None},
    {'code': 'SFM_MALLORCA', 'name': 'SFM Mallorca', 'region': 'Illes Balears', 'color': '#005192', 'text_color': '#FFFFFF', 'description': 'Serveis Ferroviaris de Mallorca', 'nucleo_id_renfe': None},
]


def upgrade() -> None:
    # =========================================================================
    # PARTE 1: PREPARACIÓN - Quitar FKs existentes
    # =========================================================================
    op.drop_constraint('fk_stops_nucleo', 'gtfs_stops', type_='foreignkey')
    op.drop_constraint('fk_routes_nucleo', 'gtfs_routes', type_='foreignkey')
    op.drop_constraint('fk_provinces_nucleo', 'spanish_provinces', type_='foreignkey')

    # =========================================================================
    # PARTE 2: GTFS_NETWORKS (primero, porque nucleos depende de networks)
    # =========================================================================

    # 2.1 Renombrar nucleo_id a nucleo_id_renfe
    op.alter_column('gtfs_networks', 'nucleo_id', new_column_name='nucleo_id_renfe')

    # 2.2 Quitar columna city
    op.drop_column('gtfs_networks', 'city')

    # 2.3 Expandir columnas para soportar nuevos formatos
    op.alter_column('gtfs_networks', 'code', type_=sa.String(20))  # Códigos más largos como TRANVIA_ZARAGOZA
    op.alter_column('gtfs_networks', 'color', type_=sa.String(10))  # Formato #XXXXXX
    op.alter_column('gtfs_networks', 'text_color', type_=sa.String(10))

    # 2.4 Borrar datos antiguos y insertar nuevos
    op.execute("DELETE FROM gtfs_networks")

    networks_table = sa.table(
        'gtfs_networks',
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('region', sa.String),
        sa.column('color', sa.String),
        sa.column('text_color', sa.String),
        sa.column('description', sa.Text),
        sa.column('nucleo_id_renfe', sa.Integer),
    )
    op.bulk_insert(networks_table, NEW_NETWORKS)

    # =========================================================================
    # PARTE 3: SPANISH_PROVINCES (quitar columnas obsoletas e insertar datos)
    # =========================================================================
    op.drop_index('idx_provinces_nucleo_id', table_name='spanish_provinces')
    op.drop_index('idx_provinces_nucleo_name', table_name='spanish_provinces')
    op.drop_column('spanish_provinces', 'nucleo_id')
    op.drop_column('spanish_provinces', 'nucleo_name')

    # Insertar provincias necesarias para los FK de nucleos
    provinces_table = sa.table(
        'spanish_provinces',
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('autonomous_community', sa.String),
    )
    op.bulk_insert(provinces_table, REQUIRED_PROVINCES)

    # =========================================================================
    # PARTE 4: GTFS_NUCLEOS
    # =========================================================================

    # 4.1 Migrar nucleo_id en stops y routes (IDs que cambian)
    for old_id, new_id in OLD_TO_NEW_NUCLEO_ID.items():
        op.execute(f"UPDATE gtfs_stops SET nucleo_id = {new_id} WHERE nucleo_id = {old_id}")
        op.execute(f"UPDATE gtfs_routes SET nucleo_id = {new_id} WHERE nucleo_id = {old_id}")

    # 4.2 Borrar datos antiguos de gtfs_nucleos y insertar nuevos
    op.execute("DELETE FROM gtfs_nucleos")

    nucleos_table = sa.table(
        'gtfs_nucleos',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
    )
    op.bulk_insert(nucleos_table, NEW_NUCLEOS)

    # 4.3 Añadir columnas a gtfs_nucleos
    op.add_column('gtfs_nucleos', sa.Column('network_id', sa.String(15), nullable=True))
    op.add_column('gtfs_nucleos', sa.Column('province_code', sa.String(5), nullable=True))

    # 4.4 Poblar network_id y province_code en nucleos (antes de crear FKs)
    for nucleo_id, (network_id, province_code) in NUCLEO_MAPPING.items():
        op.execute(f"""
            UPDATE gtfs_nucleos
            SET network_id = '{network_id}', province_code = '{province_code}'
            WHERE id = {nucleo_id}
        """)

    # 4.5 Crear FK constraints para nucleos
    op.create_foreign_key(
        'fk_nucleos_network',
        'gtfs_nucleos',
        'gtfs_networks',
        ['network_id'],
        ['code'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_nucleos_province',
        'gtfs_nucleos',
        'spanish_provinces',
        ['province_code'],
        ['code'],
        ondelete='SET NULL'
    )

    # 4.6 Crear índices para nucleos
    op.create_index('idx_nucleos_network_id', 'gtfs_nucleos', ['network_id'])
    op.create_index('idx_nucleos_province_code', 'gtfs_nucleos', ['province_code'])

    # 4.7 Recrear FKs de stops y routes a nucleos
    op.create_foreign_key(
        'fk_stops_nucleo',
        'gtfs_stops',
        'gtfs_nucleos',
        ['nucleo_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_routes_nucleo',
        'gtfs_routes',
        'gtfs_nucleos',
        ['nucleo_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # =========================================================================
    # Revertir GTFS_NETWORKS
    # =========================================================================
    op.add_column('gtfs_networks', sa.Column('city', sa.String(100), nullable=True))
    op.alter_column('gtfs_networks', 'nucleo_id_renfe', new_column_name='nucleo_id')
    op.alter_column('gtfs_networks', 'color', type_=sa.String(6))
    op.alter_column('gtfs_networks', 'text_color', type_=sa.String(6))

    # =========================================================================
    # Revertir SPANISH_PROVINCES
    # =========================================================================
    op.add_column('spanish_provinces', sa.Column('nucleo_id', sa.Integer(), nullable=True))
    op.add_column('spanish_provinces', sa.Column('nucleo_name', sa.String(100), nullable=True))
    op.create_index('idx_provinces_nucleo_id', 'spanish_provinces', ['nucleo_id'])
    op.create_index('idx_provinces_nucleo_name', 'spanish_provinces', ['nucleo_name'])

    # =========================================================================
    # Revertir GTFS_NUCLEOS
    # =========================================================================
    op.drop_constraint('fk_stops_nucleo', 'gtfs_stops', type_='foreignkey')
    op.drop_constraint('fk_routes_nucleo', 'gtfs_routes', type_='foreignkey')

    op.drop_index('idx_nucleos_network_id', table_name='gtfs_nucleos')
    op.drop_index('idx_nucleos_province_code', table_name='gtfs_nucleos')
    op.drop_constraint('fk_nucleos_network', 'gtfs_nucleos', type_='foreignkey')
    op.drop_constraint('fk_nucleos_province', 'gtfs_nucleos', type_='foreignkey')
    op.drop_column('gtfs_nucleos', 'network_id')
    op.drop_column('gtfs_nucleos', 'province_code')

    # Recrear FK de provinces a nucleos
    op.create_foreign_key(
        'fk_provinces_nucleo',
        'spanish_provinces',
        'gtfs_nucleos',
        ['nucleo_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Recrear FKs de stops y routes
    op.create_foreign_key(
        'fk_stops_nucleo',
        'gtfs_stops',
        'gtfs_nucleos',
        ['nucleo_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_routes_nucleo',
        'gtfs_routes',
        'gtfs_nucleos',
        ['nucleo_id'],
        ['id'],
        ondelete='SET NULL'
    )
