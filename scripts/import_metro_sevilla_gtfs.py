#!/usr/bin/env python3
"""Import and expand GTFS data for Metro de Sevilla.

This script:
1. Imports calendar.txt with service periods by season
2. Imports calendar_dates.txt (festivos) + adds missing 24/12/2026
3. Expands frequencies.txt into individual trips
4. Generates stop_times for each expanded trip

The NAP GTFS uses frequencies.txt instead of individual trips.
This script expands ~104 base trips with ~594 frequency entries into
~3,500 individual trips with ~73,500 stop_times.

Usage:
    python scripts/import_metro_sevilla_gtfs.py /tmp/gtfs_metro_sevilla
    python scripts/import_metro_sevilla_gtfs.py /tmp/gtfs_metro_sevilla --dry-run
    python scripts/import_metro_sevilla_gtfs.py /tmp/gtfs_metro_sevilla --analyze

GTFS Source: NAP (Punto de Acceso Nacional) File ID 1583
"""

import sys
import os
import csv
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BATCH_SIZE = 5000

# Metro Sevilla configuration
METRO_SEV_ROUTE_ID = 'METRO_SEV_L1_CE_OQ'
METRO_SEV_NETWORK_ID = 'METRO_SEV'

# Shape IDs for directions
SHAPE_ID_CE_OQ = 'METRO_SEV_L1_CE_OQ'  # Ciudad Expo -> Olivar de Quintos
SHAPE_ID_OQ_CE = 'METRO_SEV_L1_OQ_CE'  # Olivar de Quintos -> Ciudad Expo


def time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS or H:MM:SS to seconds since midnight."""
    parts = time_str.strip().split(':')
    if len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    elif len(parts) == 2:
        hours, minutes = int(parts[0]), int(parts[1])
        seconds = 0
    else:
        return 0
    return hours * 3600 + minutes * 60 + seconds


def seconds_to_time(secs: int) -> str:
    """Convert seconds since midnight to HH:MM:SS format."""
    hours = secs // 3600
    minutes = (secs % 3600) // 60
    seconds = secs % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def parse_date(date_str: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD."""
    date_str = date_str.strip()
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


def map_metro_sev_stop_id(gtfs_stop_id: str) -> Optional[str]:
    """Map Metro Sevilla GTFS platform ID to our station ID.

    GTFS uses L1-N (platforms), we use METRO_SEV_L1_EN (stations).
    """
    if not gtfs_stop_id:
        return None

    # Parse L1-N format (platforms)
    if gtfs_stop_id.startswith('L1-') and not gtfs_stop_id.startswith('L1-E'):
        try:
            num = int(gtfs_stop_id.split('-')[1])
            return f"METRO_SEV_L1_E{num}"
        except (ValueError, IndexError):
            return None

    return None


def load_csv(directory: str, filename: str) -> List[Dict]:
    """Load a CSV file from the GTFS directory."""
    filepath = os.path.join(directory, filename)
    if not os.path.exists(filepath):
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        return [row for row in reader]


def load_stop_times_templates(directory: str) -> Dict[str, List[Tuple[str, int]]]:
    """Load base stop_times and compute time offsets from first stop.

    Returns dict mapping trip_id -> [(stop_id, offset_seconds), ...]
    """
    rows = load_csv(directory, 'stop_times.txt')

    templates = defaultdict(list)

    for row in rows:
        trip_id = row['trip_id'].strip()
        stop_id = row['stop_id'].strip()
        arrival_time = row['arrival_time'].strip()
        stop_sequence = int(row['stop_sequence'].strip())

        arrival_secs = time_to_seconds(arrival_time)
        templates[trip_id].append((stop_id, stop_sequence, arrival_secs))

    # Sort by stop_sequence and compute offsets from first stop
    result = {}
    for trip_id, stops in templates.items():
        stops.sort(key=lambda x: x[1])  # Sort by stop_sequence
        first_time = stops[0][2]
        result[trip_id] = [(stop_id, arr_secs - first_time) for stop_id, seq, arr_secs in stops]

    return result


def load_trips_info(directory: str) -> Dict[str, Dict]:
    """Load trip information (service_id, direction, headsign)."""
    rows = load_csv(directory, 'trips.txt')

    trips = {}
    for row in rows:
        trip_id = row['trip_id'].strip()
        trips[trip_id] = {
            'service_id': row['service_id'].strip(),
            'direction_id': int(row.get('direction_id', '0').strip() or '0'),
            'headsign': row.get('trip_headsign', '').strip(),
            'short_name': row.get('trip_short_name', '').strip(),
        }

    return trips


def load_frequencies(directory: str) -> List[Dict]:
    """Load frequencies.txt and parse time values."""
    rows = load_csv(directory, 'frequencies.txt')

    frequencies = []
    for row in rows:
        frequencies.append({
            'trip_id': row['trip_id'].strip(),
            'start_time': time_to_seconds(row['start_time'].strip()),
            'end_time': time_to_seconds(row['end_time'].strip()),
            'headway_secs': int(row['headway_secs'].strip()),
        })

    return frequencies


def expand_frequencies(
    frequencies: List[Dict],
    trips_info: Dict[str, Dict],
    stop_times_templates: Dict[str, List[Tuple[str, int]]]
) -> Tuple[List[Dict], List[Dict]]:
    """Expand frequencies into individual trips and stop_times.

    Returns (trips, stop_times) where each is a list of dicts.
    """
    expanded_trips = []
    expanded_stop_times = []

    trip_counter = defaultdict(int)

    for freq in frequencies:
        base_trip_id = freq['trip_id']
        start_time = freq['start_time']
        end_time = freq['end_time']
        headway_secs = freq['headway_secs']

        if base_trip_id not in trips_info:
            logger.warning(f"Trip {base_trip_id} not found in trips.txt")
            continue

        if base_trip_id not in stop_times_templates:
            logger.warning(f"Trip {base_trip_id} not found in stop_times.txt")
            continue

        trip_info = trips_info[base_trip_id]
        template = stop_times_templates[base_trip_id]

        # Generate trips at each headway interval
        current_time = start_time
        while current_time < end_time:
            trip_counter[base_trip_id] += 1
            trip_num = trip_counter[base_trip_id]

            # Create unique trip_id: METRO_SEV_{base_trip_id}_{trip_num:04d}
            new_trip_id = f"METRO_SEV_{base_trip_id}_{trip_num:04d}"
            our_service_id = f"METRO_SEV_{trip_info['service_id']}"

            # Determine direction and shape
            direction_id = trip_info['direction_id']
            if base_trip_id.startswith('CE-'):
                shape_id = SHAPE_ID_CE_OQ
            else:  # OQ-CE or PO-CE
                shape_id = SHAPE_ID_OQ_CE

            expanded_trips.append({
                'id': new_trip_id,
                'route_id': METRO_SEV_ROUTE_ID,
                'service_id': our_service_id,
                'headsign': trip_info['headsign'],
                'short_name': trip_info['short_name'] or None,
                'direction_id': direction_id,
                'block_id': None,
                'shape_id': shape_id,
                'wheelchair_accessible': 1,
                'bikes_allowed': None,
            })

            # Generate stop_times with offset from current_time
            for seq, (gtfs_stop_id, offset_secs) in enumerate(template, 1):
                our_stop_id = map_metro_sev_stop_id(gtfs_stop_id)
                if not our_stop_id:
                    continue

                arrival_secs = current_time + offset_secs
                time_str = seconds_to_time(arrival_secs)

                expanded_stop_times.append({
                    'trip_id': new_trip_id,
                    'stop_sequence': seq,
                    'stop_id': our_stop_id,
                    'arrival_time': time_str,
                    'departure_time': time_str,
                    'arrival_seconds': arrival_secs,
                    'departure_seconds': arrival_secs,
                    'stop_headsign': None,
                    'pickup_type': 0,
                    'drop_off_type': 0,
                    'shape_dist_traveled': None,
                    'timepoint': 1,
                })

            current_time += headway_secs

    return expanded_trips, expanded_stop_times


def verify_our_stops(db) -> Dict[str, str]:
    """Verify our Metro Sevilla stops exist."""
    result = db.execute(text(
        "SELECT id, name FROM gtfs_stops WHERE id LIKE 'METRO_SEV_%'"
    )).fetchall()

    stops = {row[0]: row[1] for row in result}
    logger.info(f"Found {len(stops)} METRO_SEV stops in database")

    return stops


def verify_route_exists(db) -> bool:
    """Verify Metro Sevilla route exists."""
    result = db.execute(text(
        "SELECT id, short_name FROM gtfs_routes WHERE id = :rid"
    ), {'rid': METRO_SEV_ROUTE_ID}).fetchone()

    if not result:
        logger.error(f"Route {METRO_SEV_ROUTE_ID} not found!")
        return False

    logger.info(f"Found route: {result[0]} ({result[1]})")
    return True


def clear_metro_sev_data(db):
    """Clear existing Metro Sevilla trips and stop_times."""
    logger.info("Clearing existing Metro Sevilla schedule data...")

    # Delete stop_times
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

    # Delete calendar_dates for METRO_SEV
    result = db.execute(text(
        "DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_SEV_%'"
    ))
    db.commit()
    logger.info(f"  Cleared {result.rowcount} calendar_dates")

    # Delete calendars
    result = db.execute(text(
        "DELETE FROM gtfs_calendar WHERE service_id LIKE 'METRO_SEV_%'"
    ))
    db.commit()
    logger.info(f"  Cleared {result.rowcount} calendar entries")


def import_calendar(db, directory: str) -> int:
    """Import calendar.txt with METRO_SEV_ prefix."""
    logger.info("Importing calendar data...")

    rows = load_csv(directory, 'calendar.txt')

    calendar_rows = []
    for row in rows:
        service_id = row['service_id'].strip()
        our_service_id = f"METRO_SEV_{service_id}"

        calendar_rows.append({
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

    if calendar_rows:
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
            calendar_rows
        )
        db.commit()

    return len(calendar_rows)


def import_calendar_dates(db, directory: str) -> int:
    """Import calendar_dates.txt with METRO_SEV_ prefix + add missing 24/12/2026."""
    logger.info("Importing calendar_dates data...")

    rows = load_csv(directory, 'calendar_dates.txt')

    calendar_dates_rows = []
    for row in rows:
        service_id = row['service_id'].strip()
        our_service_id = f"METRO_SEV_{service_id}"

        calendar_dates_rows.append({
            'service_id': our_service_id,
            'date': parse_date(row['date']),
            'exception_type': int(row['exception_type'].strip()),
        })

    # Add missing víspera Navidad 24/12/2026
    # On this day, VIERNES service applies (nocturnal until 02:00)
    # and LABORABLE service is removed
    logger.info("Adding missing víspera Navidad (24/12/2026)...")

    # Add VIERNES service for 24/12/2026 (exception_type=1 = service added)
    calendar_dates_rows.append({
        'service_id': 'METRO_SEV_2026_Viernes_SEP_DIC',
        'date': '2026-12-24',
        'exception_type': 1,
    })

    # Remove LABORABLE service for 24/12/2026 (exception_type=2 = service removed)
    calendar_dates_rows.append({
        'service_id': 'METRO_SEV_2026_Laborable_SEP_DIC',
        'date': '2026-12-24',
        'exception_type': 2,
    })

    if calendar_dates_rows:
        for i in range(0, len(calendar_dates_rows), BATCH_SIZE):
            batch = calendar_dates_rows[i:i+BATCH_SIZE]
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

    return len(calendar_dates_rows)


def import_trips(db, trips: List[Dict]) -> int:
    """Import expanded trips."""
    logger.info(f"Importing {len(trips):,} expanded trips...")

    for i in range(0, len(trips), BATCH_SIZE):
        batch = trips[i:i+BATCH_SIZE]
        db.execute(
            text("""
                INSERT INTO gtfs_trips
                (id, route_id, service_id, headsign, short_name, direction_id, block_id, shape_id, wheelchair_accessible, bikes_allowed)
                VALUES (:id, :route_id, :service_id, :headsign, :short_name, :direction_id, :block_id, :shape_id, :wheelchair_accessible, :bikes_allowed)
                ON CONFLICT (id) DO UPDATE SET
                    route_id = EXCLUDED.route_id,
                    service_id = EXCLUDED.service_id,
                    headsign = EXCLUDED.headsign,
                    direction_id = EXCLUDED.direction_id,
                    shape_id = EXCLUDED.shape_id
            """),
            batch
        )

        if (i + BATCH_SIZE) % 10000 == 0 or i + BATCH_SIZE >= len(trips):
            logger.info(f"  Imported {min(i + BATCH_SIZE, len(trips)):,} trips...")
            db.commit()

    db.commit()
    return len(trips)


def import_stop_times(db, stop_times: List[Dict], our_stops: Dict[str, str]) -> int:
    """Import expanded stop_times, filtering to valid stops."""
    logger.info(f"Importing {len(stop_times):,} stop_times...")

    # Filter to stops that exist in our database
    valid_stop_times = [st for st in stop_times if st['stop_id'] in our_stops]
    skipped = len(stop_times) - len(valid_stop_times)

    if skipped > 0:
        logger.warning(f"Skipping {skipped} stop_times with unknown stops")

    for i in range(0, len(valid_stop_times), BATCH_SIZE):
        batch = valid_stop_times[i:i+BATCH_SIZE]
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
            batch
        )

        if (i + BATCH_SIZE) % 20000 == 0 or i + BATCH_SIZE >= len(valid_stop_times):
            logger.info(f"  Imported {min(i + BATCH_SIZE, len(valid_stop_times)):,} stop_times...")
            db.commit()

    db.commit()
    return len(valid_stop_times)


def analyze_gtfs(directory: str):
    """Analyze GTFS files and show expansion estimates."""
    print("\n" + "=" * 70)
    print("METRO SEVILLA GTFS ANALYSIS")
    print("=" * 70)

    # Calendar
    calendars = load_csv(directory, 'calendar.txt')
    print(f"\nCalendar entries: {len(calendars)}")
    if calendars:
        service_ids = [c['service_id'].strip() for c in calendars]
        print(f"  Sample: {service_ids[:3]}...")

    # Calendar dates
    calendar_dates = load_csv(directory, 'calendar_dates.txt')
    print(f"\nCalendar dates (exceptions): {len(calendar_dates)}")
    print("  Note: Missing 24/12/2026 (víspera Navidad) - will be added")

    # Trips
    trips_info = load_trips_info(directory)
    print(f"\nBase trips: {len(trips_info)}")

    # Frequencies
    frequencies = load_frequencies(directory)
    print(f"\nFrequency entries: {len(frequencies)}")

    # Stop times templates
    templates = load_stop_times_templates(directory)
    print(f"\nStop times templates: {len(templates)} base trips")
    if templates:
        first_trip = list(templates.keys())[0]
        print(f"  Sample trip {first_trip}: {len(templates[first_trip])} stops")

    # Estimate expansion
    print("\n" + "-" * 70)
    print("EXPANSION ESTIMATES")
    print("-" * 70)

    total_trips = 0
    total_stop_times = 0

    for freq in frequencies:
        base_trip_id = freq['trip_id']
        start_time = freq['start_time']
        end_time = freq['end_time']
        headway_secs = freq['headway_secs']

        if base_trip_id not in templates:
            continue

        num_stops = len(templates[base_trip_id])
        num_trips = 0

        current_time = start_time
        while current_time < end_time:
            num_trips += 1
            current_time += headway_secs

        total_trips += num_trips
        total_stop_times += num_trips * num_stops

    print(f"\nEstimated expanded trips: {total_trips:,}")
    print(f"Estimated stop_times: {total_stop_times:,}")

    # By service type
    print("\n" + "-" * 70)
    print("TRIPS BY SERVICE TYPE (estimated)")
    print("-" * 70)

    by_service = defaultdict(int)
    for freq in frequencies:
        base_trip_id = freq['trip_id']
        if base_trip_id not in trips_info:
            continue

        service_id = trips_info[base_trip_id]['service_id']

        start_time = freq['start_time']
        end_time = freq['end_time']
        headway_secs = freq['headway_secs']

        num_trips = 0
        current_time = start_time
        while current_time < end_time:
            num_trips += 1
            current_time += headway_secs

        by_service[service_id] += num_trips

    for service_id in sorted(by_service.keys()):
        print(f"  {service_id}: {by_service[service_id]:,} trips")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Import and expand GTFS data for Metro de Sevilla'
    )
    parser.add_argument('gtfs_dir', help='Path to GTFS directory (e.g., /tmp/gtfs_metro_sevilla)')
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze GTFS files and show expansion estimates'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Expand data but do not import to database'
    )

    args = parser.parse_args()

    if not os.path.isdir(args.gtfs_dir):
        logger.error(f"Directory not found: {args.gtfs_dir}")
        sys.exit(1)

    # Analyze mode
    if args.analyze:
        analyze_gtfs(args.gtfs_dir)
        sys.exit(0)

    # Load GTFS data
    logger.info(f"Loading GTFS data from {args.gtfs_dir}...")

    trips_info = load_trips_info(args.gtfs_dir)
    logger.info(f"Loaded {len(trips_info)} base trips")

    templates = load_stop_times_templates(args.gtfs_dir)
    logger.info(f"Loaded stop_times templates for {len(templates)} trips")

    frequencies = load_frequencies(args.gtfs_dir)
    logger.info(f"Loaded {len(frequencies)} frequency entries")

    # Expand frequencies
    logger.info("Expanding frequencies to individual trips...")
    expanded_trips, expanded_stop_times = expand_frequencies(
        frequencies, trips_info, templates
    )

    logger.info(f"Expanded to {len(expanded_trips):,} trips")
    logger.info(f"Expanded to {len(expanded_stop_times):,} stop_times")

    if args.dry_run:
        logger.info("\nDRY RUN - No changes made to database")

        # Show sample of expanded data
        print("\n" + "-" * 70)
        print("SAMPLE EXPANDED TRIPS")
        print("-" * 70)
        for trip in expanded_trips[:5]:
            print(f"  {trip['id']}: {trip['headsign']} (service: {trip['service_id']})")

        print("\n" + "-" * 70)
        print("SAMPLE STOP_TIMES")
        print("-" * 70)
        if expanded_trips:
            first_trip_id = expanded_trips[0]['id']
            first_trip_stops = [st for st in expanded_stop_times if st['trip_id'] == first_trip_id][:5]
            for st in first_trip_stops:
                print(f"  {st['stop_id']}: {st['arrival_time']} (seq {st['stop_sequence']})")

        analyze_gtfs(args.gtfs_dir)
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
            logger.error("No METRO_SEV stops found! Import stops first.")
            sys.exit(1)

        # Clear existing data
        clear_metro_sev_data(db)

        # Import calendar
        calendar_count = import_calendar(db, args.gtfs_dir)
        logger.info(f"Imported {calendar_count} calendar entries")

        # Import calendar_dates (with added víspera Navidad)
        calendar_dates_count = import_calendar_dates(db, args.gtfs_dir)
        logger.info(f"Imported {calendar_dates_count} calendar_dates")

        # Import expanded trips
        trips_count = import_trips(db, expanded_trips)
        logger.info(f"Imported {trips_count:,} trips")

        # Import expanded stop_times
        stop_times_count = import_stop_times(db, expanded_stop_times, our_stops)
        logger.info(f"Imported {stop_times_count:,} stop_times")

        elapsed = datetime.now() - start_time

        # Summary
        print("\n" + "=" * 70)
        print("IMPORT SUMMARY - Metro de Sevilla")
        print("=" * 70)
        print(f"Calendar entries: {calendar_count}")
        print(f"Calendar dates: {calendar_dates_count} (includes víspera Navidad 24/12/2026)")
        print(f"Trips: {trips_count:,}")
        print(f"Stop times: {stop_times_count:,}")
        print(f"Elapsed time: {elapsed}")
        print("=" * 70)
        print("\nMetro Sevilla GTFS import completed successfully!")
        print("\nNext steps:")
        print("  1. Restart the server to reload GTFSStore")
        print("  2. Verify with: SELECT COUNT(*) FROM gtfs_trips WHERE route_id LIKE 'METRO_SEV%';")
        print("  3. Test departures: curl 'http://localhost:8002/api/v1/gtfs/stops/METRO_SEV_L1_E1/departures?limit=5'")

    except Exception as e:
        db.rollback()
        logger.error(f"Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
