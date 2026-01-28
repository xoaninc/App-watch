#!/usr/bin/env python3
"""Fix C5 Cercanías Sevilla shape to include Dos Hermanas.

The C5 shape currently ends at Bellavista but should extend to Dos Hermanas.
This script regenerates the shape using BRouter rail routing.

Usage:
    python scripts/fix_c5_shape.py
    python scripts/fix_c5_shape.py --dry-run  # Preview without making changes
"""

import sys
import time
import argparse
import logging
from pathlib import Path

import httpx

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# C5 stops in order (Benacazón to Dos Hermanas)
C5_STOPS = [
    ("Benacazón", 37.3569021, -6.208323),
    ("Sanlúcar la Mayor", 37.3813983, -6.2077107),
    ("Villanueva del Ariscal", 37.4070993, -6.1359773),
    ("Salteras", 37.4102351, -6.102884),
    ("Valencina-Santiponce", 37.4267612, -6.067665),
    ("Camas", 37.4176788, -6.0234312),
    ("San Jerónimo", 37.4332477, -5.9931946),
    ("Santa Justa", 37.3925116, -5.974551),
    ("San Bernardo RENFE", 37.3778455, -5.973217),
    ("Virgen del Rocío", 37.3627962, -5.9746041),
    ("Jardines de Hércules", 37.3328862, -5.9711093),
    ("Bellavista", 37.3214856, -5.9642475),
    ("Dos Hermanas", 37.2872212, -5.9238949),
]

BROUTER_URL = "https://brouter.de/brouter"
OSRM_URL = "https://router.project-osrm.org/route/v1/foot"
SHAPE_ID = "30_C5_FULL"


def get_segment_route(from_stop: tuple, to_stop: tuple) -> list:
    """Generate route for a single segment using BRouter or OSRM."""
    from_name, from_lat, from_lon = from_stop
    to_name, to_lat, to_lon = to_stop

    # Try BRouter trekking first
    lonlats = f"{from_lon},{from_lat}|{to_lon},{to_lat}"
    url = f"{BROUTER_URL}?lonlats={lonlats}&profile=trekking&format=geojson"

    try:
        response = httpx.get(url, timeout=30.0)
        if response.status_code == 200:
            data = response.json()
            feature = data['features'][0]
            coords_raw = feature['geometry']['coordinates']
            coords = [(c[1], c[0]) for c in coords_raw]
            logger.debug(f"BRouter: {from_name} → {to_name}: {len(coords)} points")
            return coords
    except Exception as e:
        logger.debug(f"BRouter failed: {e}")

    # Fallback to OSRM
    osrm_url = f"{OSRM_URL}/{from_lon},{from_lat};{to_lon},{to_lat}?overview=full&geometries=geojson"

    try:
        response = httpx.get(osrm_url, timeout=30.0)
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 'Ok' and data.get('routes'):
                route = data['routes'][0]
                coords_raw = route['geometry']['coordinates']
                coords = [(c[1], c[0]) for c in coords_raw]
                logger.debug(f"OSRM: {from_name} → {to_name}: {len(coords)} points")
                return coords
    except Exception as e:
        logger.debug(f"OSRM failed: {e}")

    # Last resort: straight line
    logger.debug(f"Using straight line: {from_name} → {to_name}")
    return [(from_lat, from_lon), (to_lat, to_lon)]


def get_full_route(stops: list) -> list:
    """Generate full route by connecting all stops segment by segment."""
    all_coords = []

    logger.info(f"Generating route for {len(stops)} stops...")

    for i in range(len(stops) - 1):
        segment = get_segment_route(stops[i], stops[i + 1])
        if segment:
            # Skip first point of segment if it duplicates last point
            if all_coords and segment:
                start_idx = 1 if (abs(all_coords[-1][0] - segment[0][0]) < 0.0001 and
                                  abs(all_coords[-1][1] - segment[0][1]) < 0.0001) else 0
                all_coords.extend(segment[start_idx:])
            else:
                all_coords.extend(segment)

        # Small delay to avoid rate limiting
        time.sleep(0.3)

    logger.info(f"Total route: {len(all_coords)} points")

    # Check coverage
    if all_coords:
        lats = [c[0] for c in all_coords]
        logger.info(f"Lat range: {min(lats):.4f} to {max(lats):.4f}")
        logger.info(f"Expected: {stops[0][1]:.4f} to {stops[-1][1]:.4f}")

    return all_coords


def update_shape(db, coords: list, dry_run: bool = False):
    """Update the shape in the database."""
    if dry_run:
        logger.info(f"[DRY-RUN] Would insert {len(coords)} points for shape {SHAPE_ID}")
        return

    # Check if shape exists
    existing = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_shapes WHERE id = :sid"
    ), {"sid": SHAPE_ID}).fetchone()[0]

    if existing == 0:
        # Create shape entry
        db.execute(text(
            "INSERT INTO gtfs_shapes (id) VALUES (:sid)"
        ), {"sid": SHAPE_ID})
        logger.info(f"Created shape {SHAPE_ID}")

    # Delete old points
    db.execute(text(
        "DELETE FROM gtfs_shape_points WHERE shape_id = :sid"
    ), {"sid": SHAPE_ID})

    # Insert new points
    for seq, (lat, lon) in enumerate(coords, start=1):
        db.execute(text("""
            INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon)
            VALUES (:sid, :seq, :lat, :lon)
        """), {"sid": SHAPE_ID, "seq": seq, "lat": lat, "lon": lon})

    db.commit()
    logger.info(f"Inserted {len(coords)} points for shape {SHAPE_ID}")


def update_trips(db, dry_run: bool = False):
    """Update C5 trips to use the new shape."""
    # Get trips count
    count = db.execute(text("""
        SELECT COUNT(*)
        FROM gtfs_trips t
        JOIN gtfs_routes r ON t.route_id = r.id
        WHERE r.network_id = '30T' AND r.short_name = 'C5'
    """)).fetchone()[0]

    if dry_run:
        logger.info(f"[DRY-RUN] Would update {count} trips to use shape {SHAPE_ID}")
        return count

    # Update trips
    db.execute(text("""
        UPDATE gtfs_trips t
        SET shape_id = :sid
        FROM gtfs_routes r
        WHERE t.route_id = r.id
          AND r.network_id = '30T'
          AND r.short_name = 'C5'
    """), {"sid": SHAPE_ID})

    db.commit()
    logger.info(f"Updated {count} trips to use shape {SHAPE_ID}")
    return count


def verify_fix(db):
    """Verify the fix was applied correctly."""
    # Check shape points
    result = db.execute(text("""
        SELECT COUNT(*), MIN(lat), MAX(lat)
        FROM gtfs_shape_points
        WHERE shape_id = :sid
    """), {"sid": SHAPE_ID}).fetchone()

    logger.info(f"Shape {SHAPE_ID}: {result[0]} points, lat range {result[1]:.4f} - {result[2]:.4f}")

    # Check trips
    result2 = db.execute(text("""
        SELECT COUNT(*)
        FROM gtfs_trips t
        JOIN gtfs_routes r ON t.route_id = r.id
        WHERE r.network_id = '30T' AND r.short_name = 'C5' AND t.shape_id = :sid
    """), {"sid": SHAPE_ID}).fetchone()

    logger.info(f"Trips using shape: {result2[0]}")

    # Verify it reaches Dos Hermanas
    if result[1] and result[1] < 37.30:
        logger.info("✓ Shape now reaches Dos Hermanas (lat < 37.30)")
        return True
    else:
        logger.warning("✗ Shape may not reach Dos Hermanas")
        return False


def main():
    parser = argparse.ArgumentParser(description='Fix C5 shape to include Dos Hermanas')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        # Generate route with BRouter segment by segment
        coords = get_full_route(C5_STOPS)

        if not coords:
            logger.error("Failed to generate route")
            return 1

        # Update shape
        update_shape(db, coords, args.dry_run)

        # Update trips
        update_trips(db, args.dry_run)

        # Verify
        if not args.dry_run:
            verify_fix(db)

        logger.info("Done!")
        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
