#!/usr/bin/env python3
"""Pre-generate walking shapes for important correspondences.

Generates pedestrian routes using BRouter for all correspondences
that don't have cached shapes yet. Can be run incrementally.

Usage:
    python scripts/pregenerate_walking_shapes.py
    python scripts/pregenerate_walking_shapes.py --limit 50  # Process only 50
    python scripts/pregenerate_walking_shapes.py --dry-run   # Show what would be done
"""

import sys
import time
import argparse
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import SessionLocal
from adapters.http.api.gtfs.utils.walking_route import generate_walking_route, coords_to_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def pregenerate_shapes(limit: int = None, dry_run: bool = False):
    """Generate walking shapes for correspondences that don't have them."""
    db = SessionLocal()

    try:
        # Get correspondences without shapes
        # Exclude same-station correspondences (internal passages)
        query = """
            SELECT c.id, c.from_stop_id, c.to_stop_id,
                   s1.lat as from_lat, s1.lon as from_lon, s1.name as from_name,
                   s2.lat as to_lat, s2.lon as to_lon, s2.name as to_name
            FROM stop_correspondence c
            JOIN gtfs_stops s1 ON s1.id = c.from_stop_id
            JOIN gtfs_stops s2 ON s2.id = c.to_stop_id
            WHERE c.walking_shape IS NULL
              AND NOT (
                  LOWER(s1.name) = LOWER(s2.name)
                  OR LOWER(REPLACE(s1.name, ' ', '')) = LOWER(REPLACE(s2.name, ' ', ''))
                  OR s1.name LIKE s2.name || '%'
                  OR s2.name LIKE s1.name || '%'
              )
            ORDER BY c.id
        """
        if limit:
            query += f" LIMIT {limit}"

        result = db.execute(text(query)).fetchall()

        logger.info(f"Found {len(result)} correspondences without shapes")

        if dry_run:
            logger.info("[DRY-RUN] Would generate shapes for:")
            for row in result[:10]:
                logger.info(f"  {row[5]} -> {row[8]}")
            if len(result) > 10:
                logger.info(f"  ... and {len(result) - 10} more")
            return

        success = 0
        failed = 0

        for row in result:
            corr_id = row[0]
            from_name, to_name = row[5], row[8]
            from_lat, from_lon = row[3], row[4]
            to_lat, to_lon = row[6], row[7]

            logger.info(f"Generating: {from_name} -> {to_name}")

            route_result = generate_walking_route(from_lat, from_lon, to_lat, to_lon)

            if route_result:
                coords, distance_m, walk_time_s = route_result
                shape_json = coords_to_json(coords)

                db.execute(text("""
                    UPDATE stop_correspondence
                    SET walking_shape = :shape,
                        distance_m = COALESCE(distance_m, :dist),
                        walk_time_s = COALESCE(walk_time_s, :time)
                    WHERE id = :id
                """), {
                    'shape': shape_json,
                    'dist': distance_m,
                    'time': walk_time_s,
                    'id': corr_id
                })
                db.commit()

                logger.info(f"  OK: {len(coords)} points, {distance_m}m, {walk_time_s}s")
                success += 1
            else:
                logger.warning(f"  FAILED: Could not generate route")
                failed += 1

            # Rate limiting for BRouter
            time.sleep(0.5)

        logger.info(f"\nCompleted: {success} success, {failed} failed")

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description='Pre-generate walking shapes')
    parser.add_argument('--limit', type=int, help='Maximum number to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()

    pregenerate_shapes(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
