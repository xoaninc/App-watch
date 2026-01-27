#!/usr/bin/env python3
"""Import GTFS data for Metro de Sevilla.

Metro Sevilla GTFS uses a hierarchical stop structure:
- Stations: L1-E1, L1-E2, ... (location_type=1)
- Platforms: L1-1, L1-2, ... (location_type=0)

The stop_times.txt references PLATFORMS (L1-1, L1-2, etc.) not stations.
Our database has STATIONS with IDs like METRO_SEV_L1_E1.

This script maps:
    GTFS platform L1-N -> our station METRO_SEV_L1_EN

Usage:
    python scripts/import_metro_sevilla_gtfs.py /path/to/google_transit.zip

GTFS Source: https://metro-sevilla.es/google-transit/google_transit.zip
"""

import sys
import os
import csv
import zipfile
import logging
import argparse
from datetime import datetime
from io import TextIOWrapper
from typing import Optional, Dict
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BATCH_SIZE = 5000

# Metro Sevilla configuration
# Route ID in database is METRO_SEV_L1_CE_OQ (not METRO_SEV_L1)
METRO_SEV_ROUTE_ID = 'METRO_SEV_L1_CE_OQ'
METRO_SEV_NETWORK_ID = 'METRO_SEV'


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


def map_metro_sev_stop_id(gtfs_stop_id: str) -> Optional[str]:
    """Map Metro Sevilla GTFS stop_id to our stop_id.

    GTFS structure:
    - Platforms: L1-1, L1-2, ..., L1-21 (used in stop_times)
    - Stations: L1-E1, L1-E2, ..., L1-E21 (parent stations)

    Our structure:
    - METRO_SEV_L1_E1, METRO_SEV_L1_E2, ..., METRO_SEV_L1_E21

    Mapping: L1-N -> METRO_SEV_L1_EN
    """
    if not gtfs_stop_id:
        return None

    # Parse L1-N format
    if gtfs_stop_id.startswith('L1-') and not gtfs_stop_id.startswith('L1-E'):
        try:
            num = int(gtfs_stop_id.split('-')[1])
            return f"METRO_SEV_L1_E{num}"
        except (ValueError, IndexError):
            return None

    # Also handle L1-EN format (station IDs in GTFS)
    if gtfs_stop_id.startswith('L1-E'):
        try:
            num = int(gtfs_stop_id.split('-E')[1])
            return f"METRO_SEV_L1_E{num}"
        except (ValueError, IndexError):
            return None

    return None


def verify_our_stops(db) -> Dict[str, str]:
    """Verify our Metro Sevilla stops exist and return mapping."""
    result = db.execute(text(
        "SELECT id, name FROM gtfs_stops WHERE id LIKE 'METRO_SEV_%'"
    )).fetchall()

    stops = {row[0]: row[1] for row in result}
    logger.info(f"Found {len(stops)} METRO_SEV stops in database")

    if not stops:
        logger.error("No METRO_SEV stops found! Import stops first.")
        return {}

    return stops


def verify_route_exists(db) -> bool:
    """Verify Metro Sevilla route exists in database."""
    result = db.execute(text(
        "SELECT id, short_name FROM gtfs_routes WHERE id = :rid"
    ), {'rid': METRO_SEV_ROUTE_ID}).fetchone()

    if not result:
        logger.error(f"Route {METRO_SEV_ROUTE_ID} not found in database!")
        return False

    logger.info(f"Found route: {result[0]} ({result[1]})")
    return True


def clear_metro_sev_data(db):
    """Clear existing Metro Sevilla trips and stop_times."""
    logger.info("Clearing existing Metro Sevilla schedule data...")

    # Delete stop_times for Metro Sevilla trips
    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id IN (
            SELECT id FROM gtfs_trips WHERE route_id = :rid
        )
    """), {'rid': METRO_SEV_ROUTE_ID})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id = :rid"
    ), {'rid': METRO_SEV_ROUTE_ID})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} trips")


def import_calendar(db, zf: zipfile.ZipFile) -> int:
    """Import calendar.txt data for Metro Sevilla."""
    logger.info("Importing calendar data...")

    with zf.open('calendar.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        rows = []

        for row in reader:
            service_id = row['service_id'].strip()

            # Prefix service_id to avoid conflicts with other operators
            our_service_id = f"METRO_SEV_{service_id}"

            rows.append({
                'service_id': our_service_id,
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
                rows
            )
            db.commit()

    return len(rows)


def import_calendar_dates(db, zf: zipfile.ZipFile) -> int:
    """Import calendar_dates.txt data (service exceptions)."""
    logger.info("Importing calendar_dates data...")

    if 'calendar_dates.txt' not in zf.namelist():
        logger.info("No calendar_dates.txt found - skipping")
        return 0

    with zf.open('calendar_dates.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        rows = []

        for row in reader:
            service_id = row['service_id'].strip()
            our_service_id = f"METRO_SEV_{service_id}"

            rows.append({
                'service_id': our_service_id,
                'date': parse_date(row['date']),
                'exception_type': int(row['exception_type'].strip()),
            })

        if rows:
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i+BATCH_SIZE]
                db.execute(
                    text("""
                        INSERT INTO gtfs_calendar_dates
                        (service_id, date, exception_type)
                        VALUES (:service_id, :date, :exception_type)
                        ON CONFLICT (service_id, date) DO UPDATE SET
                            exception_type = EXCLUDED.exception_type
                    """),
                    batch
                )
            db.commit()

    return len(rows)


def import_trips(db, zf: zipfile.ZipFile) -> int:
    """Import trips.txt data for Metro Sevilla."""
    logger.info("Importing trips data...")

    with zf.open('trips.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        rows = []

        for row in reader:
            trip_id = row['trip_id'].strip()
            service_id = row['service_id'].strip()

            # Prefix IDs to avoid conflicts
            our_trip_id = f"METRO_SEV_{trip_id}"
            our_service_id = f"METRO_SEV_{service_id}"

            direction_id = row.get('direction_id', '').strip()

            rows.append({
                'id': our_trip_id,
                'route_id': METRO_SEV_ROUTE_ID,
                'service_id': our_service_id,
                'headsign': row.get('trip_headsign', '').strip() or None,
                'short_name': None,
                'direction_id': int(direction_id) if direction_id else None,
                'block_id': None,
                'shape_id': row.get('shape_id', '').strip() or None,
                'wheelchair_accessible': 1,  # Metro is accessible
                'bikes_allowed': None,
            })

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
                            direction_id = EXCLUDED.direction_id
                    """),
                    batch
                )
            db.commit()

    return len(rows)


def import_stop_times(db, zf: zipfile.ZipFile, our_stops: Dict[str, str]) -> int:
    """Import stop_times.txt data with platform-to-station mapping."""
    logger.info("Importing stop_times data...")

    # Get existing trip_ids
    existing_trips = set(row[0] for row in db.execute(text(
        "SELECT id FROM gtfs_trips WHERE route_id = :rid"
    ), {'rid': METRO_SEV_ROUTE_ID}).fetchall())

    logger.info(f"Found {len(existing_trips)} Metro Sevilla trips in database")

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

            # Prefix trip_id
            our_trip_id = f"METRO_SEV_{trip_id}"

            # Skip if trip doesn't exist
            if our_trip_id not in existing_trips:
                skipped_trip += 1
                continue

            # Map GTFS platform ID to our station ID
            our_stop_id = map_metro_sev_stop_id(gtfs_stop_id)
            if not our_stop_id or our_stop_id not in our_stops:
                logger.debug(f"Unknown stop: {gtfs_stop_id} -> {our_stop_id}")
                skipped_stop += 1
                continue

            arrival_time = row['arrival_time'].strip()
            departure_time = row['departure_time'].strip()

            rows.append({
                'trip_id': our_trip_id,
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

                if total_imported % 10000 == 0:
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
        logger.info(f"Skipped {skipped_stop} stop_times (stop not found/mapped)")

    return total_imported


def analyze_gtfs(zf: zipfile.ZipFile):
    """Analyze GTFS file structure."""
    print("\n" + "=" * 60)
    print("GTFS FILE ANALYSIS")
    print("=" * 60)

    print("\nFiles in archive:")
    for name in sorted(zf.namelist()):
        info = zf.getinfo(name)
        print(f"  {name}: {info.file_size:,} bytes")

    # Analyze stops
    print("\nStops:")
    with zf.open('stops.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        stations = []
        platforms = []
        for row in reader:
            stop_id = row['stop_id'].strip()
            location_type = row.get('location_type', '0').strip()
            if location_type == '1':
                stations.append(stop_id)
            else:
                platforms.append(stop_id)
        print(f"  Stations (location_type=1): {len(stations)}")
        print(f"    IDs: {stations[:5]}..." if len(stations) > 5 else f"    IDs: {stations}")
        print(f"  Platforms (location_type=0): {len(platforms)}")
        print(f"    IDs: {platforms[:5]}..." if len(platforms) > 5 else f"    IDs: {platforms}")

    # Analyze trips
    print("\nTrips:")
    with zf.open('trips.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        trips = list(reader)
        print(f"  Total: {len(trips)}")
        if trips:
            print(f"  Sample trip_id: {trips[0]['trip_id'].strip()}")

    # Analyze stop_times
    print("\nStop times:")
    with zf.open('stop_times.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        stop_ids = set()
        count = 0
        for row in reader:
            stop_ids.add(row['stop_id'].strip())
            count += 1
        print(f"  Total: {count:,}")
        print(f"  Unique stop_ids used: {len(stop_ids)}")
        print(f"    IDs: {sorted(stop_ids)[:5]}..." if len(stop_ids) > 5 else f"    IDs: {sorted(stop_ids)}")

    # Check if frequencies.txt exists
    if 'frequencies.txt' in zf.namelist():
        print("\nFrequencies:")
        with zf.open('frequencies.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
            freqs = list(reader)
            print(f"  Total: {len(freqs)}")
            if freqs:
                print(f"  Sample: headway_secs={freqs[0].get('headway_secs', 'N/A').strip()}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Import GTFS data for Metro de Sevilla'
    )
    parser.add_argument('zip_path', help='Path to GTFS zip file (google_transit.zip)')
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze GTFS file structure and exit'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be imported without making changes'
    )

    args = parser.parse_args()

    if not os.path.exists(args.zip_path):
        logger.error(f"File not found: {args.zip_path}")
        sys.exit(1)

    with zipfile.ZipFile(args.zip_path, 'r') as zf:
        # Analyze mode
        if args.analyze:
            analyze_gtfs(zf)
            sys.exit(0)

        if args.dry_run:
            logger.info("DRY RUN - No changes will be made")
            analyze_gtfs(zf)
            sys.exit(0)

        # Real import
        db = SessionLocal()

        try:
            start_time = datetime.now()

            # Verify prerequisites
            if not verify_route_exists(db):
                sys.exit(1)

            our_stops = verify_our_stops(db)
            if not our_stops:
                sys.exit(1)

            # Clear existing data
            clear_metro_sev_data(db)

            # Import data
            calendar_count = import_calendar(db, zf)
            logger.info(f"Imported {calendar_count} calendar entries")

            calendar_dates_count = import_calendar_dates(db, zf)
            if calendar_dates_count > 0:
                logger.info(f"Imported {calendar_dates_count} calendar_dates (exceptions)")

            trips_count = import_trips(db, zf)
            logger.info(f"Imported {trips_count:,} trips")

            stop_times_count = import_stop_times(db, zf, our_stops)
            logger.info(f"Imported {stop_times_count:,} stop_times")

            elapsed = datetime.now() - start_time

            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("Import Summary - Metro de Sevilla")
            logger.info("=" * 60)
            logger.info(f"Calendar entries: {calendar_count:,}")
            if calendar_dates_count > 0:
                logger.info(f"Calendar dates (exceptions): {calendar_dates_count:,}")
            logger.info(f"Trips: {trips_count:,}")
            logger.info(f"Stop times: {stop_times_count:,}")
            logger.info(f"Elapsed time: {elapsed}")
            logger.info("=" * 60)
            logger.info("\nMetro Sevilla GTFS import completed successfully!")

        except Exception as e:
            db.rollback()
            logger.error(f"Import failed: {e}")
            raise
        finally:
            db.close()


if __name__ == '__main__':
    main()
