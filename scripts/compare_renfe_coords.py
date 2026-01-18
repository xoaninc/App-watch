#!/usr/bin/env python3
"""Compare RENFE stop coordinates with official GeoJSON data."""
import sys
sys.path.insert(0, '/var/www/renfeserver')

import requests
from core.database import get_db
from sqlalchemy import text
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two coordinates."""
    R = 6371000
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# Download GeoJSON
print("Descargando GeoJSON de Renfe...")
url = "https://tiempo-real.renfe.com/data/estaciones.geojson"
response = requests.get(url, timeout=30)
response.raise_for_status()
geojson = response.json()

print(f"Descargado: {len(geojson.get('features', []))} estaciones en el GeoJSON")
print()

# Build dict of GeoJSON stations by (CODIGO_ESTACION, NUCLEO)
geojson_stations = {}
for feature in geojson.get('features', []):
    props = feature.get('properties', {})
    codigo = props.get('CODIGO_ESTACION')
    nucleo = props.get('NUCLEO')
    if codigo and nucleo:
        key = (str(codigo), int(nucleo))
        geojson_stations[key] = {
            'name': props.get('NOMBRE_ESTACION', ''),
            'lat': props.get('LATITUD'),
            'lon': props.get('LONGITUD'),
            'nucleo': nucleo,
            'nucleo_name': props.get('NOMBRE_NUCLEO'),
            'lineas': props.get('LINEAS', '')
        }

print(f"Estaciones únicas en GeoJSON (codigo+nucleo): {len(geojson_stations)}")
print()

# Get all RENFE stops from database
db = next(get_db())
db_stops = db.execute(text("""
    SELECT s.id, s.name, s.lat, s.lon, s.nucleo_id, s.lineas, s.renfe_codigo_estacion,
           n.name as nucleo_name
    FROM gtfs_stops s
    LEFT JOIN gtfs_nucleos n ON s.nucleo_id = n.id
    WHERE s.id LIKE 'RENFE_%'
    ORDER BY s.nucleo_id, s.id
""")).fetchall()

print(f"Paradas RENFE en BD: {len(db_stops)}")
print()

# Compare
print("=" * 140)
print("COMPARACION DE COORDENADAS: BD vs GeoJSON Oficial de Renfe (por CODIGO + NUCLEO)")
print("=" * 140)
print()

differences = []
not_found_in_geojson = []
matched = 0
current_nucleo = None

for stop in db_stops:
    stop_id, name, db_lat, db_lon, nucleo_id, lineas, codigo_estacion, nucleo_name = stop

    # Extract codigo from stop_id if not in renfe_codigo_estacion
    if not codigo_estacion:
        # RENFE_12345 -> 12345
        codigo_estacion = stop_id.replace('RENFE_', '')

    # Key is (codigo, nucleo_id)
    key = (str(codigo_estacion), nucleo_id)
    geojson_station = geojson_stations.get(key)

    if not geojson_station:
        not_found_in_geojson.append({
            'id': stop_id,
            'name': name,
            'nucleo_id': nucleo_id,
            'nucleo_name': nucleo_name,
            'codigo': codigo_estacion,
            'lineas': lineas,
            'lat': db_lat,
            'lon': db_lon
        })
        continue

    matched += 1
    gj_lat = geojson_station['lat']
    gj_lon = geojson_station['lon']

    if gj_lat is None or gj_lon is None:
        continue

    distance = haversine(db_lat, db_lon, gj_lat, gj_lon)

    if distance > 10:  # More than 10 meters difference
        differences.append({
            'id': stop_id,
            'name': name,
            'nucleo_id': nucleo_id,
            'nucleo_name': nucleo_name,
            'lineas': lineas,
            'db_lat': db_lat,
            'db_lon': db_lon,
            'gj_lat': gj_lat,
            'gj_lon': gj_lon,
            'gj_name': geojson_station['name'],
            'gj_lineas': geojson_station['lineas'],
            'distance': distance
        })

# Print differences sorted by distance
print("DIFERENCIAS DE COORDENADAS (>10m):")
print("-" * 140)

if differences:
    differences.sort(key=lambda x: (-x['nucleo_id'], -x['distance']))
    current_nucleo = None

    for diff in differences:
        if diff['nucleo_id'] != current_nucleo:
            current_nucleo = diff['nucleo_id']
            print()
            print(f"{'='*60}")
            print(f"NUCLEO {current_nucleo} - {diff['nucleo_name']}")
            print(f"{'='*60}")

        print()
        print(f"  {diff['id']} - {diff['name']}")
        print(f"    BD:      lat={diff['db_lat']:.6f}, lon={diff['db_lon']:.6f}  lineas=[{diff['lineas']}]")
        print(f"    GeoJSON: lat={diff['gj_lat']:.6f}, lon={diff['gj_lon']:.6f}  lineas=[{diff['gj_lineas']}] ({diff['gj_name']})")
        print(f"    DIFERENCIA: {diff['distance']:.0f} metros")
else:
    print("  Ninguna diferencia mayor a 10 metros!")

print()
print("=" * 140)
print("PARADAS EN BD QUE NO ESTAN EN GEOJSON (mismo codigo+nucleo):")
print("-" * 140)

if not_found_in_geojson:
    current_nucleo = None
    for stop in sorted(not_found_in_geojson, key=lambda x: (x['nucleo_id'], x['id'])):
        if stop['nucleo_id'] != current_nucleo:
            current_nucleo = stop['nucleo_id']
            print()
            print(f"{'='*60}")
            print(f"NUCLEO {current_nucleo} - {stop['nucleo_name']}")
            print(f"{'='*60}")
        print(f"  {stop['id']} - {stop['name']}")
        print(f"    codigo={stop['codigo']}, lineas=[{stop['lineas']}]")
        print(f"    coords: lat={stop['lat']:.6f}, lon={stop['lon']:.6f}")
else:
    print("  Todas las paradas tienen correspondencia en el GeoJSON!")

print()
print("=" * 140)
print("RESUMEN:")
print("-" * 140)
print(f"  Paradas RENFE en BD: {len(db_stops)}")
print(f"  Estaciones en GeoJSON: {len(geojson_stations)}")
print(f"  Coincidencias encontradas (codigo+nucleo): {matched}")
print(f"  Con diferencia >10m: {len(differences)}")
print(f"  No encontradas en GeoJSON: {len(not_found_in_geojson)}")
print("=" * 140)
