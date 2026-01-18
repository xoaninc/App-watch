#!/usr/bin/env python3
"""List all correspondences in Madrid."""
import sys
sys.path.insert(0, '/var/www/renfeserver')
from core.database import get_db
from sqlalchemy import text

db = next(get_db())

print('=' * 80)
print('CERCANÍAS MADRID - Correspondencias con Metro/ML')
print('=' * 80)
result = db.execute(text('''
    SELECT name, lineas, cor_metro, cor_ml, cor_tranvia
    FROM gtfs_stops
    WHERE id LIKE 'RENFE_%' AND nucleo_id = 10
    AND (cor_metro IS NOT NULL OR cor_ml IS NOT NULL OR cor_tranvia IS NOT NULL)
    ORDER BY name
'''))
for row in result.fetchall():
    extras = []
    if row[2]: extras.append(f'Metro: {row[2]}')
    if row[3]: extras.append(f'ML: {row[3]}')
    if row[4]: extras.append(f'Tranvía: {row[4]}')
    print(f'{row[0]} ({row[1]}) -> {", ".join(extras)}')

print()
print('=' * 80)
print('METRO MADRID - Correspondencias con Cercanías')
print('=' * 80)
result = db.execute(text('''
    SELECT name, lineas, cor_cercanias
    FROM gtfs_stops
    WHERE id LIKE 'METRO_%' AND id NOT LIKE 'METRO_SEV%' AND nucleo_id = 10
    AND cor_cercanias IS NOT NULL AND cor_cercanias != ''
    ORDER BY name
'''))
for row in result.fetchall():
    print(f'{row[0]} ({row[1]}) -> Cercanías: {row[2]}')

print()
print('=' * 80)
print('METRO LIGERO MADRID - Correspondencias con Cercanías')
print('=' * 80)
result = db.execute(text('''
    SELECT name, lineas, cor_cercanias
    FROM gtfs_stops
    WHERE id LIKE 'ML_%' AND nucleo_id = 10
    AND cor_cercanias IS NOT NULL AND cor_cercanias != ''
    ORDER BY name
'''))
for row in result.fetchall():
    print(f'{row[0]} ({row[1]}) -> Cercanías: {row[2]}')
