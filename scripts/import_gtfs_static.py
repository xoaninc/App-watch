#!/usr/bin/env python3
"""Import GTFS static data (calendar, trips, stop_times) from fomento_transit.zip.

This script imports the schedule data needed for the /departures endpoint.

Usage:
    # Import all núcleos
    python scripts/import_gtfs_static.py /path/to/fomento_transit.zip

    # Import specific núcleo by ID
    python scripts/import_gtfs_static.py /path/to/fomento_transit.zip --nucleo 10

    # Import specific núcleo by name
    python scripts/import_gtfs_static.py /path/to/fomento_transit.zip --nucleo madrid

    # List available núcleos in the GTFS file
    python scripts/import_gtfs_static.py /path/to/fomento_transit.zip --list-nucleos
"""

import sys
import os
import csv
import zipfile
import logging
import argparse
from datetime import datetime
from io import TextIOWrapper
from typing import Optional
from sqlalchemy import text
from core.database import SessionLocal, engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Núcleo ID to name mapping
NUCLEO_NAMES = {
    10: 'Madrid',
    20: 'Asturias',
    30: 'Santander',
    31: 'Bilbao',
    32: 'San Sebastián',
    40: 'Zaragoza',
    50: 'Barcelona (Rodalies)',
    60: 'Valencia',
    61: 'Murcia/Alicante',
    62: 'Castellón',
    70: 'Sevilla',
    71: 'Cádiz',
    72: 'Málaga',
}

# Nucleo ID mapping: GTFS -> our database
NUCLEO_MAPPING = {
    51: 50,  # Rodalies de Catalunya
    90: 10,  # Madrid C9 special trains
}

BATCH_SIZE = 10000


def time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS to seconds since midnight."""
    parts = time_str.strip().split(':')
    if len(parts) != 3:
        return 0
    hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def parse_date(date_str: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD."""
    date_str = date_str.strip()
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


def parse_nucleo_arg(nucleo_arg: str) -> Optional[int]:
    """Parse --nucleo argument (ID or name) and return núcleo ID."""
    if nucleo_arg is None:
        return None

    # Try as integer ID
    try:
        nucleo_id = int(nucleo_arg)
        if nucleo_id in NUCLEO_NAMES:
            return nucleo_id
        logger.error(f"Unknown núcleo ID: {nucleo_id}")
        logger.info(f"Valid IDs: {list(NUCLEO_NAMES.keys())}")
        return None
    except ValueError:
        pass

    # Try as name (case-insensitive)
    nucleo_lower = nucleo_arg.lower()
    for nid, name in NUCLEO_NAMES.items():
        if nucleo_lower in name.lower():
            return nid

    logger.error(f"Unknown núcleo name: {nucleo_arg}")
    logger.info(f"Valid names: {list(NUCLEO_NAMES.values())}")
    return None


def list_nucleos(zf: zipfile.ZipFile) -> dict:
    """List núcleos found in GTFS file with route counts."""
    nucleos = {}

    with zf.open('routes.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]

        for row in reader:
            gtfs_route_id = row['route_id'].strip()

            # Extract nucleo_id from GTFS route_id (first 2 digits)
            if len(gtfs_route_id) >= 2 and gtfs_route_id[:2].isdigit():
                gtfs_nucleo_id = int(gtfs_route_id[:2])
                our_nucleo_id = NUCLEO_MAPPING.get(gtfs_nucleo_id, gtfs_nucleo_id)

                if our_nucleo_id not in nucleos:
                    nucleos[our_nucleo_id] = {
                        'name': NUCLEO_NAMES.get(our_nucleo_id, f'Unknown ({our_nucleo_id})'),
                        'route_count': 0,
                        'routes': []
                    }
                nucleos[our_nucleo_id]['route_count'] += 1
                short_name = row.get('route_short_name', '').strip()
                if short_name and short_name not in nucleos[our_nucleo_id]['routes']:
                    nucleos[our_nucleo_id]['routes'].append(short_name)

    return nucleos


def print_nucleos(nucleos: dict):
    """Print núcleos in a formatted table."""
    print("\n" + "=" * 60)
    print("NÚCLEOS IN GTFS FILE")
    print("=" * 60)
    print(f"{'ID':<5} {'Name':<25} {'Routes':<8} {'Lines'}")
    print("-" * 60)

    for nid in sorted(nucleos.keys()):
        info = nucleos[nid]
        routes_str = ', '.join(sorted(info['routes'])[:10])
        if len(info['routes']) > 10:
            routes_str += f"... (+{len(info['routes']) - 10} more)"
        print(f"{nid:<5} {info['name']:<25} {info['route_count']:<8} {routes_str}")

    print("=" * 60)
    print(f"Total: {len(nucleos)} núcleos")
    print("\nUse --nucleo <ID> or --nucleo <name> to import a specific núcleo")


def import_calendar(db, zf: zipfile.ZipFile) -> int:
    """Import calendar.txt data."""
    logger.info("Importing calendar data...")

    with zf.open('calendar.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        # Strip whitespace from field names (fixed-width format)
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        rows = []

        for row in reader:
            rows.append({
                'service_id': row['service_id'].strip(),
                'monday': row['monday'].strip() == '1',
                'tuesday': row['tuesday'].strip() == '1',
                'wednesday': row['wednesday'].strip() == '1',
                'thursday': row['thursday'].strip() == '1',
                'friday': row['friday'].strip() == '1',
                'saturday': row['saturday'].strip() == '1',
                'sunday': row['sunday'].strip() == '1',
                'start_date': parse_date(row['start_date']),
                'end_date': parse_date(row['end_date']),
            })

        if rows:
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i+BATCH_SIZE]
                db.execute(
                    text("""
                        INSERT INTO gtfs_calendar
                        (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                        VALUES (:service_id, :monday, :tuesday, :wednesday, :thursday, :friday, :saturday, :sunday, :start_date, :end_date)
                        ON CONFLICT (service_id) DO UPDATE SET
                            monday = EXCLUDED.monday,
                            tuesday = EXCLUDED.tuesday,
                            wednesday = EXCLUDED.wednesday,
                            thursday = EXCLUDED.thursday,
                            friday = EXCLUDED.friday,
                            saturday = EXCLUDED.saturday,
                            sunday = EXCLUDED.sunday,
                            start_date = EXCLUDED.start_date,
                            end_date = EXCLUDED.end_date
                    """),
                    batch
                )
            db.commit()

    return len(rows)


def build_route_mapping(db, zf: zipfile.ZipFile, nucleo_filter: Optional[int] = None) -> dict:
    """Build mapping from GTFS route_id to our route_id.

    GTFS route_id format: {nucleo_id}T{seq}{short_name} (e.g., 10T0001C1)
    Our route_id format: RENFE_{short_name}_{renfe_idlinea} (e.g., RENFE_C1_34)

    Maps via nucleo_id + short_name.

    Note: GTFS uses different nucleo codes in some cases:
    - 51 in GTFS = 50 in our DB (Rodalies de Catalunya)
    - 90 in GTFS = 10 in our DB (Madrid C9 special)

    Args:
        db: Database session
        zf: Opened GTFS zip file
        nucleo_filter: If set, only map routes for this núcleo ID
    """
    if nucleo_filter:
        logger.info(f"Building route mapping for núcleo {nucleo_filter} ({NUCLEO_NAMES.get(nucleo_filter, 'Unknown')})...")
    else:
        logger.info("Building route mapping for all núcleos...")

    # Get our routes with nucleo_id and short_name
    our_routes = db.execute(text(
        "SELECT id, nucleo_id, short_name FROM gtfs_routes WHERE nucleo_id IS NOT NULL"
    )).fetchall()

    # Build lookup: (nucleo_id, short_name_lower) -> our_route_id
    route_lookup = {}
    for route in our_routes:
        key = (route[1], route[2].strip().lower())  # nucleo_id, short_name (lowercase)
        route_lookup[key] = route[0]

    logger.info(f"Built lookup with {len(route_lookup)} route mappings")

    # Parse GTFS routes and build mapping
    gtfs_to_our = {}
    skipped_by_filter = 0

    with zf.open('routes.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        for row in reader:
            gtfs_route_id = row['route_id'].strip()
            short_name = row['route_short_name'].strip()

            # Extract nucleo_id from GTFS route_id (first 2 digits)
            if len(gtfs_route_id) >= 2 and gtfs_route_id[:2].isdigit():
                gtfs_nucleo_id = int(gtfs_route_id[:2])
                # Map to our nucleo_id if different
                our_nucleo_id = NUCLEO_MAPPING.get(gtfs_nucleo_id, gtfs_nucleo_id)

                # Filter by nucleo if specified
                if nucleo_filter and our_nucleo_id != nucleo_filter:
                    skipped_by_filter += 1
                    continue

                key = (our_nucleo_id, short_name.lower())

                if key in route_lookup:
                    gtfs_to_our[gtfs_route_id] = route_lookup[key]

    if nucleo_filter:
        logger.info(f"Skipped {skipped_by_filter} routes from other núcleos")
    logger.info(f"Mapped {len(gtfs_to_our)} GTFS routes to our routes")
    return gtfs_to_our


def import_trips(db, zf: zipfile.ZipFile, route_mapping: dict) -> int:
    """Import trips.txt data, mapping GTFS routes to our routes."""
    logger.info("Importing trips data...")

    with zf.open('trips.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        rows = []
        skipped = 0

        for row in reader:
            gtfs_route_id = row['route_id'].strip()

            # Map to our route_id
            our_route_id = route_mapping.get(gtfs_route_id)
            if not our_route_id:
                skipped += 1
                continue

            rows.append({
                'id': row['trip_id'].strip(),
                'route_id': our_route_id,
                'service_id': row['service_id'].strip(),
                'headsign': row.get('trip_headsign', '').strip() or None,
                'short_name': None,
                'direction_id': None,
                'block_id': row.get('block_id', '').strip() or None,
                'shape_id': row.get('shape_id', '').strip() or None,
                'wheelchair_accessible': int(row.get('wheelchair_accessible', 0) or 0),
                'bikes_allowed': None,
            })

        logger.info(f"Skipped {skipped} trips (routes not mapped)")

        if rows:
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i+BATCH_SIZE]
                db.execute(
                    text("""
                        INSERT INTO gtfs_trips
                        (id, route_id, service_id, headsign, short_name, direction_id, block_id, shape_id, wheelchair_accessible, bikes_allowed)
                        VALUES (:id, :route_id, :service_id, :headsign, :short_name, :direction_id, :block_id, :shape_id, :wheelchair_accessible, :bikes_allowed)
                        ON CONFLICT (id) DO UPDATE SET
                            route_id = EXCLUDED.route_id,
                            service_id = EXCLUDED.service_id,
                            headsign = EXCLUDED.headsign,
                            shape_id = EXCLUDED.shape_id
                    """),
                    batch
                )
                if (i + BATCH_SIZE) % 50000 == 0:
                    logger.info(f"  Imported {i + BATCH_SIZE} trips...")
                    db.commit()

            db.commit()

    return len(rows)


def import_stop_times(db, zf: zipfile.ZipFile) -> int:
    """Import stop_times.txt data."""
    logger.info("Importing stop_times data (this may take a while)...")

    # Get existing trip_ids and stop_ids
    existing_trips = set(row[0] for row in db.execute(text("SELECT id FROM gtfs_trips")).fetchall())
    logger.info(f"Found {len(existing_trips)} trips in database")

    # Build stop mapping: GTFS stop_id -> our stop_id
    # Our format: RENFE_{number}, GTFS format: {number}
    stop_mapping = {}
    our_stops = db.execute(text("SELECT id FROM gtfs_stops")).fetchall()
    for stop in our_stops:
        our_id = stop[0]
        if our_id.startswith('RENFE_'):
            gtfs_id = our_id.replace('RENFE_', '')
            stop_mapping[gtfs_id] = our_id
    logger.info(f"Built stop mapping with {len(stop_mapping)} stops")

    with zf.open('stop_times.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        rows = []
        total_imported = 0
        skipped_trip = 0
        skipped_stop = 0

        for row in reader:
            trip_id = row['trip_id'].strip()
            gtfs_stop_id = row['stop_id'].strip()

            # Skip if trip doesn't exist
            if trip_id not in existing_trips:
                skipped_trip += 1
                continue

            # Map stop_id
            our_stop_id = stop_mapping.get(gtfs_stop_id)
            if not our_stop_id:
                skipped_stop += 1
                continue

            arrival_time = row['arrival_time'].strip()
            departure_time = row['departure_time'].strip()

            rows.append({
                'trip_id': trip_id,
                'stop_sequence': int(row['stop_sequence'].strip()),
                'stop_id': our_stop_id,
                'arrival_time': arrival_time,
                'departure_time': departure_time,
                'arrival_seconds': time_to_seconds(arrival_time),
                'departure_seconds': time_to_seconds(departure_time),
                'stop_headsign': None,
                'pickup_type': 0,
                'drop_off_type': 0,
                'shape_dist_traveled': None,
                'timepoint': 1,
            })

            if len(rows) >= BATCH_SIZE:
                db.execute(
                    text("""
                        INSERT INTO gtfs_stop_times
                        (trip_id, stop_sequence, stop_id, arrival_time, departure_time,
                         arrival_seconds, departure_seconds, stop_headsign, pickup_type,
                         drop_off_type, shape_dist_traveled, timepoint)
                        VALUES (:trip_id, :stop_sequence, :stop_id, :arrival_time, :departure_time,
                                :arrival_seconds, :departure_seconds, :stop_headsign, :pickup_type,
                                :drop_off_type, :shape_dist_traveled, :timepoint)
                    """),
                    rows
                )
                total_imported += len(rows)
                rows = []

                if total_imported % 100000 == 0:
                    logger.info(f"  Imported {total_imported:,} stop_times...")
                    db.commit()

        # Insert remaining rows
        if rows:
            db.execute(
                text("""
                    INSERT INTO gtfs_stop_times
                    (trip_id, stop_sequence, stop_id, arrival_time, departure_time,
                     arrival_seconds, departure_seconds, stop_headsign, pickup_type,
                     drop_off_type, shape_dist_traveled, timepoint)
                    VALUES (:trip_id, :stop_sequence, :stop_id, :arrival_time, :departure_time,
                            :arrival_seconds, :departure_seconds, :stop_headsign, :pickup_type,
                            :drop_off_type, :shape_dist_traveled, :timepoint)
                """),
                rows
            )
            total_imported += len(rows)

        db.commit()

        logger.info(f"Skipped {skipped_trip} stop_times (trip not found)")
        logger.info(f"Skipped {skipped_stop} stop_times (stop not found)")

    return total_imported


def clear_nucleo_data(db, nucleo_id: int):
    """Clear trips and stop_times for a specific núcleo."""
    nucleo_name = NUCLEO_NAMES.get(nucleo_id, 'Unknown')
    logger.info(f"Clearing existing data for núcleo {nucleo_id} ({nucleo_name})...")

    # Get route IDs for this nucleo
    result = db.execute(text(
        "SELECT id FROM gtfs_routes WHERE nucleo_id = :nid"
    ), {'nid': nucleo_id}).fetchall()
    route_ids = [r[0] for r in result]

    if not route_ids:
        logger.warning(f"No routes found for núcleo {nucleo_id}")
        return

    logger.info(f"  Found {len(route_ids)} routes for núcleo {nucleo_id}")

    # Delete stop_times for trips on these routes
    delete_result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id IN (
            SELECT id FROM gtfs_trips WHERE route_id = ANY(:rids)
        )
    """), {'rids': route_ids})
    db.commit()
    logger.info(f"  Cleared {delete_result.rowcount} stop_times")

    # Delete trips for these routes
    delete_result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id = ANY(:rids)"
    ), {'rids': route_ids})
    db.commit()
    logger.info(f"  Cleared {delete_result.rowcount} trips")


def clear_all_data(db):
    """Clear all trips, stop_times, and calendar data."""
    logger.info("Clearing all existing schedule data...")
    db.execute(text("DELETE FROM gtfs_stop_times"))
    db.commit()
    logger.info("  Cleared stop_times")
    db.execute(text("DELETE FROM gtfs_trips"))
    db.commit()
    logger.info("  Cleared trips")
    db.execute(text("DELETE FROM gtfs_calendar"))
    db.commit()
    logger.info("  Cleared calendar")


def main():
    parser = argparse.ArgumentParser(
        description='Import GTFS static data (calendar, trips, stop_times) from fomento_transit.zip'
    )
    parser.add_argument('zip_path', help='Path to GTFS zip file')
    parser.add_argument(
        '--nucleo',
        help='Import only this núcleo (ID or name). Examples: 10, madrid, sevilla'
    )
    parser.add_argument(
        '--list-nucleos',
        action='store_true',
        help='List núcleos available in the GTFS file and exit'
    )

    args = parser.parse_args()

    if not os.path.exists(args.zip_path):
        logger.error(f"File not found: {args.zip_path}")
        sys.exit(1)

    # Handle --list-nucleos
    if args.list_nucleos:
        with zipfile.ZipFile(args.zip_path, 'r') as zf:
            nucleos = list_nucleos(zf)
            print_nucleos(nucleos)
        sys.exit(0)

    # Parse nucleo filter
    nucleo_filter = None
    if args.nucleo:
        nucleo_filter = parse_nucleo_arg(args.nucleo)
        if nucleo_filter is None:
            sys.exit(1)

    db = SessionLocal()

    try:
        logger.info(f"Opening {args.zip_path}...")

        with zipfile.ZipFile(args.zip_path, 'r') as zf:
            start_time = datetime.now()

            # Build route mapping (filtered if nucleo specified)
            route_mapping = build_route_mapping(db, zf, nucleo_filter)

            if not route_mapping:
                logger.error("No routes mapped - check if routes exist in database")
                sys.exit(1)

            # Clear existing data
            if nucleo_filter:
                # Only clear data for specific nucleo
                clear_nucleo_data(db, nucleo_filter)
            else:
                # Clear all data
                clear_all_data(db)

            # Import calendar (only for full import, not per-nucleo)
            calendar_count = 0
            if not nucleo_filter:
                calendar_count = import_calendar(db, zf)
                logger.info(f"Imported {calendar_count} calendar entries")
            else:
                logger.info("Skipping calendar import (nucleo-specific import)")

            trips_count = import_trips(db, zf, route_mapping)
            logger.info(f"Imported {trips_count:,} trips")

            stop_times_count = import_stop_times(db, zf)
            logger.info(f"Imported {stop_times_count:,} stop_times")

            elapsed = datetime.now() - start_time

            logger.info("\n" + "="*60)
            logger.info("Import Summary")
            logger.info("="*60)
            if nucleo_filter:
                logger.info(f"Núcleo: {nucleo_filter} ({NUCLEO_NAMES.get(nucleo_filter, 'Unknown')})")
            else:
                logger.info("Scope: All núcleos")
                logger.info(f"Calendar entries: {calendar_count:,}")
            logger.info(f"Trips: {trips_count:,}")
            logger.info(f"Stop times: {stop_times_count:,}")
            logger.info(f"Elapsed time: {elapsed}")
            logger.info("="*60)

        logger.info("\nGTFS static import completed successfully!")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Import failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
