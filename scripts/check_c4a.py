#!/usr/bin/env python3
"""Check C4a route data."""
import sys
sys.path.insert(0, '/var/www/renfeserver')

from core.database import get_db
from sqlalchemy import text

db = next(get_db())

print('=== RUTA C4a ===')
route = db.execute(text("""
    SELECT id, short_name, long_name, nucleo_id
    FROM gtfs_routes
    WHERE short_name = 'C4a'
""")).fetchone()

if route:
    print(f'ID: {route[0]}')
    print(f'Short name: {route[1]}')
    print(f'Long name: {route[2]}')
    print(f'Nucleo: {route[3]}')
else:
    print('No encontrada')

print()
print('=== STOP_TIMES de C4a (primeros 10 ordenados por hora) ===')
times = db.execute(text("""
    SELECT st.arrival_time, st.departure_time, s.name, t.direction_id
    FROM gtfs_stop_times st
    JOIN gtfs_trips t ON st.trip_id = t.id
    JOIN gtfs_routes r ON t.route_id = r.id
    JOIN gtfs_stops s ON st.stop_id = s.id
    WHERE r.short_name = 'C4a'
    ORDER BY st.arrival_time
    LIMIT 10
""")).fetchall()

for t in times:
    print(f'{t[0]} - {t[2]} (dir {t[3]})')

print()
print('=== PRIMERAS SALIDAS REALES (por dirección) ===')
first_deps = db.execute(text("""
    SELECT t.direction_id, MIN(st.departure_time) as first_dep
    FROM gtfs_stop_times st
    JOIN gtfs_trips t ON st.trip_id = t.id
    JOIN gtfs_routes r ON t.route_id = r.id
    WHERE r.short_name = 'C4a' AND st.stop_sequence = 1
    GROUP BY t.direction_id
""")).fetchall()

for f in first_deps:
    print(f'Dirección {f[0]}: Primera salida {f[1]}')

print()
print('=== PARADAS TERMINUS de C4a (stop_route_sequence) ===')
terminus = db.execute(text("""
    SELECT s.name, srs.sequence
    FROM gtfs_stop_route_sequence srs
    JOIN gtfs_stops s ON srs.stop_id = s.id
    JOIN gtfs_routes r ON srs.route_id = r.id
    WHERE r.short_name = 'C4a'
    ORDER BY srs.sequence
""")).fetchall()

if terminus:
    print(f'Primera: {terminus[0][0]} (seq {terminus[0][1]})')
    print(f'Última: {terminus[-1][0]} (seq {terminus[-1][1]})')
    print()
    print('Todas las paradas:')
    for t in terminus:
        print(f'  {t[1]}: {t[0]}')
else:
    print('No hay stop_route_sequence para C4a')

print()
print('=== TRIPS de C4a con sus headsigns ===')
trips = db.execute(text("""
    SELECT DISTINCT t.headsign, t.direction_id, COUNT(*) as count
    FROM gtfs_trips t
    JOIN gtfs_routes r ON t.route_id = r.id
    WHERE r.short_name = 'C4a'
    GROUP BY t.headsign, t.direction_id
""")).fetchall()

for t in trips:
    print(f'Dir {t[1]}: {t[0]} ({t[2]} trips)')
