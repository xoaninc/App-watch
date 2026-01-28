#!/usr/bin/env python3
"""Generate shapes for Metro Madrid lines using BRouter.

Metro Madrid GTFS doesn't include shapes.txt, so we generate shapes
by routing between consecutive stations using BRouter's trekking profile.

This creates realistic route geometries that follow streets/paths
between station coordinates.
"""

import os
import sys
import time
import logging
import argparse
from typing import List, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# BRouter configuration
BROUTER_URL = "https://brouter.de/brouter"
BROUTER_PROFILE = "trekking"
REQUEST_TIMEOUT = 30.0
RATE_LIMIT_DELAY = 0.5  # seconds between requests to avoid rate limiting


def get_brouter_route(
    from_lat: float, from_lon: float,
    to_lat: float, to_lon: float
) -> Optional[List[Tuple[float, float]]]:
    """Get route from BRouter between two points.

    Returns list of (lat, lon) tuples or None if failed.
    """
    # Note: alternativeidx=0 is required for BRouter to work reliably
    url = (
        f"{BROUTER_URL}?lonlats={from_lon},{from_lat}|{to_lon},{to_lat}"
        f"&profile={BROUTER_PROFILE}&alternativeidx=0&format=geojson"
    )

    try:
        response = httpx.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        if response.status_code != 200:
            logger.warning(f"BRouter error {response.status_code}")
            return None

        data = response.json()
        coords_raw = data["features"][0]["geometry"]["coordinates"]

        # Convert from [lon, lat] to (lat, lon)
        return [(c[1], c[0]) for c in coords_raw]

    except Exception as e:
        logger.warning(f"BRouter request failed: {e}")
        return None


def get_line_stops(db, route_id: str) -> List[Tuple[str, str, float, float]]:
    """Get stops for a Metro line in sequence order.

    Returns list of (stop_id, name, lat, lon) tuples.
    """
    result = db.execute(text('''
        SELECT s.id, s.name, s.lat, s.lon
        FROM gtfs_stop_route_sequence srs
        JOIN gtfs_stops s ON srs.stop_id = s.id
        WHERE srs.route_id = :route_id
        ORDER BY srs.sequence
    '''), {'route_id': route_id}).fetchall()

    return [(r[0], r[1], float(r[2]), float(r[3])) for r in result]


def generate_line_shape(db, route_id: str, dry_run: bool = False) -> int:
    """Generate shape for a Metro line by routing between stations.

    Returns number of points in the generated shape.
    """
    stops = get_line_stops(db, route_id)

    if len(stops) < 2:
        logger.warning(f"Route {route_id} has less than 2 stops, skipping")
        return 0

    logger.info(f"Generating shape for {route_id}: {len(stops)} stops")

    all_coords = []

    for i in range(len(stops) - 1):
        from_stop = stops[i]
        to_stop = stops[i + 1]

        logger.debug(f"  Routing: {from_stop[1]} → {to_stop[1]}")

        # Get route from BRouter
        coords = get_brouter_route(
            from_stop[2], from_stop[3],
            to_stop[2], to_stop[3]
        )

        if coords:
            # Skip first point if not first segment (to avoid duplicates)
            if all_coords:
                coords = coords[1:]
            all_coords.extend(coords)
            logger.debug(f"    Got {len(coords)} points")
        else:
            # Fallback: straight line between stops
            logger.warning(f"    BRouter failed, using straight line")
            if all_coords:
                all_coords.append((to_stop[2], to_stop[3]))
            else:
                all_coords.append((from_stop[2], from_stop[3]))
                all_coords.append((to_stop[2], to_stop[3]))

        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)

    if not all_coords:
        logger.warning(f"No coordinates generated for {route_id}")
        return 0

    logger.info(f"Generated {len(all_coords)} points for {route_id}")

    if dry_run:
        return len(all_coords)

    # Save to database
    # Shape ID format: METRO_MAD_<line>_BROUTER
    line_num = route_id.replace('METRO_', '')
    shape_id = f"METRO_MAD_{line_num}_BROUTER"

    # Delete existing shape points first (due to FK constraint)
    db.execute(text('DELETE FROM gtfs_shape_points WHERE shape_id = :shape_id'),
               {'shape_id': shape_id})

    # Insert or update shape record
    db.execute(text('''
        INSERT INTO gtfs_shapes (id)
        VALUES (:shape_id)
        ON CONFLICT (id) DO NOTHING
    '''), {'shape_id': shape_id})

    # Insert new shape points
    for seq, (lat, lon) in enumerate(all_coords):
        db.execute(text('''
            INSERT INTO gtfs_shape_points (shape_id, lat, lon, sequence)
            VALUES (:shape_id, :lat, :lon, :seq)
        '''), {'shape_id': shape_id, 'lat': lat, 'lon': lon, 'seq': seq})

    # Update trips to use this shape
    db.execute(text('''
        UPDATE gtfs_trips SET shape_id = :shape_id
        WHERE route_id = :route_id
    '''), {'shape_id': shape_id, 'route_id': route_id})

    db.commit()
    logger.info(f"Saved shape {shape_id} with {len(all_coords)} points")

    return len(all_coords)


def main():
    parser = argparse.ArgumentParser(description='Generate Metro Madrid shapes using BRouter')
    parser.add_argument('--route', type=str, help='Generate for specific route (e.g., METRO_10)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without saving')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        # Get all Metro Madrid routes
        if args.route:
            routes = [(args.route,)]
        else:
            result = db.execute(text('''
                SELECT DISTINCT id FROM gtfs_routes
                WHERE id LIKE 'METRO_%'
                AND id NOT LIKE 'METRO_VAL%'
                AND id NOT LIKE 'METRO_SEV%'
                AND id NOT LIKE 'METRO_MAL%'
                AND id NOT LIKE 'METRO_GRA%'
                AND id NOT LIKE 'METRO_TEN%'
                AND id NOT LIKE 'METRO_BILBAO%'
                ORDER BY id
            ''')).fetchall()
            routes = result

        total_points = 0
        for (route_id,) in routes:
            points = generate_line_shape(db, route_id, dry_run=args.dry_run)
            total_points += points

        logger.info("=" * 60)
        logger.info(f"TOTAL: {len(routes)} lines, {total_points:,} points")
        if args.dry_run:
            logger.info("[DRY RUN - no changes saved]")
        logger.info("=" * 60)

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
