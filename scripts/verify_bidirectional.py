#!/usr/bin/env python3
"""Verify all correspondences are bidirectional."""
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

# Get all stops with correspondences
all_stops = db.execute(text("""
    SELECT id, name, lineas, nucleo_id, lat, lon, cor_metro, cor_cercanias, cor_ml, cor_tranvia
    FROM gtfs_stops
    WHERE cor_metro IS NOT NULL OR cor_cercanias IS NOT NULL OR cor_ml IS NOT NULL OR cor_tranvia IS NOT NULL
    ORDER BY nucleo_id, id
""")).fetchall()

print("=" * 100)
print("VERIFICACION DE CORRESPONDENCIAS BIDIRECCIONALES")
print("=" * 100)
print()

errors = []
current_nucleo = None

for stop in all_stops:
    stop_id, name, lineas, nucleo_id, lat, lon, cor_metro, cor_cercanias, cor_ml, cor_tranvia = stop

    if nucleo_id != current_nucleo:
        current_nucleo = nucleo_id
        nucleo_name = db.execute(text("SELECT name FROM gtfs_nucleos WHERE id = :nid"), {"nid": nucleo_id}).fetchone()
        print()
        print("=" * 80)
        print("NUCLEO {} - {}".format(nucleo_id, nucleo_name[0] if nucleo_name else "Desconocido"))
        print("=" * 80)

    # Check cor_metro - should have inverse in METRO stops
    if cor_metro:
        # Find nearby Metro stops
        metro_stops = db.execute(text("""
            SELECT id, name, lineas, cor_cercanias, cor_ml
            FROM gtfs_stops
            WHERE id LIKE 'METRO_%' AND nucleo_id = :nid
        """), {"nid": nucleo_id}).fetchall()

        found_inverse = False
        for metro in metro_stops:
            dist = haversine(lat, lon,
                           db.execute(text("SELECT lat, lon FROM gtfs_stops WHERE id = :sid"), {"sid": metro[0]}).fetchone()[0],
                           db.execute(text("SELECT lat, lon FROM gtfs_stops WHERE id = :sid"), {"sid": metro[0]}).fetchone()[1])
            if dist < 200:  # Within 200m
                # Check if this metro has inverse correspondence
                if stop_id.startswith('RENFE_') and metro[3]:  # cor_cercanias
                    found_inverse = True
                    break
                elif stop_id.startswith('ML_') and metro[4]:  # cor_ml - not applicable, ML doesn't go to metro
                    found_inverse = True
                    break

        if not found_inverse and stop_id.startswith('RENFE_'):
            # Find the specific metro stop nearby
            for metro in metro_stops:
                m_coords = db.execute(text("SELECT lat, lon FROM gtfs_stops WHERE id = :sid"), {"sid": metro[0]}).fetchone()
                dist = haversine(lat, lon, m_coords[0], m_coords[1])
                if dist < 200:
                    if not metro[3]:  # No cor_cercanias
                        errors.append({
                            'type': 'MISSING_INVERSE',
                            'stop1': stop_id,
                            'stop1_name': name,
                            'stop1_cor': 'cor_metro: {}'.format(cor_metro),
                            'stop2': metro[0],
                            'stop2_name': metro[1],
                            'missing': 'cor_cercanias',
                            'distance': dist
                        })

    # Check cor_cercanias - should have inverse in RENFE stops
    if cor_cercanias:
        renfe_stops = db.execute(text("""
            SELECT id, name, lineas, cor_metro, cor_ml
            FROM gtfs_stops
            WHERE id LIKE 'RENFE_%' AND nucleo_id = :nid
        """), {"nid": nucleo_id}).fetchall()

        for renfe in renfe_stops:
            r_coords = db.execute(text("SELECT lat, lon FROM gtfs_stops WHERE id = :sid"), {"sid": renfe[0]}).fetchone()
            dist = haversine(lat, lon, r_coords[0], r_coords[1])
            if dist < 200:
                # Check inverse
                has_inverse = False
                if stop_id.startswith('METRO_') and renfe[3]:  # cor_metro
                    has_inverse = True
                elif stop_id.startswith('ML_') and renfe[4]:  # cor_ml
                    has_inverse = True
                elif stop_id.startswith('METRO_SEV_') and renfe[3]:
                    has_inverse = True
                elif stop_id.startswith('TRAM_SEV_') and renfe[3]:
                    has_inverse = True

                if not has_inverse:
                    errors.append({
                        'type': 'MISSING_INVERSE',
                        'stop1': stop_id,
                        'stop1_name': name,
                        'stop1_cor': 'cor_cercanias: {}'.format(cor_cercanias),
                        'stop2': renfe[0],
                        'stop2_name': renfe[1],
                        'missing': 'cor_metro or cor_ml',
                        'distance': dist
                    })

    # Check cor_ml - should have inverse in ML stops
    if cor_ml:
        ml_stops = db.execute(text("""
            SELECT id, name, lineas, cor_cercanias, cor_metro
            FROM gtfs_stops
            WHERE id LIKE 'ML_%' AND nucleo_id = :nid
        """), {"nid": nucleo_id}).fetchall()

        for ml in ml_stops:
            ml_coords = db.execute(text("SELECT lat, lon FROM gtfs_stops WHERE id = :sid"), {"sid": ml[0]}).fetchone()
            dist = haversine(lat, lon, ml_coords[0], ml_coords[1])
            if dist < 200:
                has_inverse = False
                if stop_id.startswith('RENFE_') and ml[3]:  # cor_cercanias
                    has_inverse = True
                elif stop_id.startswith('METRO_') and ml[4]:  # cor_metro
                    has_inverse = True

                if not has_inverse:
                    errors.append({
                        'type': 'MISSING_INVERSE',
                        'stop1': stop_id,
                        'stop1_name': name,
                        'stop1_cor': 'cor_ml: {}'.format(cor_ml),
                        'stop2': ml[0],
                        'stop2_name': ml[1],
                        'missing': 'cor_cercanias or cor_metro',
                        'distance': dist
                    })

    print("{} ({}) [{}]".format(stop_id, name, lineas))
    cors = []
    if cor_metro: cors.append("Metro: {}".format(cor_metro))
    if cor_cercanias: cors.append("Cercanias: {}".format(cor_cercanias))
    if cor_ml: cors.append("ML: {}".format(cor_ml))
    if cor_tranvia: cors.append("Tranvia: {}".format(cor_tranvia))
    if cors:
        print("  -> {}".format(", ".join(cors)))

print()
print("=" * 100)
print("ERRORES ENCONTRADOS: {}".format(len(errors)))
print("=" * 100)

if errors:
    for err in errors:
        print()
        print("FALTA CORRESPONDENCIA INVERSA:")
        print("  {} ({}) tiene {}".format(err['stop1'], err['stop1_name'], err['stop1_cor']))
        print("  {} ({}) NO tiene {} (dist: {:.0f}m)".format(err['stop2'], err['stop2_name'], err['missing'], err['distance']))
else:
    print()
    print("Todas las correspondencias son bidireccionales!")
