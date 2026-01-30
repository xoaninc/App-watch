#!/usr/bin/env python3
"""Import TMB Metro Barcelona accesses from GTFS.

TMB includes entrance/exit data in their GTFS stops.txt file:
- location_type=2: Entrances/Exits
- Prefix E.10xxxxx: Elevators (ascensors)
- Prefix E.xxxxx: Regular entrances
- wheelchair_boarding: 1=accessible, 2=not accessible

Source: TMB GTFS
https://api.tmb.cat/v1/static/datasets/gtfs.zip

Usage:
    python scripts/import_tmb_accesses.py [--dry-run]
"""

import os
import sys
import argparse
import logging
import tempfile
import zipfile
from typing import Dict, List, Optional, Tuple
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

    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    temp_file.write(response.content)
    temp_file.close()

    logger.info(f"  Downloaded {len(response.content) / 1024 / 1024:.1f} MB")
    return temp_file.name


def parse_stops(gtfs_path: str) -> Tuple[Dict, Dict, Dict]:
    """Parse stops.txt from GTFS.

    Returns:
        Tuple of (entrances, stations, platforms)
        - entrances: {stop_id: {name, lat, lon, parent_station, wheelchair, is_elevator}}
        - stations: {stop_id: {name, lat, lon}}
        - platforms: {stop_id: {name, lat, lon, parent_station}}
    """
    entrances = {}
    stations = {}
    platforms = {}

    with zipfile.ZipFile(gtfs_path, 'r') as zf:
        with zf.open('stops.txt') as f:
            reader = csv.DictReader(line.decode('utf-8') for line in f)

            for row in reader:
                stop_id = row['stop_id']
                location_type = int(row.get('location_type', 0))

                data = {
                    'name': row['stop_name'],
                    'lat': float(row['stop_lat']),
                    'lon': float(row['stop_lon']),
                    'parent_station': row.get('parent_station', ''),
                    'wheelchair': row.get('wheelchair_boarding', ''),
                }

                if location_type == 2:  # Entrance/Exit
                    # Check if it's an elevator
                    is_elevator = 'ascensor' in row['stop_name'].lower() or stop_id.startswith('E.10')
                    data['is_elevator'] = is_elevator

                    # Parse wheelchair accessibility
                    wb = row.get('wheelchair_boarding', '')
                    if wb == '1':
                        data['wheelchair'] = True
                    elif wb == '2':
                        data['wheelchair'] = False
                    else:
                        data['wheelchair'] = None

                    entrances[stop_id] = data

                elif location_type == 1:  # Station
                    stations[stop_id] = data

                elif location_type == 0:  # Platform/Stop
                    platforms[stop_id] = data

    return entrances, stations, platforms


def parse_pathways(gtfs_path: str) -> Dict[str, List[Dict]]:
    """Parse pathways.txt from GTFS.

    Returns:
        Dict of {from_stop_id: [{to_stop_id, traversal_time, description}, ...]}
    """
    pathways = {}

    with zipfile.ZipFile(gtfs_path, 'r') as zf:
        with zf.open('pathways.txt') as f:
            reader = csv.DictReader(line.decode('utf-8') for line in f)

            for row in reader:
                from_id = row['from_stop_id']
                to_id = row['to_stop_id']

                pathway_data = {
                    'to_stop_id': to_id,
                    'traversal_time': int(row.get('traversal_time', 60)),
                    'description': row.get('signposted_as', ''),
                }

                if from_id not in pathways:
                    pathways[from_id] = []
                pathways[from_id].append(pathway_data)

    return pathways


def map_to_platform(db, parent_station_id: str, stations: Dict) -> Optional[str]:
    """Map TMB parent_station to a platform stop_id.

    TMB structure:
    - Entrance (location_type=2): E.xxxxx -> parent_station P.6660XXX
    - Station (location_type=1): P.6660XXX
    - Platform (location_type=0): 1.XXX (usually no parent_station!)

    Most platforms have parent_station_id = None, so we match by name.
    """
    if not parent_station_id:
        return None

    # Get station name from GTFS data
    station_data = stations.get(parent_station_id)
    if not station_data:
        return None

    station_name = station_data['name']

    # Find a metro platform (location_type=0, id like TMB_METRO_1.xxx) with matching name
    # TMB_METRO_1.xxx are metro platforms, TMB_METRO_2.xxx are bus stops
    result = db.execute(text("""
        SELECT id FROM gtfs_stops
        WHERE id LIKE 'TMB_METRO_1.%'
        AND location_type = 0
        AND LOWER(name) = LOWER(:name)
        LIMIT 1
    """), {
        'name': station_name
    }).fetchone()

    if result:
        return result[0]

    return None


def import_accesses(db, entrances: Dict, stations: Dict, dry_run: bool = False) -> int:
    """Import entrances as stop_access records."""
    logger.info("Importing accesses...")

    if not dry_run:
        # Clear existing TMB accesses
        result = db.execute(text("DELETE FROM stop_access WHERE stop_id LIKE 'TMB_METRO_%' AND source = 'gtfs'"))
        logger.info(f"  Cleared {result.rowcount} existing accesses")

    count = 0
    mapped = 0
    unmapped = 0

    for entrance_id, data in entrances.items():
        parent_station = data['parent_station']

        # Map entrance to a platform via parent station name
        our_stop_id = map_to_platform(db, parent_station, stations)

        if not our_stop_id:
            unmapped += 1
            continue

        mapped += 1

        # Determine access type from name
        access_type = 'elevator' if data.get('is_elevator') else 'entrance'

        if not dry_run:
            db.execute(text("""
                INSERT INTO stop_access
                (stop_id, name, lat, lon, wheelchair, source)
                VALUES (:stop_id, :name, :lat, :lon, :wheelchair, 'gtfs')
            """), {
                'stop_id': our_stop_id,
                'name': data['name'],
                'lat': data['lat'],
                'lon': data['lon'],
                'wheelchair': data.get('wheelchair'),
            })

        count += 1

    if not dry_run:
        db.commit()

    logger.info(f"  Imported {count} accesses ({mapped} mapped, {unmapped} unmapped)")
    return count


def verify_mapping(db):
    """Verify mapping between TMB GTFS and our stops."""
    logger.info("\nVerifying stop mapping...")

    # Count our TMB stops
    our_count = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_stops WHERE id LIKE 'TMB_METRO_%'"
    )).scalar()

    # Count accesses imported
    access_count = db.execute(text(
        "SELECT COUNT(*) FROM stop_access WHERE stop_id LIKE 'TMB_METRO_%'"
    )).scalar()

    # Count stops with accesses
    stops_with_access = db.execute(text("""
        SELECT COUNT(DISTINCT stop_id) FROM stop_access WHERE stop_id LIKE 'TMB_METRO_%'
    """)).scalar()

    print("\n" + "=" * 60)
    print("TMB MAPPING VERIFICATION")
    print("=" * 60)
    print(f"Our TMB Metro stops: {our_count}")
    print(f"Accesses imported: {access_count}")
    print(f"Stops with accesses: {stops_with_access}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Import TMB Metro Barcelona accesses from GTFS')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without saving')
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

        # Parse data
        logger.info("Parsing GTFS data...")
        entrances, stations, platforms = parse_stops(gtfs_path)
        pathways = parse_pathways(gtfs_path)

        logger.info(f"  Found {len(entrances)} entrances")
        logger.info(f"  Found {len(stations)} stations")
        logger.info(f"  Found {len(platforms)} platforms")
        logger.info(f"  Found {len(pathways)} pathway connections")

        # Count elevators
        elevators = sum(1 for e in entrances.values() if e.get('is_elevator'))
        logger.info(f"  Elevators: {elevators}")

        # Import accesses
        access_count = import_accesses(db, entrances, stations, args.dry_run)

        # Verify
        if not args.dry_run:
            verify_mapping(db)

        # Cleanup
        os.unlink(gtfs_path)

        logger.info("\n" + "=" * 60)
        logger.info("IMPORT COMPLETE - TMB Metro Barcelona")
        logger.info("=" * 60)
        logger.info(f"Entrances in GTFS: {len(entrances)}")
        logger.info(f"Elevators: {elevators}")
        logger.info(f"Accesses imported: {access_count}")
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
