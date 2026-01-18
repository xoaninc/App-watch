#!/usr/bin/env python3
"""List all stops with correspondences."""
import sys
sys.path.insert(0, '/var/www/renfeserver')
from core.database import get_db
from sqlalchemy import text

db = next(get_db())

print("=" * 100)
print("METRO MADRID - TODAS LAS PARADAS")
print("=" * 100)
result = db.execute(text("""
    SELECT id, name, lineas, cor_cercanias, cor_metro, cor_ml
    FROM gtfs_stops
    WHERE id LIKE 'METRO_%' AND id NOT LIKE 'METRO_SEV%' AND nucleo_id = 10
    ORDER BY
        CASE WHEN id ~ E'^METRO_[0-9]+$' THEN CAST(SUBSTRING(id FROM 7) AS INTEGER) ELSE 9999 END,
        id
"""))
rows = result.fetchall()
print("Total: {} estaciones".format(len(rows)))
print()
for row in rows:
    extras = []
    if row[3]: extras.append("Cercanias: {}".format(row[3]))
    if row[4]: extras.append("Cor Metro: {}".format(row[4]))
    if row[5]: extras.append("ML: {}".format(row[5]))
    cor_str = " -> " + ", ".join(extras) if extras else ""
    print("{} ({}) [{}]{}".format(row[0], row[1], row[2], cor_str))

print()
print("=" * 100)
print("METRO LIGERO MADRID - TODAS LAS PARADAS")
print("=" * 100)
result = db.execute(text("""
    SELECT id, name, lineas, cor_cercanias, cor_metro
    FROM gtfs_stops
    WHERE id LIKE 'ML_%' AND nucleo_id = 10
    ORDER BY
        CASE WHEN id ~ E'^ML_[0-9]+$' THEN CAST(SUBSTRING(id FROM 4) AS INTEGER) ELSE 9999 END,
        id
"""))
rows = result.fetchall()
print("Total: {} estaciones".format(len(rows)))
print()
for row in rows:
    extras = []
    if row[3]: extras.append("Cercanias: {}".format(row[3]))
    if row[4]: extras.append("Metro: {}".format(row[4]))
    cor_str = " -> " + ", ".join(extras) if extras else ""
    print("{} ({}) [{}]{}".format(row[0], row[1], row[2], cor_str))

print()
print("=" * 100)
print("CERCANIAS MADRID - TODAS LAS PARADAS")
print("=" * 100)
result = db.execute(text("""
    SELECT id, name, lineas, cor_metro, cor_ml, cor_tranvia
    FROM gtfs_stops
    WHERE id LIKE 'RENFE_%' AND nucleo_id = 10
    ORDER BY
        CASE WHEN id ~ E'^RENFE_[0-9]+$' THEN CAST(SUBSTRING(id FROM 7) AS INTEGER) ELSE 9999 END,
        id
"""))
rows = result.fetchall()
print("Total: {} estaciones".format(len(rows)))
print()
for row in rows:
    extras = []
    if row[3]: extras.append("Metro: {}".format(row[3]))
    if row[4]: extras.append("ML: {}".format(row[4]))
    if row[5]: extras.append("Tranvia: {}".format(row[5]))
    cor_str = " -> " + ", ".join(extras) if extras else ""
    print("{} ({}) [{}]{}".format(row[0], row[1], row[2], cor_str))
