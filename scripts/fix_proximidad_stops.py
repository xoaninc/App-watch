#!/usr/bin/env python3
"""Fix Proximidad stop mappings.

This script:
1. Migrates María Zambrano stop_times from RENFE_54413 (Proximidad) to RENFE_54500 (Cercanías)
   - Cercanías stop_id must be preserved for GTFS-RT compatibility
   - Proximidad services should appear at the same station

2. Creates correspondence between Cartagena stations:
   - RENFE_5951 (Cartagena-Plaza Bastarreche) - FEVE
   - RENFE_61307 (Cartagena) - Proximidad
   - Walking distance: ~320m, ~4 min (calculated from OSM coordinates)

Usage:
    python scripts/fix_proximidad_stops.py
    python scripts/fix_proximidad_stops.py --dry-run
"""

import sys
import os
import argparse
import logging
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_maria_zambrano(db, dry_run: bool = False):
    """Migrate Proximidad stop_times from RENFE_54413 to RENFE_54500."""
    logger.info("=== María Zambrano Migration ===")

    # Check current state
    result = db.execute(text("""
        SELECT COUNT(*) FROM gtfs_stop_times WHERE stop_id = 'RENFE_54413'
    """))
    count_54413 = result.scalar()

    result = db.execute(text("""
        SELECT COUNT(*) FROM gtfs_stop_times WHERE stop_id = 'RENFE_54500'
    """))
    count_54500 = result.scalar()

    logger.info(f"Before migration:")
    logger.info(f"  RENFE_54413 (Proximidad): {count_54413} stop_times")
    logger.info(f"  RENFE_54500 (Cercanías): {count_54500} stop_times")

    if count_54413 == 0:
        logger.info("No Proximidad stop_times to migrate for María Zambrano")
        return

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {count_54413} stop_times from 54413 to 54500")
        return

    # Migrate stop_times
    result = db.execute(text("""
        UPDATE gtfs_stop_times
        SET stop_id = 'RENFE_54500'
        WHERE stop_id = 'RENFE_54413'
    """))
    migrated = result.rowcount
    logger.info(f"Migrated {migrated} stop_times from RENFE_54413 to RENFE_54500")

    # Check if RENFE_54413 stop can be deleted (no remaining references)
    result = db.execute(text("""
        SELECT COUNT(*) FROM gtfs_stop_times WHERE stop_id = 'RENFE_54413'
    """))
    remaining = result.scalar()

    if remaining == 0:
        # Delete the orphaned stop
        db.execute(text("DELETE FROM gtfs_stops WHERE id = 'RENFE_54413'"))
        logger.info("Deleted orphaned stop RENFE_54413")

    # Verify final state
    result = db.execute(text("""
        SELECT COUNT(*) FROM gtfs_stop_times WHERE stop_id = 'RENFE_54500'
    """))
    final_count = result.scalar()
    logger.info(f"After migration: RENFE_54500 has {final_count} stop_times")


def create_cartagena_correspondence(db, dry_run: bool = False):
    """Create correspondence between Cartagena FEVE and Proximidad stations.

    Coordinates (from OSM):
    - RENFE_5951 (FEVE): 37.6036154, -0.9773265
    - RENFE_61307 (Proximidad): 37.604967, -0.975122

    Calculated:
    - Straight-line: 246m
    - Walking estimate: ~320m (30% street factor)
    - Walking time: ~255 seconds (4.3 min at 4.5 km/h)
    """
    logger.info("=== Cartagena Correspondence ===")

    # OSM-calculated values
    distance_m = 320  # meters (with street routing factor)
    walk_time_s = 255  # seconds (~4.3 minutes)

    # Check if correspondence already exists
    result = db.execute(text("""
        SELECT COUNT(*) FROM stop_correspondence
        WHERE (from_stop_id = 'RENFE_5951' AND to_stop_id = 'RENFE_61307')
           OR (from_stop_id = 'RENFE_61307' AND to_stop_id = 'RENFE_5951')
    """))
    existing = result.scalar()

    if existing > 0:
        logger.info(f"Cartagena correspondence already exists ({existing} entries)")
        return

    if dry_run:
        logger.info(f"[DRY RUN] Would create Cartagena correspondence: {distance_m}m, {walk_time_s}s")
        return

    # Create bidirectional correspondence
    db.execute(text("""
        INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
        VALUES ('RENFE_5951', 'RENFE_61307', :distance, :time, 'osm')
        ON CONFLICT DO NOTHING
    """), {'distance': distance_m, 'time': walk_time_s})

    db.execute(text("""
        INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
        VALUES ('RENFE_61307', 'RENFE_5951', :distance, :time, 'osm')
        ON CONFLICT DO NOTHING
    """), {'distance': distance_m, 'time': walk_time_s})

    logger.info(f"Created Cartagena correspondence: RENFE_5951 <-> RENFE_61307")
    logger.info(f"  Distance: {distance_m}m, Walk time: {walk_time_s}s ({walk_time_s/60:.1f} min)")


def main():
    parser = argparse.ArgumentParser(description='Fix Proximidad stop mappings')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()

    logger.info("Starting Proximidad stop fixes...")
    if args.dry_run:
        logger.info("=== DRY RUN MODE ===")

    with SessionLocal() as db:
        try:
            # 1. Migrate María Zambrano
            migrate_maria_zambrano(db, args.dry_run)

            # 2. Create Cartagena correspondence
            create_cartagena_correspondence(db, args.dry_run)

            if not args.dry_run:
                db.commit()
                logger.info("All changes committed successfully")
            else:
                logger.info("Dry run complete - no changes made")

        except Exception as e:
            logger.error(f"Error: {e}")
            db.rollback()
            raise


if __name__ == '__main__':
    main()
