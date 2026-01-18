#!/usr/bin/env python3
"""Fix station codes and coordinates from GeoJSON."""
import sys
sys.path.insert(0, '/var/www/renfeserver')

import requests
from core.database import get_db
from sqlalchemy import text

db = next(get_db())

# Descargar GeoJSON
print("Descargando GeoJSON...")
url = 'https://tiempo-real.renfe.com/data/estaciones.geojson'
r = requests.get(url, timeout=30)
data = r.json()

# Crear índice por nombre+nucleo para buscar
geojson_by_name_nucleo = {}
for f in data['features']:
    p = f['properties']
    name = p.get('NOMBRE_ESTACION', '').lower().strip()
    nucleo = p.get('NUCLEO')
    if name and nucleo:
        key = (name, nucleo)
        geojson_by_name_nucleo[key] = {
            'codigo': p.get('CODIGO_ESTACION'),
            'name': p.get('NOMBRE_ESTACION'),
            'lat': p.get('LATITUD'),
            'lon': p.get('LONGITUD'),
            'lineas': p.get('LINEAS')
        }

print(f"Estaciones indexadas: {len(geojson_by_name_nucleo)}")
print()
print('=== BUSCANDO ESTACIONES CORRECTAS ===')
print()

# Paradas a corregir (stop_id, nombre_buscar, nucleo_id)
paradas_corregir = [
    ('RENFE_5376', 'santa cruz', 20),
    ('RENFE_5436', 'san martín', 20),
    ('RENFE_54501', 'victoria kent', 32),
    ('RENFE_54514', 'torreblanca', 32),
    ('RENFE_6004', 'la hoya', 41),
    ('RENFE_4040', 'delicias', 70),
    ('RENFE_5609', 'boo de pielagos', 62),  # Boo de Pielagos es diferente de Boo
]

for stop_id, name, nucleo_id in paradas_corregir:
    # Buscar por nombre exacto + nucleo
    key = (name, nucleo_id)
    gj = geojson_by_name_nucleo.get(key)

    if gj:
        print(f'{stop_id} ({name}) en nucleo {nucleo_id}:')
        print(f'  GeoJSON: codigo={gj["codigo"]}, lat={gj["lat"]:.6f}, lon={gj["lon"]:.6f}, lineas={gj["lineas"]}')

        # Actualizar en BD
        db.execute(text('''
            UPDATE gtfs_stops
            SET renfe_codigo_estacion = :cod,
                lat = :lat,
                lon = :lon,
                lineas = :lineas
            WHERE id = :id
        '''), {
            'id': stop_id,
            'cod': str(gj['codigo']),
            'lat': gj['lat'],
            'lon': gj['lon'],
            'lineas': gj['lineas']
        })
        print(f'  -> ACTUALIZADO')
    else:
        print(f'{stop_id} ({name}) en nucleo {nucleo_id}: NO ENCONTRADO')
        # Buscar variantes
        print(f'  Buscando variantes...')
        found = False
        for k, v in geojson_by_name_nucleo.items():
            if name in k[0] and k[1] == nucleo_id:
                print(f'    Posible: "{v["name"]}" (codigo {v["codigo"]})')
                found = True
        if not found:
            print(f'    Ninguna variante encontrada en nucleo {nucleo_id}')
    print()

db.commit()
print('=== CORRECCIONES APLICADAS ===')
print()

# Verificar
print('=== VERIFICACION FINAL ===')
stops = db.execute(text("""
    SELECT s.id, s.name, s.nucleo_id, n.name as nucleo_name,
           s.lat, s.lon, s.lineas, s.renfe_codigo_estacion
    FROM gtfs_stops s
    LEFT JOIN gtfs_nucleos n ON s.nucleo_id = n.id
    WHERE s.id IN ('RENFE_6004', 'RENFE_54501', 'RENFE_5376', 'RENFE_5436',
                   'RENFE_5609', 'RENFE_54514', 'RENFE_4040')
    ORDER BY s.id
""")).fetchall()

for s in stops:
    print(f'{s[0]} - {s[1]}')
    print(f'  Nucleo: {s[2]} ({s[3]})')
    print(f'  Coords: lat={s[4]:.6f}, lon={s[5]:.6f}')
    print(f'  Lineas: {s[6]}')
    print(f'  Codigo estacion: {s[7]}')
    print()
