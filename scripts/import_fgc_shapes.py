#!/usr/bin/env python3
"""Import FGC shapes from GTFS zip file.

Downloads shapes.txt from FGC GTFS and imports them
into gtfs_shapes and gtfs_shape_points tables.

Source: https://www.fgc.cat/google/google_transit.zip
- 46 unique shapes
- 11,662 shape points

Usage:
    python scripts/import_fgc_shapes.py [--dry-run]
"""

import os
import sys
import csv
import argparse
import logging
import tempfile
import zipfile
from typing import Dict, List
from collections import defaultdict
from io import TextIOWrapper

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FGC GTFS URL
FGC_GTFS_URL = "https://www.fgc.cat/google/google_transit.zip"


def fetch_all_shapes() -> List[Dict]:
    """Download GTFS and extract shapes.txt."""
    logger.info("Downloading FGC GTFS...")

    response = requests.get(FGC_GTFS_URL, timeout=120)
    response.raise_for_status()

    # Save to temp file and extract shapes.txt
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
        f.write(response.content)
        temp_path = f.name

    logger.info(f"Downloaded {len(response.content):,} bytes")

    all_records = []
    try:
        with zipfile.ZipFile(temp_path, 'r') as zf:
            with zf.open('shapes.txt') as shapes_file:
                reader = csv.DictReader(TextIOWrapper(shapes_file, 'utf-8'))
                for row in reader:
                    all_records.append({
                        'shape_id': row.get('shape_id', ''),
                        'shape_pt_lat': float(row.get('shape_pt_lat', 0)),
                        'shape_pt_lon': float(row.get('shape_pt_lon', 0)),
                        'shape_pt_sequence': int(row.get('shape_pt_sequence', 0)),
                    })
    finally:
        os.unlink(temp_path)

    logger.info(f"Total points extracted: {len(all_records)}")
    return all_records


def group_by_shape(records: List[Dict]) -> Dict[str, List[Dict]]:
    """Group records by shape_id."""
    grouped = defaultdict(list)

    for record in records:
        shape_id = str(record.get('shape_id', ''))
        if shape_id:
            grouped[shape_id].append(record)

    # Sort each group by sequence
    for shape_id in grouped:
        grouped[shape_id].sort(key=lambda x: x.get('shape_pt_sequence', 0))

    return grouped


def import_shapes(db, dry_run: bool = False) -> Dict[str, int]:
    """Import FGC shapes into database.

    Args:
        db: Database session
        dry_run: If True, don't make any changes

    Returns:
        Statistics dict
    """
    stats = {
        'shapes_created': 0,
        'points_imported': 0,
        'shapes_skipped': 0,
    }

    # Fetch all shape points
    records = fetch_all_shapes()

    # Group by shape_id
    grouped = group_by_shape(records)
    logger.info(f"Found {len(grouped)} unique shapes")

    for shape_id, points in sorted(grouped.items()):
        if not points:
            stats['shapes_skipped'] += 1
            continue

        num_points = len(points)
        logger.info(f"  Shape {shape_id}: {num_points} points")

        if dry_run:
            stats['shapes_created'] += 1
            stats['points_imported'] += num_points
            continue

        # Delete existing shape points first
        db.execute(
            text('DELETE FROM gtfs_shape_points WHERE shape_id = :shape_id'),
            {'shape_id': shape_id}
        )

        # Insert or update shape record
        db.execute(text('''
            INSERT INTO gtfs_shapes (id)
            VALUES (:shape_id)
            ON CONFLICT (id) DO NOTHING
        '''), {'shape_id': shape_id})

        # Insert shape points
        for point in points:
            lat = point.get('shape_pt_lat')
            lon = point.get('shape_pt_lon')
            seq = point.get('shape_pt_sequence', 0)

            if lat is None or lon is None:
                continue

            db.execute(text('''
                INSERT INTO gtfs_shape_points (shape_id, lat, lon, sequence)
                VALUES (:shape_id, :lat, :lon, :seq)
            '''), {
                'shape_id': shape_id,
                'lat': lat,
                'lon': lon,
                'seq': seq
            })

        stats['shapes_created'] += 1
        stats['points_imported'] += num_points

    if not dry_run:
        db.commit()
        logger.info("Changes committed to database")

    return stats


def verify_import(db) -> None:
    """Verify the import by checking shape counts."""
    shapes = db.execute(text('''
        SELECT COUNT(*) FROM gtfs_shapes WHERE id::text ~ '^[12]000'
    ''')).scalar()

    points = db.execute(text('''
        SELECT COUNT(*) FROM gtfs_shape_points WHERE shape_id::text ~ '^[12]000'
    ''')).scalar()

    # Check which routes now have valid shapes
    routes_with_shapes = db.execute(text('''
        SELECT DISTINCT t.route_id
        FROM gtfs_trips t
        JOIN gtfs_shape_points sp ON t.shape_id::text = sp.shape_id::text
        WHERE t.route_id LIKE 'FGC_%'
    ''')).fetchall()

    logger.info(f"\nVerification:")
    logger.info(f"  FGC shapes in DB: {shapes}")
    logger.info(f"  FGC shape points in DB: {points}")
    logger.info(f"  Routes with valid shapes: {len(routes_with_shapes)}")
    for r in routes_with_shapes:
        logger.info(f"    - {r[0]}")


def main():
    parser = argparse.ArgumentParser(description='Import FGC shapes from Open Data')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without saving')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made")

        stats = import_shapes(db, dry_run=args.dry_run)

        logger.info("=" * 60)
        logger.info("IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Shapes created: {stats['shapes_created']}")
        logger.info(f"Points imported: {stats['points_imported']:,}")
        logger.info(f"Shapes skipped: {stats['shapes_skipped']}")

        if args.dry_run:
            logger.info("[DRY RUN - no changes saved]")
        else:
            verify_import(db)

        logger.info("=" * 60)

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
