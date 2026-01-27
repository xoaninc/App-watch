#!/usr/bin/env python3
"""Import GTFS data for Metro de Granada.

Metro Granada GTFS has a simple stop structure:
- stop_ids: 1, 2, 3, ... 26 (simple numbers)
- Our database uses: METRO_GRANADA_1, METRO_GRANADA_2, ... METRO_GRANADA_26

The mapping is straightforward: GTFS N -> METRO_GRANADA_N

Usage:
    python scripts/import_metro_granada_gtfs.py /path/to/gtfs.zip

GTFS Source: NAP ID 1370 - https://nap.transportes.gob.es/Files/Detail/1370
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

# Metro Granada configuration
METRO_GRANADA_ROUTE_ID = 'METRO_GRANADA_L1'
METRO_GRANADA_PREFIX = 'METRO_GRANADA_'


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


def map_metro_granada_stop_id(gtfs_stop_id: str) -> Optional[str]:
    """Map Metro Granada GTFS stop_id to our stop_id.

    GTFS uses simple numbers: 1, 2, 3, ... 26
    Our database uses: METRO_GRANADA_1, METRO_GRANADA_2, ... METRO_GRANADA_26
    """
    if not gtfs_stop_id:
        return None

    try:
        num = int(gtfs_stop_id.strip())
        if 1 <= num <= 26:
            return f"{METRO_GRANADA_PREFIX}{num}"
    except ValueError:
        pass

    return None


def verify_our_stops(db) -> Dict[str, str]:
    """Verify our Metro Granada stops exist and return mapping."""
    result = db.execute(text(
        "SELECT id, name FROM gtfs_stops WHERE id LIKE 'METRO_GRANADA_%'"
    )).fetchall()

    stops = {row[0]: row[1] for row in result}
    logger.info(f"Found {len(stops)} METRO_GRANADA stops in database")

    if not stops:
        logger.error("No METRO_GRANADA stops found! Import stops first.")
        return {}

    return stops


def verify_route_exists(db) -> bool:
    """Verify Metro Granada route exists in database."""
    result = db.execute(text(
        "SELECT id, short_name FROM gtfs_routes WHERE id = :rid"
    ), {'rid': METRO_GRANADA_ROUTE_ID}).fetchone()

    if not result:
        logger.error(f"Route {METRO_GRANADA_ROUTE_ID} not found in database!")
        return False

    logger.info(f"Found route: {result[0]} ({result[1]})")
    return True


def clear_metro_granada_data(db):
    """Clear existing Metro Granada trips and stop_times."""
    logger.info("Clearing existing Metro Granada schedule data...")

    # Delete stop_times for Metro Granada trips
    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id IN (
            SELECT id FROM gtfs_trips WHERE route_id = :rid
        )
    """), {'rid': METRO_GRANADA_ROUTE_ID})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id = :rid"
    ), {'rid': METRO_GRANADA_ROUTE_ID})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} trips")


def import_calendar(db, zf: zipfile.ZipFile) -> int:
    """Import calendar.txt data for Metro Granada."""
    logger.info("Importing calendar data...")

    with zf.open('calendar.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        rows = []

        for row in reader:
            service_id = row['service_id'].strip()

            # Prefix service_id to avoid conflicts with other operators
            our_service_id = f"{METRO_GRANADA_PREFIX}{service_id}"

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
    """Import calendar_dates.txt data (service exceptions).

    Note: calendar_dates.txt may contain service_ids not in calendar.txt.
    For exception_type=1 (added), the service only operates on specific dates.
    We create dummy calendar entries for these service_ids first.
    """
    logger.info("Importing calendar_dates data...")

    if 'calendar_dates.txt' not in zf.namelist():
        logger.info("No calendar_dates.txt found - skipping")
        return 0

    # First, get all existing service_ids in calendar
    existing_services = set(row[0] for row in db.execute(text(
        "SELECT service_id FROM gtfs_calendar WHERE service_id LIKE 'METRO_GRANADA_%'"
    )).fetchall())
    logger.info(f"Found {len(existing_services)} existing calendar service_ids")

    with zf.open('calendar_dates.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        rows = []
        missing_services = set()

        for row in reader:
            service_id = row['service_id'].strip()
            our_service_id = f"{METRO_GRANADA_PREFIX}{service_id}"

            # Track service_ids that don't exist in calendar
            if our_service_id not in existing_services:
                missing_services.add(our_service_id)

            rows.append({
                'service_id': our_service_id,
                'date': parse_date(row['date']),
                'exception_type': int(row['exception_type'].strip()),
            })

        # Create dummy calendar entries for missing service_ids
        # These are services that only operate on specific dates (holidays, etc.)
        if missing_services:
            logger.info(f"Creating {len(missing_services)} dummy calendar entries for exception-only services")
            dummy_rows = [{
                'service_id': sid,
                'monday': False,
                'tuesday': False,
                'wednesday': False,
                'thursday': False,
                'friday': False,
                'saturday': False,
                'sunday': False,
                'start_date': '2025-01-01',
                'end_date': '2026-12-31',
            } for sid in missing_services]

            db.execute(
                text("""
                    INSERT INTO gtfs_calendar
                    (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                    VALUES (:service_id, :monday, :tuesday, :wednesday, :thursday, :friday, :saturday, :sunday, :start_date, :end_date)
                    ON CONFLICT (service_id) DO NOTHING
                """),
                dummy_rows
            )
            db.commit()

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
    """Import trips.txt data for Metro Granada."""
    logger.info("Importing trips data...")

    with zf.open('trips.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        rows = []

        for row in reader:
            trip_id = row['trip_id'].strip()
            service_id = row['service_id'].strip()

            # Prefix IDs to avoid conflicts
            our_trip_id = f"{METRO_GRANADA_PREFIX}{trip_id}"
            our_service_id = f"{METRO_GRANADA_PREFIX}{service_id}"

            direction_id = row.get('direction_id', '').strip()

            rows.append({
                'id': our_trip_id,
                'route_id': METRO_GRANADA_ROUTE_ID,
                'service_id': our_service_id,
                'headsign': row.get('trip_headsign', '').strip() or None,
                'short_name': None,
                'direction_id': int(direction_id) if direction_id else None,
                'block_id': None,
                'shape_id': row.get('shape_id', '').strip() or None,
                'wheelchair_accessible': int(row.get('wheelchair_accessible', 1) or 1),
                'bikes_allowed': int(row.get('bikes_allowed', 1) or 1),
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
    """Import stop_times.txt data with stop_id mapping."""
    logger.info("Importing stop_times data...")

    # Get existing trip_ids
    existing_trips = set(row[0] for row in db.execute(text(
        "SELECT id FROM gtfs_trips WHERE route_id = :rid"
    ), {'rid': METRO_GRANADA_ROUTE_ID}).fetchall())

    logger.info(f"Found {len(existing_trips)} Metro Granada trips in database")

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
            our_trip_id = f"{METRO_GRANADA_PREFIX}{trip_id}"

            # Skip if trip doesn't exist
            if our_trip_id not in existing_trips:
                skipped_trip += 1
                continue

            # Map GTFS stop_id to our stop_id
            our_stop_id = map_metro_granada_stop_id(gtfs_stop_id)
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

                if total_imported % 50000 == 0:
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
    print("GTFS FILE ANALYSIS - METRO GRANADA")
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
        stops = list(reader)
        print(f"  Total: {len(stops)}")
        if stops:
            print(f"  Sample: {stops[0]['stop_id'].strip()} = {stops[0]['stop_name'].strip()}")
            print(f"  Last: {stops[-1]['stop_id'].strip()} = {stops[-1]['stop_name'].strip()}")

    # Analyze trips
    print("\nTrips:")
    with zf.open('trips.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        trips = list(reader)
        print(f"  Total: {len(trips)}")
        headsigns = set(t.get('trip_headsign', '').strip() for t in trips)
        print(f"  Headsigns: {headsigns}")

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
        print(f"  Unique stop_ids: {len(stop_ids)}")
        print(f"  Stop IDs: {sorted(stop_ids, key=lambda x: int(x) if x.isdigit() else 0)}")

    # Analyze calendar
    print("\nCalendar:")
    with zf.open('calendar.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        services = list(reader)
        print(f"  Services: {len(services)}")
        for s in services:
            days = []
            for d in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                if s[d].strip() == '1':
                    days.append(d[:3])
            print(f"    {s['service_id'].strip()}: {', '.join(days) or 'none'}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Import GTFS data for Metro de Granada'
    )
    parser.add_argument('zip_path', help='Path to GTFS zip file')
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
            clear_metro_granada_data(db)

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
            logger.info("Import Summary - Metro de Granada")
            logger.info("=" * 60)
            logger.info(f"Calendar entries: {calendar_count:,}")
            if calendar_dates_count > 0:
                logger.info(f"Calendar dates (exceptions): {calendar_dates_count:,}")
            logger.info(f"Trips: {trips_count:,}")
            logger.info(f"Stop times: {stop_times_count:,}")
            logger.info(f"Elapsed time: {elapsed}")
            logger.info("=" * 60)
            logger.info("\nMetro Granada GTFS import completed successfully!")

        except Exception as e:
            db.rollback()
            logger.error(f"Import failed: {e}")
            raise
        finally:
            db.close()


if __name__ == '__main__':
    main()
