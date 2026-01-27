#!/usr/bin/env python3
"""Generate stop_route_sequence using shapes and stop proximity.

Simple approach: for each line (short_name), find matching shape and order stops.

Usage:
    python scripts/generate_stop_sequences_simple.py
"""

import logging
import math
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def process_network(db, network_config):
    """Process a network configuration."""
    name = network_config['name']
    shape_prefix = network_config['shape_prefix']
    stop_prefix = network_config['stop_prefix']
    route_prefix = network_config['route_prefix']
    line_map = network_config.get('line_map', {})

    logger.info(f"\n=== Processing {name} ===")

    # Get stops
    stops = db.execute(text(
        "SELECT id, name, lat, lon FROM gtfs_stops WHERE id LIKE :p || '%' AND location_type IN (0,1)"
    ), {'p': stop_prefix}).fetchall()
    stops = [{'id': s[0], 'name': s[1], 'lat': s[2], 'lon': s[3]} for s in stops]
    logger.info(f"Found {len(stops)} stops")

    # Get routes
    routes = db.execute(text(
        "SELECT id, short_name FROM gtfs_routes WHERE id LIKE :p || '%'"
    ), {'p': route_prefix}).fetchall()
    logger.info(f"Found {len(routes)} routes")

    # Group routes by short_name (line)
    lines = {}
    for route_id, short_name in routes:
        if short_name not in lines:
            lines[short_name] = []
        lines[short_name].append(route_id)

    total = 0

    for line, route_ids in lines.items():
        # Find shape for this line
        shape_line = line_map.get(line, f"L{line}")
        shape_pattern = f"{shape_prefix}{shape_line}%"

        shape_pts = db.execute(text(
            "SELECT lat, lon, sequence FROM gtfs_shape_points WHERE shape_id LIKE :p ORDER BY shape_id, sequence LIMIT 500"
        ), {'p': shape_pattern}).fetchall()

        if not shape_pts:
            continue

        shape_pts = [{'lat': p[0], 'lon': p[1]} for p in shape_pts]

        # Match stops to shape
        matched = []
        for stop in stops:
            best_pos, best_dist = 0, float('inf')
            for i, pt in enumerate(shape_pts):
                d = haversine(stop['lat'], stop['lon'], pt['lat'], pt['lon'])
                if d < best_dist:
                    best_dist, best_pos = d, i
            if best_dist < 1000:  # 1km tolerance
                matched.append({'stop_id': stop['id'], 'pos': best_pos, 'dist': best_dist})

        matched.sort(key=lambda x: x['pos'])

        if matched:
            # Insert for all route variants of this line
            for route_id in route_ids:
                for i, m in enumerate(matched):
                    db.execute(text("""
                        INSERT INTO gtfs_stop_route_sequence (route_id, stop_id, sequence)
                        VALUES (:rid, :sid, :seq)
                        ON CONFLICT (route_id, stop_id) DO UPDATE SET sequence = EXCLUDED.sequence
                    """), {'rid': route_id, 'sid': m['stop_id'], 'seq': i + 1})
                    total += 1

            db.commit()
            logger.info(f"  Line {line}: {len(matched)} stops -> {len(route_ids)} routes")

    logger.info(f"Total sequences for {name}: {total}")
    return total


def main():
    # Network configurations
    networks = [
        {
            'name': 'Metrovalencia',
            'shape_prefix': 'METRO_VAL_',
            'stop_prefix': 'METRO_VAL',
            'route_prefix': 'METRO_VALENCIA',
            'line_map': {'1': 'L1', '2': 'L2', '3': 'L3', '4': 'L4', '5': 'L5',
                        '6': 'L6', '7': 'L7', '8': 'L8', '9': 'L9', '10': 'L10'}
        },
        {
            'name': 'TRAM Alicante',
            'shape_prefix': 'TRAM_ALI_',
            'stop_prefix': 'TRAM_ALI',
            'route_prefix': 'TRAM_ALI',
            'line_map': {'L1': 'L1', 'L2': 'L2', 'L3': 'L3', 'L4': 'L4', 'L5': 'L5', 'L9': 'L9'}
        },
        {
            'name': 'TRAM Barcelona',
            'shape_prefix': 'TRAM_BCN_',
            'stop_prefix': 'TRAM_BCN',
            'route_prefix': 'TRAM_BCN',
            'line_map': {'T1': 'T1', 'T2': 'T2', 'T3': 'T3', 'T4': 'T4', 'T5': 'T5', 'T6': 'T6'}
        },
    ]

    db = SessionLocal()
    try:
        grand_total = 0
        for net in networks:
            grand_total += process_network(db, net)
        logger.info(f"\n=== GRAND TOTAL: {grand_total} sequences ===")
    finally:
        db.close()


if __name__ == '__main__':
    main()
