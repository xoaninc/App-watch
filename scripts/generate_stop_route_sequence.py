#!/usr/bin/env python3
"""Generate stop_route_sequence from shapes and stops proximity.

For networks that have shapes but no stop_route_sequence, this script:
1. Gets all stops for the network
2. Gets shape points for each route
3. Orders stops by proximity to shape points
4. Creates stop_route_sequence entries

Usage:
    python scripts/generate_stop_route_sequence.py METRO_VAL
    python scripts/generate_stop_route_sequence.py TRAM_ALI
    python scripts/generate_stop_route_sequence.py TRAM_BCN
"""

import argparse
import logging
import math
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two points."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def get_routes_with_shapes(db, prefix: str) -> list:
    """Get routes that have shapes."""
    result = db.execute(text("""
        SELECT DISTINCT r.id, r.short_name
        FROM gtfs_routes r
        JOIN gtfs_trips t ON r.id = t.route_id OR t.shape_id LIKE r.id || '%'
        JOIN gtfs_shape_points sp ON sp.shape_id LIKE :prefix || '%'
        WHERE r.id LIKE :prefix || '%'
        ORDER BY r.id
    """), {'prefix': prefix}).fetchall()

    if not result:
        # Try direct shape match
        result = db.execute(text("""
            SELECT DISTINCT r.id, r.short_name
            FROM gtfs_routes r
            WHERE r.id LIKE :prefix || '%'
            ORDER BY r.id
        """), {'prefix': prefix}).fetchall()

    return [(row[0], row[1]) for row in result]


def get_network_stops(db, prefix: str) -> list:
    """Get all stops for a network prefix."""
    result = db.execute(text("""
        SELECT id, name, lat, lon
        FROM gtfs_stops
        WHERE id LIKE :prefix || '%'
        AND location_type IN (0, 1)
        ORDER BY id
    """), {'prefix': prefix}).fetchall()
    return [{'id': r[0], 'name': r[1], 'lat': r[2], 'lon': r[3]} for r in result]


def get_shape_points(db, shape_prefix: str) -> list:
    """Get shape points ordered by sequence."""
    result = db.execute(text("""
        SELECT shape_id, lat, lon, sequence
        FROM gtfs_shape_points
        WHERE shape_id LIKE :prefix || '%'
        ORDER BY shape_id, sequence
    """), {'prefix': shape_prefix}).fetchall()
    return [{'shape_id': r[0], 'lat': r[1], 'lon': r[2], 'seq': r[3]} for r in result]


def find_closest_shape_position(stop, shape_points):
    """Find the position along the shape where stop is closest."""
    min_dist = float('inf')
    best_pos = 0

    for i, pt in enumerate(shape_points):
        dist = haversine_distance(stop['lat'], stop['lon'], pt['lat'], pt['lon'])
        if dist < min_dist:
            min_dist = dist
            best_pos = i

    return best_pos, min_dist


def generate_sequence_for_route(db, route_id: str, stops: list, shape_prefix: str, max_distance: float = 500) -> list:
    """Generate stop sequence for a route based on shape proximity."""

    # Get shape points for this route
    shape_points = get_shape_points(db, shape_prefix)
    if not shape_points:
        return []

    # Find closest position for each stop
    stop_positions = []
    for stop in stops:
        pos, dist = find_closest_shape_position(stop, shape_points)
        if dist <= max_distance:  # Only include stops within max_distance meters of shape
            stop_positions.append({
                'stop_id': stop['id'],
                'position': pos,
                'distance': dist
            })

    # Sort by position along shape
    stop_positions.sort(key=lambda x: x['position'])

    # Create sequence
    sequence = []
    for i, sp in enumerate(stop_positions):
        sequence.append({
            'route_id': route_id,
            'stop_id': sp['stop_id'],
            'sequence': i + 1
        })

    return sequence


def generate_for_network(db, prefix: str, dry_run: bool):
    """Generate stop_route_sequence for a network."""

    # Map prefixes to stop prefixes (sometimes different)
    stop_prefix_map = {
        'METRO_VAL': 'METRO_VAL',
        'TRAM_ALI': 'TRAM_ALI',
        'TRAM_BCN': 'TRAM_BCN',
        'METRO_MAL': 'METRO_MAL',
        'METRO_TEN': 'METRO_TEN',
        'TRAM_SEV': 'TRAM_SEV',
    }

    stop_prefix = stop_prefix_map.get(prefix, prefix)

    # Get stops
    stops = get_network_stops(db, stop_prefix)
    logger.info(f"Found {len(stops)} stops for {stop_prefix}")

    if not stops:
        logger.error(f"No stops found for prefix {stop_prefix}")
        return

    # Get routes
    routes = db.execute(text(
        "SELECT id, short_name FROM gtfs_routes WHERE id LIKE :prefix || '%' ORDER BY id"
    ), {'prefix': prefix}).fetchall()

    logger.info(f"Found {len(routes)} routes for {prefix}")

    # Clear existing
    if not dry_run:
        db.execute(text("DELETE FROM gtfs_stop_route_sequence WHERE route_id LIKE :prefix || '%'"), {'prefix': prefix})
        db.commit()

    total_sequences = 0

    for route_id, short_name in routes:
        # Try to find matching shape
        shape_prefix = route_id.replace('METRO_VALENCIA_', 'METRO_VAL_')

        # Get shape points directly for this route pattern
        shape_result = db.execute(text("""
            SELECT DISTINCT shape_id FROM gtfs_shape_points
            WHERE shape_id LIKE :pattern
            LIMIT 1
        """), {'pattern': f'%{short_name}%'}).fetchone()

        if shape_result:
            shape_id = shape_result[0]
            # Get shape points for this specific shape
            pts = db.execute(text("""
                SELECT lat, lon, sequence FROM gtfs_shape_points
                WHERE shape_id = :sid ORDER BY sequence
            """), {'sid': shape_id}).fetchall()

            if pts:
                shape_points = [{'lat': p[0], 'lon': p[1], 'seq': p[2]} for p in pts]

                # Match stops to shape
                stop_positions = []
                for stop in stops:
                    pos, dist = find_closest_shape_position(stop, shape_points)
                    if dist <= 800:  # 800m tolerance
                        stop_positions.append({
                            'stop_id': stop['id'],
                            'position': pos,
                            'distance': dist
                        })

                # Sort and create sequence
                stop_positions.sort(key=lambda x: x['position'])

                if stop_positions:
                    for i, sp in enumerate(stop_positions):
                        if not dry_run:
                            db.execute(text("""
                                INSERT INTO gtfs_stop_route_sequence (route_id, stop_id, sequence)
                                VALUES (:route_id, :stop_id, :seq)
                                ON CONFLICT (route_id, stop_id) DO UPDATE SET sequence = EXCLUDED.sequence
                            """), {'route_id': route_id, 'stop_id': sp['stop_id'], 'seq': i + 1})
                        total_sequences += 1

                    if not dry_run:
                        db.commit()

                    logger.info(f"  {route_id} ({short_name}): {len(stop_positions)} stops")

    logger.info(f"\n{'DRY RUN - ' if dry_run else ''}Total sequences created: {total_sequences}")


def main():
    parser = argparse.ArgumentParser(description='Generate stop_route_sequence from shapes')
    parser.add_argument('prefix', help='Route prefix (e.g., METRO_VAL, TRAM_ALI)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--max-distance', type=float, default=500, help='Max distance from shape (meters)')
    args = parser.parse_args()

    db = SessionLocal()
    try:
        generate_for_network(db, args.prefix, args.dry_run)
    finally:
        db.close()


if __name__ == '__main__':
    main()
