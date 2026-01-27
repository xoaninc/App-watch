#!/usr/bin/env python3
"""Generate full-day trips for Metro Madrid based on GTFS frequencies.

Metro Madrid publishes GTFS with frequencies.txt, not individual trip schedules.
RAPTOR needs individual stop_times to calculate routes.

This script:
1. Downloads the official Metro Madrid GTFS from CRTM
2. Reads the trip templates and their stop_times (travel times between stations)
3. Reads the frequencies (headways per time period)
4. Generates individual trips for each departure throughout the day
5. Creates stop_times for each trip

Usage:
    python scripts/generate_metro_madrid_from_gtfs.py --analyze
    python scripts/generate_metro_madrid_from_gtfs.py --dry-run
    python scripts/generate_metro_madrid_from_gtfs.py

GTFS Source: https://crtm.maps.arcgis.com/sharing/rest/content/items/5c7f2951962540d69ffe8f640d94c246/data
"""

import os
import sys
import csv
import zipfile
import logging
import argparse
import tempfile
import urllib.request
from datetime import datetime
from io import TextIOWrapper
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
GTFS_URL = "https://crtm.maps.arcgis.com/sharing/rest/content/items/5c7f2951962540d69ffe8f640d94c246/data"
BATCH_SIZE = 5000

# Map GTFS service_ids to our day types
GTFS_SERVICE_TO_DAY_TYPE = {
    '4_I12': 'saturday',
    '4_I13': 'sunday',
    '4_I14': 'weekday',
    '4_I15': 'friday',
}

# Our service IDs in the database
SERVICE_IDS = {
    'weekday': 'METRO_MAD_LABORABLE',
    'friday': 'METRO_MAD_VIERNES',
    'saturday': 'METRO_MAD_SABADO',
    'sunday': 'METRO_MAD_DOMINGO',
}

# Map GTFS route_ids to our route_ids
# GTFS uses 4__X___ format, we use METRO_X format
GTFS_ROUTE_TO_OUR_ROUTE = {
    '4__1___': 'METRO_1',
    '4__2___': 'METRO_2',
    '4__3___': 'METRO_3',
    '4__4___': 'METRO_4',
    '4__5___': 'METRO_5',
    '4__6___': 'METRO_6',
    '4__7___': 'METRO_7',
    '4__8___': 'METRO_8',
    '4__9___': 'METRO_9',
    '4__10___': 'METRO_10',
    '4__11___': 'METRO_11',
    '4__12___': 'METRO_12',
    '4__R___': 'METRO_R',
}


@dataclass
class TripTemplate:
    """Template trip with stop sequence and travel times."""
    gtfs_trip_id: str
    our_route_id: str
    direction_id: int
    headsign: str
    stop_times: List[Dict] = field(default_factory=list)


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
    temp_path = os.path.join(tempfile.gettempdir(), "metro_madrid_gtfs.zip")
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
    """Map GTFS stop_id (par_4_XXX) to our stop_id (METRO_XXX).

    GTFS format: par_4_XXX where XXX is the station number
    Our format: METRO_XXX
    """
    if not gtfs_stop_id or not gtfs_stop_id.startswith('par_4_'):
        return None

    try:
        num = gtfs_stop_id.replace('par_4_', '')
        return f"METRO_{num}"
    except (ValueError, IndexError):
        return None


def parse_gtfs(zip_path: str) -> Tuple[Dict, Dict]:
    """Parse GTFS file to extract trip templates and frequencies.

    Returns:
        (templates_by_route_dir, frequencies_by_route_day_dir)
    """
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Read routes to understand the mapping
        logger.info("Reading routes.txt...")
        routes_info = {}
        with zf.open('routes.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8-sig'))
            for row in reader:
                gtfs_route_id = row['route_id'].strip()
                if gtfs_route_id in GTFS_ROUTE_TO_OUR_ROUTE:
                    routes_info[gtfs_route_id] = GTFS_ROUTE_TO_OUR_ROUTE[gtfs_route_id]
        logger.info(f"  Found {len(routes_info)} Metro Madrid routes")

        # Read trips
        logger.info("Reading trips.txt...")
        trips_by_id = {}
        with zf.open('trips.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8-sig'))
            for row in reader:
                gtfs_route_id = row['route_id'].strip()
                if gtfs_route_id not in routes_info:
                    continue

                trip_id = row['trip_id'].strip()
                service_id = row['service_id'].strip()

                trips_by_id[trip_id] = {
                    'gtfs_route_id': gtfs_route_id,
                    'our_route_id': routes_info[gtfs_route_id],
                    'service_id': service_id,
                    'headsign': row.get('trip_headsign', '').strip(),
                    'direction_id': int(row.get('direction_id', 0) or 0),
                }
        logger.info(f"  Found {len(trips_by_id)} trips")

        # Read stop_times
        logger.info("Reading stop_times.txt...")
        stop_times_by_trip = {}
        with zf.open('stop_times.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8-sig'))
            for row in reader:
                trip_id = row['trip_id'].strip()
                if trip_id not in trips_by_id:
                    continue

                if trip_id not in stop_times_by_trip:
                    stop_times_by_trip[trip_id] = []
                stop_times_by_trip[trip_id].append({
                    'stop_id': row['stop_id'].strip(),
                    'stop_sequence': int(row['stop_sequence'].strip()),
                    'arrival_time': row['arrival_time'].strip(),
                    'departure_time': row['departure_time'].strip(),
                })
        logger.info(f"  Found stop_times for {len(stop_times_by_trip)} trips")

        # Build ONE template per (route, direction)
        templates_by_route_dir = {}

        for trip_id, trip_info in trips_by_id.items():
            our_route_id = trip_info['our_route_id']
            direction = trip_info['direction_id']
            key = (our_route_id, direction)

            if key in templates_by_route_dir:
                continue

            if trip_id not in stop_times_by_trip:
                continue

            stop_times = sorted(stop_times_by_trip[trip_id], key=lambda x: x['stop_sequence'])
            if not stop_times:
                continue

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
                    'gtfs_stop_id': st['stop_id'],
                    'stop_sequence': st['stop_sequence'],
                    'arrival_offset': arrival_secs - first_departure,
                    'departure_offset': departure_secs - first_departure,
                })

            if template_stops:
                templates_by_route_dir[key] = TripTemplate(
                    gtfs_trip_id=trip_id,
                    our_route_id=our_route_id,
                    direction_id=direction,
                    headsign=trip_info['headsign'],
                    stop_times=template_stops,
                )

        logger.info(f"  Built {len(templates_by_route_dir)} route/direction templates")

        # Read and consolidate frequencies
        logger.info("Reading frequencies.txt...")
        frequencies_by_route_day_dir = {}

        with zf.open('frequencies.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8-sig'))
            for row in reader:
                trip_id = row['trip_id'].strip()
                if trip_id not in trips_by_id:
                    continue

                trip_info = trips_by_id[trip_id]
                our_route_id = trip_info['our_route_id']
                direction = trip_info['direction_id']
                service_id = trip_info['service_id']

                day_type = GTFS_SERVICE_TO_DAY_TYPE.get(service_id)
                if not day_type:
                    continue

                start_secs = time_str_to_seconds(row['start_time'].strip())
                end_secs = time_str_to_seconds(row['end_time'].strip())

                if end_secs <= start_secs:
                    end_secs += 24 * 3600

                headway = int(row['headway_secs'].strip())

                key = (our_route_id, day_type, direction)
                if key not in frequencies_by_route_day_dir:
                    frequencies_by_route_day_dir[key] = []

                period = FrequencyPeriod(
                    start_seconds=start_secs,
                    end_seconds=end_secs,
                    headway_secs=headway,
                    day_type=day_type,
                )

                existing = frequencies_by_route_day_dir[key]
                is_dup = any(
                    f.start_seconds == start_secs and
                    f.end_seconds == end_secs and
                    f.headway_secs == headway
                    for f in existing
                )
                if not is_dup:
                    frequencies_by_route_day_dir[key].append(period)

        total_freqs = sum(len(f) for f in frequencies_by_route_day_dir.values())
        logger.info(f"  Consolidated to {total_freqs} unique frequency periods")

    return templates_by_route_dir, frequencies_by_route_day_dir


def analyze_gtfs(templates: Dict, frequencies: Dict):
    """Print analysis of GTFS data."""
    print("\n" + "=" * 70)
    print("METRO MADRID GTFS ANALYSIS")
    print("=" * 70)

    print(f"\nRoute/Direction Templates: {len(templates)}")

    routes = {}
    for (route_id, direction), template in templates.items():
        if route_id not in routes:
            routes[route_id] = {}
        routes[route_id][direction] = template

    for route_id in sorted(routes.keys()):
        dirs = routes[route_id]
        print(f"\n  {route_id}:")
        for direction, template in sorted(dirs.items()):
            dir_name = "dir 0" if direction == 0 else "dir 1"
            stops = len(template.stop_times)
            travel_time = template.stop_times[-1]['arrival_offset'] // 60 if template.stop_times else 0
            print(f"    {dir_name}: {stops} stops, {travel_time} min, headsign='{template.headsign}'")

    print(f"\nFrequency Periods by Day Type:")
    for day_type in ['weekday', 'friday', 'saturday', 'sunday']:
        count = sum(1 for k, v in frequencies.items() if k[1] == day_type for _ in v)
        if count > 0:
            print(f"  {day_type}: {count} periods")

    print(f"\nEstimated trips to generate:")
    for day_type in ['weekday', 'friday', 'saturday', 'sunday']:
        total_trips = 0
        for (route_id, dt, direction), freqs in frequencies.items():
            if dt != day_type:
                continue
            for freq in freqs:
                period_duration = freq.end_seconds - freq.start_seconds
                if period_duration > 0:
                    num_trips = (period_duration // freq.headway_secs) + 1
                    total_trips += num_trips
        print(f"  {day_type}: ~{total_trips} trips")

    total_all = sum(
        sum((f.end_seconds - f.start_seconds) // f.headway_secs + 1
            for f in freqs if f.end_seconds > f.start_seconds)
        for freqs in frequencies.values()
    )
    print(f"\n  TOTAL (all day types): ~{total_all} trips")

    avg_stops = 25
    print(f"  Estimated stop_times: ~{total_all * avg_stops} (avg {avg_stops} stops per trip)")

    print("=" * 70)


def verify_our_stops(db, templates: Dict) -> Dict[str, str]:
    """Verify our Metro Madrid stops exist and return mapping."""
    # Collect all stop IDs needed
    needed_stops = set()
    for template in templates.values():
        for st in template.stop_times:
            needed_stops.add(st['stop_id'])

    logger.info(f"Need {len(needed_stops)} unique stops")

    # Check which exist in database
    result = db.execute(text(
        "SELECT id, name FROM gtfs_stops WHERE id LIKE 'METRO\\_%' ESCAPE '\\'"
    )).fetchall()

    our_stops = {row[0]: row[1] for row in result}
    logger.info(f"Found {len(our_stops)} METRO stops in database")

    # Find missing
    missing = needed_stops - set(our_stops.keys())
    if missing:
        logger.warning(f"Missing {len(missing)} stops in database")
        logger.warning(f"  Sample missing: {list(missing)[:10]}")

    return our_stops


def clear_existing_data(db):
    """Clear existing generated Metro Madrid trips."""
    logger.info("Clearing existing generated Metro Madrid data...")

    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id LIKE 'METRO\\_MAD\\_GEN\\_%' ESCAPE '\\'
    """))
    db.commit()
    logger.info(f"  Deleted {result.rowcount} stop_times")

    result = db.execute(text("""
        DELETE FROM gtfs_trips
        WHERE id LIKE 'METRO\\_MAD\\_GEN\\_%' ESCAPE '\\'
    """))
    db.commit()
    logger.info(f"  Deleted {result.rowcount} trips")


def ensure_calendar_entries(db):
    """Ensure calendar entries exist for our service IDs."""
    logger.info("Ensuring calendar entries exist...")

    for day_type, service_id in SERVICE_IDS.items():
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
                sunday = EXCLUDED.sunday
        """), {
            'service_id': service_id,
            'mon': days[0], 'tue': days[1], 'wed': days[2], 'thu': days[3],
            'fri': days[4], 'sat': days[5], 'sun': days[6],
        })

    db.commit()
    logger.info(f"  Created/updated {len(SERVICE_IDS)} calendar entries")


def generate_trips(db, templates: Dict, frequencies: Dict, our_stops: Dict) -> Tuple[int, int]:
    """Generate individual trips from templates and frequencies.

    IMPORTANT: Insert ALL trips first, then ALL stop_times, to avoid FK violations.
    """
    trips_created = 0
    stop_times_created = 0

    # Collect ALL trips and stop_times first
    all_trip_rows = []
    all_stop_time_rows = []

    for day_type, service_id in SERVICE_IDS.items():
        logger.info(f"Generating trips for {day_type} (service: {service_id})...")

        day_trips = 0

        for (route_id, direction), template in templates.items():
            key = (route_id, day_type, direction)
            if key not in frequencies:
                continue

            day_freqs = sorted(frequencies[key], key=lambda x: x.start_seconds)
            if not day_freqs:
                continue

            trip_num = 0
            for freq in day_freqs:
                current_time = freq.start_seconds

                while current_time < freq.end_seconds:
                    new_trip_id = f"METRO_MAD_GEN_{route_id}_{day_type[:3]}_{direction}_{trip_num}"

                    all_trip_rows.append({
                        'id': new_trip_id,
                        'route_id': route_id,
                        'service_id': service_id,
                        'headsign': template.headsign,
                        'direction_id': direction,
                        'wheelchair_accessible': 1,
                    })

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
        description='Generate Metro Madrid trips from GTFS frequencies'
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
    templates, frequencies = parse_gtfs(zip_path)

    if args.analyze:
        analyze_gtfs(templates, frequencies)
        sys.exit(0)

    if args.dry_run:
        logger.info("[DRY RUN MODE - no database changes]")
        analyze_gtfs(templates, frequencies)
        sys.exit(0)

    # Connect to database
    db = SessionLocal()

    try:
        start_time = datetime.now()

        # Verify our stops exist
        our_stops = verify_our_stops(db, templates)
        if not our_stops:
            logger.error("No Metro Madrid stops found in database!")
            logger.error("Import stops first using import_metro_madrid.py or similar")
            sys.exit(1)

        # Clear existing generated data
        clear_existing_data(db)

        # Ensure calendar entries
        ensure_calendar_entries(db)

        # Generate trips
        trips_created, stop_times_created = generate_trips(
            db, templates, frequencies, our_stops
        )

        elapsed = datetime.now() - start_time

        logger.info("\n" + "=" * 60)
        logger.info("METRO MADRID TRIP GENERATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Trips created: {trips_created:,}")
        logger.info(f"Stop times created: {stop_times_created:,}")
        logger.info(f"Elapsed time: {elapsed}")
        logger.info("=" * 60)

    except Exception as e:
        db.rollback()
        logger.error(f"Generation failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
