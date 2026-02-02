#!/usr/bin/env python3
"""Apply shape interpolations directly to the database.

This script reads interpolated points from shapes_interpolated.json and
inserts them into the gtfs_shape_points table, renumbering sequences.

Usage:
    python scripts/apply_shape_interpolations_db.py
    python scripts/apply_shape_interpolations_db.py --dry-run
    python scripts/apply_shape_interpolations_db.py --shape 20_C1
"""

import argparse
import json
import logging
from pathlib import Path

from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

INTERPOLATIONS_PATH = Path(__file__).parent.parent / "data" / "shapes_interpolated.json"


def load_interpolations(path: Path) -> dict:
    """Load interpolated points from JSON file."""
    if not path.exists():
        logger.error(f"Interpolations file not found: {path}")
        return {}

    with open(path, 'r') as f:
        return json.load(f)


def get_shape_points(db, shape_id: str) -> list:
    """Get all points for a shape from the database."""
    result = db.execute(text("""
        SELECT sequence, lat, lon, dist_traveled
        FROM gtfs_shape_points
        WHERE shape_id = :shape_id
        ORDER BY sequence
    """), {'shape_id': shape_id})

    return [{'seq': row[0], 'lat': row[1], 'lon': row[2], 'dist': row[3]} for row in result]


def apply_interpolations_to_db(interpolations: dict, dry_run: bool = False, shape_filter: str = None):
    """Apply interpolations to the database."""
    db = SessionLocal()

    try:
        for shape_id, interp_points in interpolations.items():
            if shape_filter and shape_id != shape_filter:
                continue

            logger.info(f"\nProcessing shape {shape_id}")

            # Get existing points
            existing = get_shape_points(db, shape_id)
            logger.info(f"  Existing points: {len(existing)}")
            logger.info(f"  Interpolated points to add: {len(interp_points)}")

            if not existing:
                logger.warning(f"  Shape {shape_id} not found in database")
                continue

            # Merge existing and interpolated points
            merged = []

            # Add existing points with their original sequence as float
            for p in existing:
                merged.append({
                    'seq': float(p['seq']),
                    'lat': p['lat'],
                    'lon': p['lon'],
                    'dist': p['dist'],
                    'interpolated': False
                })

            # Add interpolated points
            for p in interp_points:
                merged.append({
                    'seq': p['seq'],
                    'lat': p['lat'],
                    'lon': p['lon'],
                    'dist': None,
                    'interpolated': True
                })

            # Sort by sequence
            merged.sort(key=lambda x: x['seq'])

            # Renumber with integer sequences starting from 1
            for i, p in enumerate(merged):
                p['new_seq'] = i + 1

            logger.info(f"  Total points after merge: {len(merged)}")

            # Find where interpolations were inserted
            interp_count = sum(1 for p in merged if p['interpolated'])
            logger.info(f"  Points marked as interpolated: {interp_count}")

            if dry_run:
                logger.info("  [DRY RUN] Would update database")
                # Show sample of interpolated points
                for p in merged:
                    if p['interpolated']:
                        logger.info(f"    New point: seq {p['new_seq']}, lat={p['lat']:.6f}, lon={p['lon']:.6f}")
                continue

            # Delete existing points for this shape
            logger.info("  Deleting existing points...")
            db.execute(text("""
                DELETE FROM gtfs_shape_points WHERE shape_id = :shape_id
            """), {'shape_id': shape_id})

            # Insert all points with new sequences
            logger.info("  Inserting merged points...")
            for p in merged:
                db.execute(text("""
                    INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon, dist_traveled)
                    VALUES (:shape_id, :sequence, :lat, :lon, :dist)
                """), {
                    'shape_id': shape_id,
                    'sequence': p['new_seq'],
                    'lat': p['lat'],
                    'lon': p['lon'],
                    'dist': p['dist']
                })

            db.commit()
            logger.info(f"  Successfully updated {shape_id} with {len(merged)} points")

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description='Apply shape interpolations to database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--shape', type=str, help='Only process specific shape ID')
    parser.add_argument('--interpolations', type=str, help='Path to interpolations JSON')
    args = parser.parse_args()

    interp_path = Path(args.interpolations) if args.interpolations else INTERPOLATIONS_PATH
    interpolations = load_interpolations(interp_path)

    if not interpolations:
        logger.error("No interpolations to apply")
        return

    logger.info(f"Loaded interpolations for {len(interpolations)} shapes")

    apply_interpolations_to_db(interpolations, dry_run=args.dry_run, shape_filter=args.shape)

    logger.info("\nDone!")


if __name__ == "__main__":
    main()
