#!/usr/bin/env python3
"""Generate full-day trips for Metro Sevilla based on GTFS frequencies.

Metro Sevilla publishes GTFS with frequencies.txt, not individual trip schedules.
RAPTOR needs individual stop_times to calculate routes.

This script:
1. Downloads the official Metro Sevilla GTFS
2. Reads the trip templates and their stop_times (travel times between stations)
3. Reads the frequencies (headways per time period)
4. Generates individual trips for each departure throughout the day
5. Creates stop_times for each trip

Usage:
    python scripts/generate_metro_sevilla_trips.py
    python scripts/generate_metro_sevilla_trips.py --dry-run
    python scripts/generate_metro_sevilla_trips.py --analyze

GTFS Source: https://metro-sevilla.es/google-transit/google_transit.zip
"""

import os
import sys
import csv
import zipfile
import logging
import argparse
import tempfile
import urllib.request
from datetime import datetime, time
from io import TextIOWrapper
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
GTFS_URL = "https://metro-sevilla.es/google-transit/google_transit.zip"
METRO_SEV_ROUTE_ID = 'METRO_SEV_L1_CE_OQ'
BATCH_SIZE = 5000

# Service ID prefixes for our database
# We'll create simplified service IDs that cover the current period
SERVICE_IDS = {
    'weekday': 'METRO_SEV_LABORABLE',
    'friday': 'METRO_SEV_VIERNES',
    'saturday': 'METRO_SEV_SABADO',
    'sunday': 'METRO_SEV_DOMINGO',
}


@dataclass
class TripTemplate:
    """Template trip with stop sequence and travel times."""
    trip_id: str
    direction_id: int
    headsign: str
    stop_times: List[Dict]  # [{stop_id, stop_sequence, arrival_offset, departure_offset}]


@dataclass
class FrequencyPeriod:
    """Frequency period with headway."""
    start_seconds: int
    end_seconds: int
    headway_secs: int
    day_type: str


def download_gtfs(url: str) -> str:
    """Download GTFS zip to temp file."""
    logger.info(f"Downloading GTFS from {url}...")
    temp_path = os.path.join(tempfile.gettempdir(), "metro_sevilla_gtfs.zip")
    urllib.request.urlretrieve(url, temp_path)
    logger.info(f"Downloaded to {temp_path}")
    return temp_path


def time_str_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS to seconds since midnight."""
    parts = time_str.strip().split(':')
    if len(parts) != 3:
        return 0
    hours, mins, secs = int(parts[0]), int(parts[1]), int(parts[2])
    return hours * 3600 + mins * 60 + secs


def seconds_to_time_str(secs: int) -> str:
    """Convert seconds to HH:MM:SS (handles >24h for GTFS)."""
    hours = secs // 3600
    mins = (secs % 3600) // 60
    seconds = secs % 60
    return f"{hours:02d}:{mins:02d}:{seconds:02d}"


def map_gtfs_stop_to_our_stop(gtfs_stop_id: str) -> Optional[str]:
    """Map Metro Sevilla GTFS stop_id to our stop_id.

    GTFS uses platforms: L1-1, L1-2, ..., L1-21
    We use stations: METRO_SEV_L1_E1, METRO_SEV_L1_E2, ..., METRO_SEV_L1_E21
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

    # L1-EN format (stations)
    if gtfs_stop_id.startswith('L1-E'):
        try:
            num = int(gtfs_stop_id.split('-E')[1])
            return f"METRO_SEV_L1_E{num}"
        except (ValueError, IndexError):
            return None

    return None


def get_day_type_from_service_id(service_id: str) -> str:
    """Determine day type from GTFS service_id."""
    service_lower = service_id.lower()
    if 'viernes' in service_lower or 'friday' in service_lower:
        return 'friday'
    elif 'sabado' in service_lower or 'saturday' in service_lower:
        return 'saturday'
    elif 'domingo' in service_lower or 'sunday' in service_lower:
        return 'sunday'
    else:
        return 'weekday'


def parse_gtfs(zip_path: str) -> Tuple[Dict[int, TripTemplate], Dict]:
    """Parse GTFS file to extract trip templates and frequencies.

    The GTFS has multiple trip templates per direction (for different periods of the year),
    but they all have the same stop times. We consolidate to one template per direction.

    Returns:
        (templates_by_direction, frequencies_by_day_direction)
        - templates_by_direction: {direction_id: TripTemplate}
        - frequencies_by_day_direction: {day_type_direction: [FrequencyPeriod]}
    """
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Read trips
        logger.info("Reading trips.txt...")
        trips_by_id = {}
        with zf.open('trips.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
            for row in reader:
                trip_id = row['trip_id'].strip()
                trips_by_id[trip_id] = {
                    'route_id': row['route_id'].strip(),
                    'service_id': row['service_id'].strip(),
                    'headsign': row.get('trip_headsign', '').strip(),
                    'direction_id': int(row.get('direction_id', 0) or 0),
                }
        logger.info(f"  Found {len(trips_by_id)} trips in GTFS")

        # Read stop_times
        logger.info("Reading stop_times.txt...")
        stop_times_by_trip = {}
        with zf.open('stop_times.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
            for row in reader:
                trip_id = row['trip_id'].strip()
                if trip_id not in stop_times_by_trip:
                    stop_times_by_trip[trip_id] = []
                stop_times_by_trip[trip_id].append({
                    'stop_id': row['stop_id'].strip(),
                    'stop_sequence': int(row['stop_sequence'].strip()),
                    'arrival_time': row['arrival_time'].strip(),
                    'departure_time': row['departure_time'].strip(),
                })

        # Build ONE template per direction (they all have the same travel times)
        templates_by_direction = {}
        for trip_id, trip_info in trips_by_id.items():
            direction = trip_info['direction_id']

            # Skip if we already have a template for this direction
            if direction in templates_by_direction:
                continue

            if trip_id not in stop_times_by_trip:
                continue

            stop_times = sorted(stop_times_by_trip[trip_id], key=lambda x: x['stop_sequence'])
            if not stop_times:
                continue

            # Calculate offsets from first departure
            first_departure = time_str_to_seconds(stop_times[0]['departure_time'])

            template_stops = []
            for st in stop_times:
                our_stop_id = map_gtfs_stop_to_our_stop(st['stop_id'])
                if not our_stop_id:
                    continue

                arrival_secs = time_str_to_seconds(st['arrival_time'])
                departure_secs = time_str_to_seconds(st['departure_time'])

                template_stops.append({
                    'stop_id': our_stop_id,
                    'stop_sequence': st['stop_sequence'],
                    'arrival_offset': arrival_secs - first_departure,
                    'departure_offset': departure_secs - first_departure,
                })

            if template_stops:
                templates_by_direction[direction] = TripTemplate(
                    trip_id=trip_id,
                    direction_id=direction,
                    headsign=trip_info['headsign'],
                    stop_times=template_stops,
                )

        logger.info(f"  Built {len(templates_by_direction)} direction templates")

        # Read and consolidate frequencies by day_type and direction
        # Multiple GTFS trips map to the same (day_type, direction) combination
        logger.info("Reading frequencies.txt...")
        frequencies_by_day_direction = {}  # {(day_type, direction): [FrequencyPeriod]}

        with zf.open('frequencies.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
            for row in reader:
                trip_id = row['trip_id'].strip()
                if trip_id not in trips_by_id:
                    continue

                trip_info = trips_by_id[trip_id]
                direction = trip_info['direction_id']
                service_id = trip_info['service_id']
                day_type = get_day_type_from_service_id(service_id)

                start_secs = time_str_to_seconds(row['start_time'].strip())
                end_secs = time_str_to_seconds(row['end_time'].strip())
                headway = int(row['headway_secs'].strip())

                key = (day_type, direction)
                if key not in frequencies_by_day_direction:
                    frequencies_by_day_direction[key] = []

                # Check if this period already exists (avoid duplicates)
                period = FrequencyPeriod(
                    start_seconds=start_secs,
                    end_seconds=end_secs,
                    headway_secs=headway,
                    day_type=day_type,
                )

                # Only add if not duplicate (same start, end, headway)
                existing = frequencies_by_day_direction[key]
                is_dup = any(
                    f.start_seconds == start_secs and
                    f.end_seconds == end_secs and
                    f.headway_secs == headway
                    for f in existing
                )
                if not is_dup:
                    frequencies_by_day_direction[key].append(period)

        total_freqs = sum(len(f) for f in frequencies_by_day_direction.values())
        logger.info(f"  Consolidated to {total_freqs} unique frequency periods")

    return templates_by_direction, frequencies_by_day_direction


def analyze_gtfs(templates_by_direction: Dict[int, TripTemplate],
                 frequencies_by_day_direction: Dict):
    """Print analysis of GTFS data."""
    print("\n" + "=" * 70)
    print("METRO SEVILLA GTFS ANALYSIS")
    print("=" * 70)

    print(f"\nDirection Templates: {len(templates_by_direction)}")

    for direction, template in templates_by_direction.items():
        dir_name = "to Olivar de Quintos" if direction == 0 else "to Ciudad Expo"
        print(f"\n  Direction {direction} ({dir_name}):")
        print(f"    Headsign: {template.headsign}")
        print(f"    Stops: {len(template.stop_times)}")
        if template.stop_times:
            last_stop = template.stop_times[-1]
            travel_time = last_stop['arrival_offset'] // 60
            print(f"    Total travel time: {travel_time} minutes")

    print(f"\nFrequency Periods by Day Type:")
    for day_type in ['weekday', 'friday', 'saturday', 'sunday']:
        dir_0_freqs = frequencies_by_day_direction.get((day_type, 0), [])
        dir_1_freqs = frequencies_by_day_direction.get((day_type, 1), [])
        total = len(dir_0_freqs) + len(dir_1_freqs)
        if total > 0:
            print(f"  {day_type}: {total} periods (dir0: {len(dir_0_freqs)}, dir1: {len(dir_1_freqs)})")

    # Calculate how many trips would be generated
    print(f"\nEstimated trips to generate:")
    for day_type in ['weekday', 'friday', 'saturday', 'sunday']:
        total_trips = 0
        for direction in [0, 1]:
            key = (day_type, direction)
            if key not in frequencies_by_day_direction:
                continue
            for freq in frequencies_by_day_direction[key]:
                period_duration = freq.end_seconds - freq.start_seconds
                if period_duration > 0:
                    num_trips = (period_duration // freq.headway_secs) + 1
                    total_trips += num_trips
        print(f"  {day_type}: ~{total_trips} trips")

    total_all = sum(
        sum((f.end_seconds - f.start_seconds) // f.headway_secs + 1
            for f in freqs if f.end_seconds > f.start_seconds)
        for freqs in frequencies_by_day_direction.values()
    )
    print(f"\n  TOTAL (all day types): ~{total_all} trips")
    print(f"  Estimated stop_times: ~{total_all * 21} (21 stops per trip)")

    print("=" * 70)


def clear_existing_data(db):
    """Clear existing Metro Sevilla schedule data."""
    logger.info("Clearing existing Metro Sevilla schedule data...")

    # Get count before deletion
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_trips WHERE route_id = :rid"
    ), {'rid': METRO_SEV_ROUTE_ID}).fetchone()
    existing_trips = result[0]

    # Delete stop_times
    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id LIKE 'METRO_SEV_GEN_%'
    """))
    db.commit()
    logger.info(f"  Deleted {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text("""
        DELETE FROM gtfs_trips
        WHERE id LIKE 'METRO_SEV_GEN_%'
    """))
    db.commit()
    logger.info(f"  Deleted {result.rowcount} generated trips")

    return existing_trips


def ensure_calendar_entries(db):
    """Ensure calendar entries exist for our service IDs."""
    logger.info("Ensuring calendar entries exist...")

    for day_type, service_id in SERVICE_IDS.items():
        # Determine which days this service runs
        days = {
            'weekday': (True, True, True, True, False, False, False),
            'friday': (False, False, False, False, True, False, False),
            'saturday': (False, False, False, False, False, True, False),
            'sunday': (False, False, False, False, False, False, True),
        }[day_type]

        db.execute(text("""
            INSERT INTO gtfs_calendar
            (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
            VALUES (:service_id, :mon, :tue, :wed, :thu, :fri, :sat, :sun, '2025-01-01', '2026-12-31')
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
        """), {
            'service_id': service_id,
            'mon': days[0], 'tue': days[1], 'wed': days[2], 'thu': days[3],
            'fri': days[4], 'sat': days[5], 'sun': days[6],
        })

    db.commit()
    logger.info(f"  Created/updated {len(SERVICE_IDS)} calendar entries")


def verify_our_stops(db) -> Dict[str, str]:
    """Verify our Metro Sevilla stops exist."""
    result = db.execute(text(
        "SELECT id, name FROM gtfs_stops WHERE id LIKE 'METRO_SEV_%'"
    )).fetchall()

    stops = {row[0]: row[1] for row in result}
    logger.info(f"Found {len(stops)} METRO_SEV stops in database")

    if not stops:
        logger.error("No METRO_SEV stops found! Import stops first.")

    return stops


def generate_trips(db, templates_by_direction: Dict[int, TripTemplate],
                   frequencies_by_day_direction: Dict,
                   our_stops: Dict[str, str]) -> Tuple[int, int]:
    """Generate individual trips from templates and frequencies.

    IMPORTANT: Insert ALL trips first, then ALL stop_times, to avoid FK violations.

    Returns: (trips_created, stop_times_created)
    """
    trips_created = 0
    stop_times_created = 0

    # Collect ALL trips and stop_times first
    all_trip_rows = []
    all_stop_time_rows = []

    # Process each day type separately
    for day_type, service_id in SERVICE_IDS.items():
        logger.info(f"Generating trips for {day_type} (service: {service_id})...")

        day_trips = 0

        # Process each direction
        for direction, template in templates_by_direction.items():
            key = (day_type, direction)
            if key not in frequencies_by_day_direction:
                continue

            # Get frequencies for this day type and direction
            day_freqs = frequencies_by_day_direction[key]
            if not day_freqs:
                continue

            # Sort by start time and merge overlapping periods
            day_freqs = sorted(day_freqs, key=lambda x: x.start_seconds)

            # Generate trips for each frequency period
            trip_num = 0
            for freq in day_freqs:
                current_time = freq.start_seconds

                while current_time < freq.end_seconds:
                    # Create unique trip ID
                    new_trip_id = f"METRO_SEV_GEN_{day_type[:3]}_{direction}_{trip_num}"

                    all_trip_rows.append({
                        'id': new_trip_id,
                        'route_id': METRO_SEV_ROUTE_ID,
                        'service_id': service_id,
                        'headsign': template.headsign,
                        'direction_id': direction,
                        'wheelchair_accessible': 1,
                    })

                    # Create stop_times
                    for st in template.stop_times:
                        if st['stop_id'] not in our_stops:
                            continue

                        arr_secs = current_time + st['arrival_offset']
                        dep_secs = current_time + st['departure_offset']

                        all_stop_time_rows.append({
                            'trip_id': new_trip_id,
                            'stop_sequence': st['stop_sequence'],
                            'stop_id': st['stop_id'],
                            'arrival_time': seconds_to_time_str(arr_secs),
                            'departure_time': seconds_to_time_str(dep_secs),
                            'arrival_seconds': arr_secs,
                            'departure_seconds': dep_secs,
                            'pickup_type': 0,
                            'drop_off_type': 0,
                            'timepoint': 1,
                        })

                    day_trips += 1
                    trip_num += 1
                    current_time += freq.headway_secs

        logger.info(f"  {day_type}: {day_trips} trips")

    # Insert ALL trips first (in batches)
    logger.info(f"Inserting {len(all_trip_rows)} trips...")
    for i in range(0, len(all_trip_rows), BATCH_SIZE):
        batch = all_trip_rows[i:i + BATCH_SIZE]
        _insert_trips_batch(db, batch)
        trips_created += len(batch)
    db.commit()
    logger.info(f"  Inserted {trips_created} trips")

    # Then insert ALL stop_times (in batches)
    logger.info(f"Inserting {len(all_stop_time_rows)} stop_times...")
    for i in range(0, len(all_stop_time_rows), BATCH_SIZE):
        batch = all_stop_time_rows[i:i + BATCH_SIZE]
        _insert_stop_times_batch(db, batch)
        stop_times_created += len(batch)
    db.commit()
    logger.info(f"  Inserted {stop_times_created} stop_times")

    return trips_created, stop_times_created


def _insert_trips_batch(db, rows: List[Dict]):
    """Insert batch of trips."""
    db.execute(text("""
        INSERT INTO gtfs_trips
        (id, route_id, service_id, headsign, direction_id, wheelchair_accessible)
        VALUES (:id, :route_id, :service_id, :headsign, :direction_id, :wheelchair_accessible)
        ON CONFLICT (id) DO UPDATE SET
            route_id = EXCLUDED.route_id,
            service_id = EXCLUDED.service_id,
            headsign = EXCLUDED.headsign,
            direction_id = EXCLUDED.direction_id
    """), rows)


def _insert_stop_times_batch(db, rows: List[Dict]):
    """Insert batch of stop_times."""
    db.execute(text("""
        INSERT INTO gtfs_stop_times
        (trip_id, stop_sequence, stop_id, arrival_time, departure_time,
         arrival_seconds, departure_seconds, pickup_type, drop_off_type, timepoint)
        VALUES (:trip_id, :stop_sequence, :stop_id, :arrival_time, :departure_time,
                :arrival_seconds, :departure_seconds, :pickup_type, :drop_off_type, :timepoint)
        ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
            stop_id = EXCLUDED.stop_id,
            arrival_time = EXCLUDED.arrival_time,
            departure_time = EXCLUDED.departure_time,
            arrival_seconds = EXCLUDED.arrival_seconds,
            departure_seconds = EXCLUDED.departure_seconds
    """), rows)


def main():
    parser = argparse.ArgumentParser(
        description='Generate Metro Sevilla trips from GTFS frequencies'
    )
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze GTFS structure and exit'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--gtfs-path',
        help='Path to local GTFS zip (skip download)'
    )

    args = parser.parse_args()

    # Download or use local GTFS
    if args.gtfs_path:
        if not os.path.exists(args.gtfs_path):
            logger.error(f"File not found: {args.gtfs_path}")
            sys.exit(1)
        zip_path = args.gtfs_path
    else:
        zip_path = download_gtfs(GTFS_URL)

    # Parse GTFS
    trip_templates, frequencies = parse_gtfs(zip_path)

    # Analyze mode
    if args.analyze:
        analyze_gtfs(trip_templates, frequencies)
        sys.exit(0)

    if args.dry_run:
        logger.info("[DRY RUN MODE - no database changes]")
        analyze_gtfs(trip_templates, frequencies)
        sys.exit(0)

    # Connect to database
    db = SessionLocal()

    try:
        start_time = datetime.now()

        # Verify our stops exist
        our_stops = verify_our_stops(db)
        if not our_stops:
            logger.error("Cannot proceed without stops. Run import_metro_sevilla.py first.")
            sys.exit(1)

        # Clear existing generated data
        clear_existing_data(db)

        # Ensure calendar entries
        ensure_calendar_entries(db)

        # Generate trips
        trips_created, stop_times_created = generate_trips(
            db, trip_templates, frequencies, our_stops
        )

        elapsed = datetime.now() - start_time

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("METRO SEVILLA TRIP GENERATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Trips created: {trips_created:,}")
        logger.info(f"Stop times created: {stop_times_created:,}")
        logger.info(f"Elapsed time: {elapsed}")
        logger.info("=" * 60)

        # Verify
        result = db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM gtfs_trips WHERE id LIKE 'METRO_SEV_GEN_%') as trips,
                (SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'METRO_SEV_GEN_%') as stop_times
        """)).fetchone()
        logger.info(f"Verification: {result[0]:,} trips, {result[1]:,} stop_times in database")

    except Exception as e:
        db.rollback()
        logger.error(f"Generation failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
