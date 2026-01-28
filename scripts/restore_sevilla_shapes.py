#!/usr/bin/env python3
"""Restore Sevilla shapes from backup.

Usage:
    python scripts/restore_sevilla_shapes.py backups/sevilla_shapes_backup_20260128.json
    python scripts/restore_sevilla_shapes.py backups/sevilla_shapes_backup_20260128.json --dry-run
"""

import sys
import json
import argparse
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def restore_shapes(backup_file: str, dry_run: bool = False):
    """Restore shapes from backup JSON file."""

    with open(backup_file, 'r') as f:
        backup = json.load(f)

    logger.info(f"Backup from: {backup['timestamp']}")
    logger.info(f"Description: {backup['description']}")
    logger.info(f"Shapes to restore: {len(backup['shapes'])}")

    if dry_run:
        logger.info("[DRY-RUN] Would restore:")
        for shape_id, points in backup['shapes'].items():
            logger.info(f"  {shape_id}: {len(points)} points")
        return

    db = SessionLocal()

    try:
        # Restore shapes
        for shape_id, points in backup['shapes'].items():
            # Delete existing
            db.execute(text("DELETE FROM gtfs_shape_points WHERE shape_id = :sid"), {'sid': shape_id})

            # Ensure shape exists
            db.execute(text("INSERT INTO gtfs_shapes (id) VALUES (:sid) ON CONFLICT DO NOTHING"), {'sid': shape_id})

            # Insert points
            for pt in points:
                db.execute(text("""
                    INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon, dist_traveled)
                    VALUES (:sid, :seq, :lat, :lon, :dist)
                """), {
                    'sid': shape_id,
                    'seq': pt['seq'],
                    'lat': pt['lat'],
                    'lon': pt['lon'],
                    'dist': pt['dist']
                })

            logger.info(f"Restored {shape_id}: {len(points)} points")

        # Restore trip assignments
        for route_id, info in backup['trip_assignments'].items():
            shape_id = info['shape_id']
            db.execute(text("""
                UPDATE gtfs_trips SET shape_id = :shape_id
                WHERE route_id = :route_id
            """), {'shape_id': shape_id, 'route_id': route_id})
            logger.info(f"Assigned {route_id} -> {shape_id}")

        db.commit()
        logger.info("Restore completed successfully!")

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description='Restore Sevilla shapes from backup')
    parser.add_argument('backup_file', help='Path to backup JSON file')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be restored')
    args = parser.parse_args()

    restore_shapes(args.backup_file, args.dry_run)


if __name__ == "__main__":
    main()
