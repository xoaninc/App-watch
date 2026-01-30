#!/usr/bin/env python
"""
Import Metro Bilbao data from GTFS.

Source: https://data.ctb.eus/eu/dataset/horario-metro-bilbao
GTFS URL: https://ctb-gtfs.s3.eu-south-2.amazonaws.com/metrobilbao.zip

GTFS-RT URLs:
- Vehicle Positions: https://ctb-gtfs-rt.s3.eu-south-2.amazonaws.com/metro-bilbao-vehicle-positions.pb
- Trip Updates: https://ctb-gtfs-rt.s3.eu-south-2.amazonaws.com/metro-bilbao-trip-updates.pb
- Alerts: https://ctb-gtfs-rt.s3.eu-south-2.amazonaws.com/metro-bilbao-service-alerts.pb

Usage:
    source .venv/bin/activate && python scripts/import_metro_bilbao_data.py
    source .venv/bin/activate && python scripts/import_metro_bilbao_data.py --dry-run
    source .venv/bin/activate && python scripts/import_metro_bilbao_data.py --trips-only
"""

import os
import csv
import zipfile
import logging
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple

import requests
import psycopg2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
GTFS_URL = "https://ctb-gtfs.s3.eu-south-2.amazonaws.com/metrobilbao.zip"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost/renfeserver_dev"
)
STOP_ID_PREFIX = "METRO_BILBAO_"
ROUTE_ID = "METRO_BILBAO_MB"


def download_gtfs() -> Dict[str, str]:
    """Download and extract GTFS files."""
    logger.info(f"Downloading GTFS from {GTFS_URL}...")
    response = requests.get(GTFS_URL, timeout=60)
    response.raise_for_status()

    files = {}
    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        for name in zf.namelist():
            if name.endswith('.txt'):
                files[name] = zf.read(name).decode('utf-8')
                logger.info(f"  Extracted {name}: {len(files[name])} bytes")

    return files


def parse_shapes(shapes_content: str) -> Dict[str, List[Tuple[float, float, int]]]:
    """Parse shapes.txt into a dict of shape_id -> [(lat, lon, seq), ...]."""
    shapes = {}
    reader = csv.DictReader(shapes_content.strip().split('\n'))

    for row in reader:
        shape_id = row['shape_id'].strip()
        lat = float(row['shape_pt_lat'].strip())
        lon = float(row['shape_pt_lon'].strip())
        seq = int(row['shape_pt_sequence'].strip())

        if shape_id not in shapes:
            shapes[shape_id] = []
        shapes[shape_id].append((lat, lon, seq))

    # Sort each shape by sequence
    for shape_id in shapes:
        shapes[shape_id].sort(key=lambda x: x[2])

    return shapes


def parse_stops(stops_content: str) -> Tuple[Dict, Dict, Dict]:
    """Parse stops.txt into stations, parents, and accesses."""
    stations = {}  # location_type=0
    parents = {}   # location_type=1
    accesses = {}  # location_type=2

    reader = csv.DictReader(stops_content.strip().split('\n'))

    for row in reader:
        stop_id = row['stop_id'].strip()
        name = row['stop_name'].strip()
        lat = float(row['stop_lat'].strip())
        lon = float(row['stop_lon'].strip())
        location_type = int(row['location_type'].strip()) if row['location_type'].strip() else 0
        parent_station = row['parent_station'].strip() if row.get('parent_station') else None

        stop_data = {
            'id': stop_id,
            'name': name,
            'lat': lat,
            'lon': lon,
            'parent': parent_station
        }

        if location_type == 0:
            stations[stop_id] = stop_data
        elif location_type == 1:
            parents[stop_id] = stop_data
        elif location_type == 2:
            accesses[stop_id] = stop_data

    return stations, parents, accesses


def parse_calendars(calendar_content: str) -> Dict[str, Dict]:
    """Parse calendar.txt."""
    calendars = {}
    reader = csv.DictReader(calendar_content.strip().split('\n'))

    for row in reader:
        service_id = row['service_id'].strip()
        calendars[service_id] = {
            'monday': int(row['monday']),
            'tuesday': int(row['tuesday']),
            'wednesday': int(row['wednesday']),
            'thursday': int(row['thursday']),
            'friday': int(row['friday']),
            'saturday': int(row['saturday']),
            'sunday': int(row['sunday']),
            'start_date': row['start_date'].strip(),
            'end_date': row['end_date'].strip(),
        }

    return calendars


def parse_calendar_dates(calendar_dates_content: str) -> List[Dict]:
    """Parse calendar_dates.txt."""
    dates = []
    reader = csv.DictReader(calendar_dates_content.strip().split('\n'))

    for row in reader:
        dates.append({
            'service_id': row['service_id'].strip(),
            'date': row['date'].strip(),
            'exception_type': int(row['exception_type']),
        })

    return dates


def parse_trips(trips_content: str) -> Dict[str, Dict]:
    """Parse trips.txt."""
    trips = {}
    reader = csv.DictReader(trips_content.strip().split('\n'))

    for row in reader:
        trip_id = row['trip_id'].strip()
        trips[trip_id] = {
            'route_id': row['route_id'].strip(),
            'service_id': row['service_id'].strip(),
            'headsign': row.get('trip_headsign', '').strip(),
            'direction_id': int(row['direction_id']) if row.get('direction_id') else 0,
            'shape_id': row.get('shape_id', '').strip(),
        }

    return trips


def parse_stop_times(stop_times_content: str) -> List[Dict]:
    """Parse stop_times.txt."""
    stop_times = []
    reader = csv.DictReader(stop_times_content.strip().split('\n'))

    for row in reader:
        stop_times.append({
            'trip_id': row['trip_id'].strip(),
            'stop_sequence': int(row['stop_sequence']),
            'arrival_time': row['arrival_time'].strip(),
            'departure_time': row['departure_time'].strip(),
            'stop_id': row['stop_id'].strip(),
        })

    return stop_times


def time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS to seconds from midnight."""
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def import_shapes(conn, shapes: Dict[str, List[Tuple[float, float, int]]], dry_run: bool = False) -> int:
    """Import shapes into database."""
    cur = conn.cursor()

    # Get existing shapes for Metro Bilbao
    cur.execute("SELECT id FROM gtfs_shapes WHERE id LIKE 'METRO_BILBAO_%'")
    existing = {row[0] for row in cur.fetchall()}
    logger.info(f"Existing Metro Bilbao shapes: {len(existing)}")

    imported_shapes = 0
    imported_points = 0

    for shape_id, points in shapes.items():
        full_shape_id = f"METRO_BILBAO_{shape_id}"

        if dry_run:
            logger.info(f"  [DRY-RUN] Would import shape {full_shape_id} with {len(points)} points")
            imported_shapes += 1
            imported_points += len(points)
            continue

        # Delete existing if present
        if full_shape_id in existing:
            cur.execute("DELETE FROM gtfs_shape_points WHERE shape_id = %s", (full_shape_id,))
            cur.execute("DELETE FROM gtfs_shapes WHERE id = %s", (full_shape_id,))

        # Insert shape
        cur.execute(
            "INSERT INTO gtfs_shapes (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
            (full_shape_id,)
        )

        # Insert shape points
        for lat, lon, seq in points:
            cur.execute("""
                INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon)
                VALUES (%s, %s, %s, %s)
            """, (full_shape_id, seq, lat, lon))

        imported_shapes += 1
        imported_points += len(points)

    if not dry_run:
        conn.commit()

    logger.info(f"Imported {imported_shapes} shapes with {imported_points} points")
    return imported_points


def import_accesses(conn, accesses: Dict, parents: Dict, dry_run: bool = False) -> int:
    """Import accesses into stop_access table."""
    cur = conn.cursor()

    # Delete existing Metro Bilbao accesses
    if not dry_run:
        cur.execute("DELETE FROM stop_access WHERE stop_id LIKE 'METRO_BILBAO_%'")
        logger.info("Deleted existing Metro Bilbao accesses")

    imported = 0

    for access_id, access in accesses.items():
        # Map parent station to our stop_id format
        parent_id = access['parent']

        # Find the parent station name
        parent_name = parents.get(parent_id, {}).get('name', 'Unknown')

        # Our stop_id format
        stop_id = f"{STOP_ID_PREFIX}{parent_id}"

        if dry_run:
            imported += 1
            continue

        cur.execute("""
            INSERT INTO stop_access (stop_id, name, lat, lon, source)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            stop_id,
            access['name'],
            access['lat'],
            access['lon'],
            'ctb_gtfs'
        ))
        imported += 1

    if not dry_run:
        conn.commit()

    logger.info(f"Imported {imported} accesses")
    return imported


def import_calendars(conn, calendars: Dict[str, Dict], calendar_dates: List[Dict], dry_run: bool = False) -> int:
    """Import calendars and calendar dates."""
    cur = conn.cursor()

    if not dry_run:
        # Delete existing Metro Bilbao calendars
        cur.execute("DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_BILBAO_%'")
        cur.execute("DELETE FROM gtfs_calendar WHERE service_id LIKE 'METRO_BILBAO_%'")
        logger.info("Deleted existing Metro Bilbao calendars")

    imported = 0

    for service_id, cal in calendars.items():
        full_service_id = f"METRO_BILBAO_{service_id}"

        if dry_run:
            imported += 1
            continue

        # Parse dates
        start_date = datetime.strptime(cal['start_date'], '%Y%m%d').date()
        end_date = datetime.strptime(cal['end_date'], '%Y%m%d').date()

        cur.execute("""
            INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        """, (
            full_service_id,
            bool(cal['monday']), bool(cal['tuesday']), bool(cal['wednesday']),
            bool(cal['thursday']), bool(cal['friday']), bool(cal['saturday']), bool(cal['sunday']),
            start_date, end_date
        ))
        imported += 1

    # Import calendar dates (exceptions) - only for service_ids that exist in calendars
    imported_dates = 0
    skipped_dates = 0
    for cd in calendar_dates:
        # Only import if the service_id exists in our calendars
        if cd['service_id'] not in calendars:
            skipped_dates += 1
            continue

        full_service_id = f"METRO_BILBAO_{cd['service_id']}"
        date = datetime.strptime(cd['date'], '%Y%m%d').date()

        if dry_run:
            imported_dates += 1
            continue

        cur.execute("""
            INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (service_id, date) DO UPDATE SET exception_type = EXCLUDED.exception_type
        """, (full_service_id, date, cd['exception_type']))
        imported_dates += 1

    if skipped_dates > 0:
        logger.info(f"  Skipped {skipped_dates} calendar_dates with missing service_ids")

    if not dry_run:
        conn.commit()

    logger.info(f"Imported {imported} calendars and {imported_dates} exceptions")
    return imported


def get_route_for_headsign(headsign: str) -> str:
    """Map headsign to route ID.

    L1 = Etxebarri - Plentzia
    L2 = Basauri - Kabiezes
    """
    headsign_lower = headsign.lower()

    # L2 headsigns
    if any(h in headsign_lower for h in ['kabiezes', 'basauri', 'ansio', 'barakaldo', 'sestao', 'portugalete', 'santurtzi', 'urbinaga', 'bagatza', 'gurutzeta']):
        return 'METRO_BILBAO_L2'

    # L1 headsigns (default)
    return 'METRO_BILBAO_L1'


def import_trips(conn, trips: Dict[str, Dict], dry_run: bool = False) -> int:
    """Import trips."""
    cur = conn.cursor()

    if not dry_run:
        # Delete existing Metro Bilbao trips
        cur.execute("DELETE FROM gtfs_stop_times WHERE trip_id LIKE 'METRO_BILBAO_%'")
        cur.execute("DELETE FROM gtfs_trips WHERE id LIKE 'METRO_BILBAO_%'")
        logger.info("Deleted existing Metro Bilbao trips")

    imported = 0

    for trip_id, trip in trips.items():
        full_trip_id = f"METRO_BILBAO_{trip_id}"
        full_service_id = f"METRO_BILBAO_{trip['service_id']}"
        full_shape_id = f"METRO_BILBAO_{trip['shape_id']}" if trip['shape_id'] else None

        # Map to correct route based on headsign
        route_id = get_route_for_headsign(trip['headsign'])

        if dry_run:
            imported += 1
            continue

        cur.execute("""
            INSERT INTO gtfs_trips (id, route_id, service_id, headsign, direction_id, shape_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                route_id = EXCLUDED.route_id,
                service_id = EXCLUDED.service_id,
                headsign = EXCLUDED.headsign,
                direction_id = EXCLUDED.direction_id,
                shape_id = EXCLUDED.shape_id
        """, (
            full_trip_id,
            route_id,
            full_service_id,
            trip['headsign'],
            trip['direction_id'],
            full_shape_id
        ))
        imported += 1

        if imported % 1000 == 0:
            logger.info(f"  Imported {imported} trips...")

    if not dry_run:
        conn.commit()

    logger.info(f"Imported {imported} trips")
    return imported


def import_stop_times(conn, stop_times: List[Dict], stations: Dict, dry_run: bool = False) -> int:
    """Import stop times."""
    cur = conn.cursor()

    # Build stop_id mapping (GTFS stop_id -> our stop_id)
    # The GTFS uses stop_ids like "17.0" which should map to "METRO_BILBAO_17"
    stop_id_map = {}
    for gtfs_stop_id, station in stations.items():
        # Extract the numeric part (e.g., "17.0" -> "17")
        numeric_id = gtfs_stop_id.split('.')[0]
        stop_id_map[gtfs_stop_id] = f"{STOP_ID_PREFIX}{numeric_id}"

    imported = 0
    batch = []
    batch_size = 5000

    for st in stop_times:
        full_trip_id = f"METRO_BILBAO_{st['trip_id']}"
        gtfs_stop_id = st['stop_id']

        # Map stop_id
        if gtfs_stop_id in stop_id_map:
            our_stop_id = stop_id_map[gtfs_stop_id]
        else:
            # Try extracting numeric part
            numeric_id = gtfs_stop_id.split('.')[0]
            our_stop_id = f"{STOP_ID_PREFIX}{numeric_id}"

        arrival_seconds = time_to_seconds(st['arrival_time'])
        departure_seconds = time_to_seconds(st['departure_time'])

        if dry_run:
            imported += 1
            continue

        batch.append((
            full_trip_id,
            our_stop_id,
            st['stop_sequence'],
            st['arrival_time'],
            st['departure_time'],
            arrival_seconds,
            departure_seconds
        ))

        if len(batch) >= batch_size:
            cur.executemany("""
                INSERT INTO gtfs_stop_times (trip_id, stop_id, stop_sequence, arrival_time, departure_time, arrival_seconds, departure_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
                    stop_id = EXCLUDED.stop_id,
                    arrival_time = EXCLUDED.arrival_time,
                    departure_time = EXCLUDED.departure_time,
                    arrival_seconds = EXCLUDED.arrival_seconds,
                    departure_seconds = EXCLUDED.departure_seconds
            """, batch)
            conn.commit()
            imported += len(batch)
            logger.info(f"  Imported {imported} stop_times...")
            batch = []

    # Insert remaining
    if batch and not dry_run:
        cur.executemany("""
            INSERT INTO gtfs_stop_times (trip_id, stop_id, stop_sequence, arrival_time, departure_time, arrival_seconds, departure_seconds)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
                stop_id = EXCLUDED.stop_id,
                arrival_time = EXCLUDED.arrival_time,
                departure_time = EXCLUDED.departure_time,
                arrival_seconds = EXCLUDED.arrival_seconds,
                departure_seconds = EXCLUDED.departure_seconds
        """, batch)
        conn.commit()
        imported += len(batch)

    logger.info(f"Imported {imported} stop_times")
    return imported


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import Metro Bilbao data from GTFS')
    parser.add_argument('--dry-run', action='store_true', help='Dry run - do not write to database')
    parser.add_argument('--trips-only', action='store_true', help='Only import trips and stop_times')
    parser.add_argument('--shapes-only', action='store_true', help='Only import shapes and accesses')
    args = parser.parse_args()

    # Download GTFS
    files = download_gtfs()

    # Parse data
    shapes = parse_shapes(files['shapes.txt'])
    logger.info(f"Parsed {len(shapes)} shapes with {sum(len(pts) for pts in shapes.values())} total points")

    stations, parents, accesses = parse_stops(files['stops.txt'])
    logger.info(f"Parsed {len(stations)} stations, {len(parents)} parents, {len(accesses)} accesses")

    calendars = parse_calendars(files['calendar.txt'])
    logger.info(f"Parsed {len(calendars)} calendars")

    calendar_dates = parse_calendar_dates(files['calendar_dates.txt'])
    logger.info(f"Parsed {len(calendar_dates)} calendar exceptions")

    trips = parse_trips(files['trips.txt'])
    logger.info(f"Parsed {len(trips)} trips")

    stop_times = parse_stop_times(files['stop_times.txt'])
    logger.info(f"Parsed {len(stop_times)} stop_times")

    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)

    try:
        if not args.trips_only:
            # Import shapes
            logger.info("\n=== Importing Shapes ===")
            import_shapes(conn, shapes, args.dry_run)

            # Import accesses
            logger.info("\n=== Importing Accesses ===")
            import_accesses(conn, accesses, parents, args.dry_run)

        if not args.shapes_only:
            # Import calendars
            logger.info("\n=== Importing Calendars ===")
            import_calendars(conn, calendars, calendar_dates, args.dry_run)

            # Import trips
            logger.info("\n=== Importing Trips ===")
            import_trips(conn, trips, args.dry_run)

            # Import stop times
            logger.info("\n=== Importing Stop Times ===")
            import_stop_times(conn, stop_times, stations, args.dry_run)

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("METRO BILBAO IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Shapes: {len(shapes)}")
        logger.info(f"Shape points: {sum(len(pts) for pts in shapes.values())}")
        logger.info(f"Accesses: {len(accesses)}")
        logger.info(f"Calendars: {len(calendars)}")
        logger.info(f"Trips: {len(trips)}")
        logger.info(f"Stop times: {len(stop_times)}")

        if args.dry_run:
            logger.info("\n[DRY-RUN] No changes were made to the database")
        else:
            # Verify
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM gtfs_shape_points WHERE shape_id LIKE 'METRO_BILBAO_%'")
            logger.info(f"\nVerification:")
            logger.info(f"  Shape points: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM stop_access WHERE stop_id LIKE 'METRO_BILBAO_%'")
            logger.info(f"  Accesses: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM gtfs_trips WHERE id LIKE 'METRO_BILBAO_%'")
            logger.info(f"  Trips: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'METRO_BILBAO_%'")
            logger.info(f"  Stop times: {cur.fetchone()[0]}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
