#!/usr/bin/env python3
"""Debug C4a route issues."""
import sys
sys.path.insert(0, '/var/www/renfeserver')

from core.database import get_db
from sqlalchemy import text

db = next(get_db())

print('=== STOP_ROUTE_SEQUENCE de C4a (primeras 5 por sequence) ===')
srs = db.execute(text("""
    SELECT srs.stop_id, s.name, srs.sequence
    FROM gtfs_stop_route_sequence srs
    JOIN gtfs_stops s ON srs.stop_id = s.id
    JOIN gtfs_routes r ON srs.route_id = r.id
    WHERE r.short_name = 'C4a'
    ORDER BY srs.sequence
    LIMIT 5
""")).fetchall()

for s in srs:
    print(f'{s[2]}: {s[0]} - {s[1]}')

print()
print('=== Buscando paradas "Parla" ===')
parla = db.execute(text("""
    SELECT id, name, nucleo_id, lat, lon
    FROM gtfs_stops
    WHERE name ILIKE '%parla%'
    ORDER BY id
""")).fetchall()

for p in parla:
    print(f'{p[0]} - {p[1]} (nucleo {p[2]}) lat={p[3]:.6f}, lon={p[4]:.6f}')

print()
print('=== long_name actual de C4a ===')
route = db.execute(text("""
    SELECT long_name FROM gtfs_routes WHERE short_name = 'C4a'
""")).fetchone()
print(f'long_name: {route[0]}')

print()
print('=== Origen del long_name (gtfs_stop_route_sequence) ===')
# Ver qué parada tiene sequence 0 para C4a
first = db.execute(text("""
    SELECT srs.stop_id, s.name, srs.sequence
    FROM gtfs_stop_route_sequence srs
    JOIN gtfs_stops s ON srs.stop_id = s.id
    WHERE srs.route_id = 'RENFE_C4a_67'
    ORDER BY srs.sequence
    LIMIT 1
""")).fetchone()
if first:
    print(f'Primera parada en stop_route_sequence: {first[0]} - {first[1]} (seq {first[2]})')

# Ver la última
last = db.execute(text("""
    SELECT srs.stop_id, s.name, srs.sequence
    FROM gtfs_stop_route_sequence srs
    JOIN gtfs_stops s ON srs.stop_id = s.id
    WHERE srs.route_id = 'RENFE_C4a_67'
    ORDER BY srs.sequence DESC
    LIMIT 1
""")).fetchone()
if last:
    print(f'Última parada en stop_route_sequence: {last[0]} - {last[1]} (seq {last[2]})')
