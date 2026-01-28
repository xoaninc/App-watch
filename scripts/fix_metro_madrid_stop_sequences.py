#!/usr/bin/env python3
"""Fix Metro Madrid stop sequences for split lines.

Lines that split into branches (7/7B, 9/9B, 10/10B) are missing the
connection station in the main line's stop sequence. The shapes from
CRTM correctly show the full line, but the stop list is incomplete.

This script adds the missing stations:
- METRO_7: Add "Estadio Metropolitano" (connection with 7B)
- METRO_10: Add "Tres Olivos" (connection with 10B)

Usage:
    python scripts/fix_metro_madrid_stop_sequences.py [--dry-run]
"""

import os
import sys
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Stations to add to main lines (at the beginning, sequence 0)
# Format: (route_id, stop_id, stop_name)
MISSING_STATIONS = [
    ('METRO_7', 'METRO_286', 'Estadio Metropolitano'),
    ('METRO_10', 'METRO_274', 'Tres Olivos'),
]


def reset_sequence(db):
    """Reset the ID sequence to avoid conflicts."""
    max_id = db.execute(text('SELECT MAX(id) FROM gtfs_stop_route_sequence')).scalar()
    if max_id:
        db.execute(text(
            "SELECT setval('gtfs_stop_route_sequence_id_seq', :next_id, false)"
        ), {'next_id': max_id + 1})
        logger.info(f"Reset sequence to {max_id + 1}")


def station_exists_in_route(db, route_id: str, stop_id: str) -> bool:
    """Check if a station is already in a route's sequence."""
    result = db.execute(text('''
        SELECT 1 FROM gtfs_stop_route_sequence
        WHERE route_id = :route_id AND stop_id = :stop_id
    '''), {'route_id': route_id, 'stop_id': stop_id}).fetchone()
    return result is not None


def get_first_stop(db, route_id: str):
    """Get the first stop in a route's sequence."""
    return db.execute(text('''
        SELECT s.name, srs.sequence
        FROM gtfs_stop_route_sequence srs
        JOIN gtfs_stops s ON srs.stop_id = s.id
        WHERE srs.route_id = :route_id
        ORDER BY srs.sequence ASC
        LIMIT 1
    '''), {'route_id': route_id}).fetchone()


def add_station_at_beginning(db, route_id: str, stop_id: str, stop_name: str, dry_run: bool) -> bool:
    """Add a station at the beginning of a route's sequence.

    Returns True if the station was added, False if it already existed.
    """
    # Check if already exists
    if station_exists_in_route(db, route_id, stop_id):
        logger.info(f"  {stop_name} already in {route_id}, skipping")
        return False

    # Get current first stop for logging
    first = get_first_stop(db, route_id)
    if first:
        logger.info(f"  Current first stop: {first[0]} (seq {first[1]})")

    if dry_run:
        logger.info(f"  Would add {stop_name} at sequence 0")
        return True

    # Shift all existing sequences +1
    result = db.execute(text('''
        UPDATE gtfs_stop_route_sequence
        SET sequence = sequence + 1
        WHERE route_id = :route_id
    '''), {'route_id': route_id})
    logger.info(f"  Shifted {result.rowcount} sequences")

    # Insert the new station at sequence 0
    db.execute(text('''
        INSERT INTO gtfs_stop_route_sequence (route_id, stop_id, sequence)
        VALUES (:route_id, :stop_id, 0)
    '''), {'route_id': route_id, 'stop_id': stop_id})
    logger.info(f"  Added {stop_name} at sequence 0")

    return True


def verify_results(db, route_id: str):
    """Print the first few stops of a route for verification."""
    stops = db.execute(text('''
        SELECT srs.sequence, s.name
        FROM gtfs_stop_route_sequence srs
        JOIN gtfs_stops s ON srs.stop_id = s.id
        WHERE srs.route_id = :route_id
        ORDER BY srs.sequence
        LIMIT 5
    '''), {'route_id': route_id}).fetchall()

    count = db.execute(text('''
        SELECT COUNT(*) FROM gtfs_stop_route_sequence
        WHERE route_id = :route_id
    '''), {'route_id': route_id}).scalar()

    logger.info(f"  {route_id} ({count} paradas):")
    for seq, name in stops:
        logger.info(f"    {seq}: {name}")
    if count > 5:
        logger.info(f"    ...")


def main():
    parser = argparse.ArgumentParser(description='Fix Metro Madrid stop sequences')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without saving')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made")

        # Reset sequence to avoid ID conflicts
        if not args.dry_run:
            reset_sequence(db)

        added_count = 0

        for route_id, stop_id, stop_name in MISSING_STATIONS:
            logger.info(f"\nProcessing {route_id}:")

            if add_station_at_beginning(db, route_id, stop_id, stop_name, args.dry_run):
                added_count += 1

        if not args.dry_run:
            db.commit()
            logger.info("\nChanges committed.")

        # Verify results
        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION")
        logger.info("=" * 60)

        for route_id, _, _ in MISSING_STATIONS:
            verify_results(db, route_id)

        logger.info("\n" + "=" * 60)
        logger.info(f"COMPLETE: {added_count} stations added")
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
