#!/usr/bin/env python3
"""Search for Calafell stations in GeoJSON."""
import requests

url = 'https://tiempo-real.renfe.com/data/estaciones.geojson'
r = requests.get(url, timeout=30)
data = r.json()

print('=== Buscando Calafell, Segur de Calafell, Calaf en GeoJSON ===')
print()

for f in data['features']:
    p = f['properties']
    name = p.get('NOMBRE_ESTACION', '').lower()

    if 'calaf' in name or 'segur' in name:
        print(f"Nombre: {p.get('NOMBRE_ESTACION')}")
        print(f"  Codigo: {p.get('CODIGO_ESTACION')}, Nucleo: {p.get('NUCLEO')} ({p.get('NOMBRE_NUCLEO')})")
        print(f"  Coords: lat={p.get('LATITUD')}, lon={p.get('LONGITUD')}")
        print(f"  Lineas: {p.get('LINEAS')}")
        print()

print()
print('=== Datos actuales en BD ===')
import sys
sys.path.insert(0, '/var/www/renfeserver')
from core.database import get_db
from sqlalchemy import text

db = next(get_db())
stops = db.execute(text("""
    SELECT id, name, lat, lon, lineas, renfe_codigo_estacion
    FROM gtfs_stops
    WHERE name ILIKE '%calaf%' OR name ILIKE '%segur%'
    ORDER BY id
""")).fetchall()

for s in stops:
    print(f"{s[0]} - {s[1]}")
    print(f"  Coords: lat={s[2]}, lon={s[3]}")
    print(f"  Lineas: {s[4]}, Codigo: {s[5]}")
    print()
