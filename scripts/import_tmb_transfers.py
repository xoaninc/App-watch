#!/usr/bin/env python3
"""Import TMB Metro Barcelona transfers from GTFS transfers.txt.

TMB GTFS includes transfers between metro lines with min_transfer_time.

Source: TMB GTFS
https://api.tmb.cat/v1/static/datasets/gtfs.zip

Usage:
    python scripts/import_tmb_transfers.py [--dry-run]
"""

import os
import sys
import argparse
import logging
import tempfile
import zipfile
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# TMB API credentials (from environment)
TMB_APP_ID = os.getenv('TMB_APP_ID')
TMB_APP_KEY = os.getenv('TMB_APP_KEY')

# GTFS URL
GTFS_URL = f"https://api.tmb.cat/v1/static/datasets/gtfs.zip?app_id={TMB_APP_ID}&app_key={TMB_APP_KEY}"


def download_gtfs() -> str:
    """Download TMB GTFS and return path to temp file."""
    logger.info("Downloading TMB GTFS...")

    response = requests.get(GTFS_URL, timeout=120)
    response.raise_for_status()

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    temp_file.write(response.content)
    temp_file.close()

    logger.info(f"  Downloaded {len(response.content) / 1024 / 1024:.1f} MB")
    return temp_file.name


def parse_transfers(gtfs_path: str) -> list:
    """Parse transfers.txt from GTFS.

    Returns:
        List of {from_stop_id, to_stop_id, transfer_type, min_transfer_time}
    """
    transfers = []

    with zipfile.ZipFile(gtfs_path, 'r') as zf:
        with zf.open('transfers.txt') as f:
            reader = csv.DictReader(line.decode('utf-8') for line in f)

            for row in reader:
                transfers.append({
                    'from_stop_id': row['from_stop_id'],
                    'to_stop_id': row['to_stop_id'],
                    'transfer_type': int(row.get('transfer_type', 0)),
                    'min_transfer_time': int(row.get('min_transfer_time', 0)),
                })

    return transfers


def import_transfers(db, transfers: list, dry_run: bool = False) -> int:
    """Import transfers into stop_correspondence."""
    logger.info("Importing transfers...")

    if not dry_run:
        # Clear existing TMB transfers from GTFS
        result = db.execute(text("""
            DELETE FROM stop_correspondence
            WHERE (from_stop_id LIKE 'TMB_METRO_%' OR to_stop_id LIKE 'TMB_METRO_%')
            AND source = 'gtfs'
        """))
        logger.info(f"  Cleared {result.rowcount} existing GTFS transfers")

    count = 0
    skipped = 0

    for t in transfers:
        # Add TMB_METRO_ prefix to stop IDs
        from_id = f"TMB_METRO_{t['from_stop_id']}"
        to_id = f"TMB_METRO_{t['to_stop_id']}"

        # Verify stops exist
        from_exists = db.execute(text(
            "SELECT 1 FROM gtfs_stops WHERE id = :id"
        ), {'id': from_id}).fetchone()

        to_exists = db.execute(text(
            "SELECT 1 FROM gtfs_stops WHERE id = :id"
        ), {'id': to_id}).fetchone()

        if not from_exists or not to_exists:
            skipped += 1
            logger.warning(f"  Skipping {from_id} -> {to_id} (stops not found)")
            continue

        # Calculate distance (estimate ~50m per 30 seconds walk time)
        walk_time = t['min_transfer_time']
        distance_m = int(walk_time * 1.25)  # ~4.5 km/h walking speed

        if not dry_run:
            db.execute(text("""
                INSERT INTO stop_correspondence
                (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
                VALUES (:from_id, :to_id, :distance, :walk_time, 'gtfs')
                ON CONFLICT DO NOTHING
            """), {
                'from_id': from_id,
                'to_id': to_id,
                'distance': distance_m,
                'walk_time': walk_time,
            })

        count += 1

    if not dry_run:
        db.commit()

    logger.info(f"  Imported {count} transfers, skipped {skipped}")
    return count


def main():
    parser = argparse.ArgumentParser(description='Import TMB Metro transfers from GTFS')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()

    if not TMB_APP_ID or not TMB_APP_KEY:
        logger.error("TMB_APP_ID and TMB_APP_KEY environment variables must be set")
        sys.exit(1)

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made\n")

        # Download GTFS
        gtfs_path = download_gtfs()

        # Parse transfers
        logger.info("Parsing transfers.txt...")
        transfers = parse_transfers(gtfs_path)
        logger.info(f"  Found {len(transfers)} transfers in GTFS")

        # Import
        count = import_transfers(db, transfers, args.dry_run)

        # Cleanup
        os.unlink(gtfs_path)

        logger.info("\n" + "=" * 60)
        logger.info("IMPORT COMPLETE - TMB Metro Transfers")
        logger.info("=" * 60)
        logger.info(f"Transfers in GTFS: {len(transfers)}")
        logger.info(f"Transfers imported: {count}")
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
