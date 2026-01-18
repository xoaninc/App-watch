#!/usr/bin/env python3
"""Check distances between problematic stops."""
import sys
sys.path.insert(0, '/var/www/renfeserver')

from core.database import get_db
from sqlalchemy import text
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

db = next(get_db())

renfe = db.execute(text("SELECT id, name, lat, lon, lineas FROM gtfs_stops WHERE id LIKE 'RENFE_%' AND nucleo_id = 10")).fetchall()

# Verificar Puerta de Arganda
print('=== Puerta de Arganda vs RENFE cercanas ===')
pa = db.execute(text("SELECT lat, lon FROM gtfs_stops WHERE id = 'METRO_182'")).fetchone()
print(f'METRO_182 (Puerta de Arganda): {pa[0]}, {pa[1]}')
for r in renfe:
    dist = haversine(pa[0], pa[1], r[2], r[3])
    if dist < 200:
        print(f'  {r[0]} ({r[1]}): {dist:.0f}m - lineas: {r[4]}')

print()
print('=== Coslada Central vs RENFE cercanas ===')
cc = db.execute(text("SELECT lat, lon FROM gtfs_stops WHERE id = 'METRO_288'")).fetchone()
print(f'METRO_288 (Coslada Central): {cc[0]}, {cc[1]}')
for r in renfe:
    dist = haversine(cc[0], cc[1], r[2], r[3])
    if dist < 200:
        print(f'  {r[0]} ({r[1]}): {dist:.0f}m - lineas: {r[4]}')

print()
print('=== Parla Centro ML vs RENFE cercanas ===')
pc = db.execute(text("SELECT lat, lon FROM gtfs_stops WHERE id = 'ML_53'")).fetchone()
print(f'ML_53 (Parla Centro): {pc[0]}, {pc[1]}')
for r in renfe:
    dist = haversine(pc[0], pc[1], r[2], r[3])
    if dist < 200:
        print(f'  {r[0]} ({r[1]}): {dist:.0f}m - lineas: {r[4]}')
