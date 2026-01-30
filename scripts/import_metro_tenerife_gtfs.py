#!/usr/bin/env python3
"""Import and expand GTFS data for Metro de Tenerife.

This script:
1. Expands frequencies.txt into individual trips
2. Generates stop_times for each expanded trip
3. Imports shapes from GTFS
4. Imports transfers (L1↔L2 at El Cardonal and Hospital Universitario)
5. Adds calendar_dates for Canarias holidays 2026

The GTFS uses frequencies.txt instead of individual trips.
This script expands ~12 base trips with ~60 frequency entries into
~2,000 individual trips with ~31,000 stop_times.

Usage:
    python scripts/import_metro_tenerife_gtfs.py /tmp/gtfs_metro_tenerife
    python scripts/import_metro_tenerife_gtfs.py /tmp/gtfs_metro_tenerife --dry-run
    python scripts/import_metro_tenerife_gtfs.py /tmp/gtfs_metro_tenerife --analyze

GTFS Source: https://metrotenerife.com/transit/google_transit.zip
"""

import sys
import os
import csv
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BATCH_SIZE = 5000

# Metro Tenerife configuration
PREFIX = 'METRO_TENERIFE_'
NETWORK_ID = 'METRO_TENERIFE'

# Route IDs in our DB
ROUTE_L1 = 'METRO_TENERIFE_L1'
ROUTE_L2 = 'METRO_TENERIFE_L2'

# Shape IDs (new)
SHAPE_L1_INT_TRI = 'METRO_TENERIFE_L1_INT_TRI'  # Intercambiador -> Trinidad
SHAPE_L1_TRI_INT = 'METRO_TENERIFE_L1_TRI_INT'  # Trinidad -> Intercambiador
SHAPE_L2_CUE_TIN = 'METRO_TENERIFE_L2_CUE_TIN'  # La Cuesta -> Tincer
SHAPE_L2_TIN_CUE = 'METRO_TENERIFE_L2_TIN_CUE'  # Tincer -> La Cuesta

# Map GTFS shape_id to our shape_id
GTFS_SHAPE_MAP = {
    'Shape1': SHAPE_L1_INT_TRI,
    'Shape2': SHAPE_L1_TRI_INT,
    'Shape3': SHAPE_L2_CUE_TIN,
    'Shape4': SHAPE_L2_TIN_CUE,
}

# Map GTFS route_id to our route_id
GTFS_ROUTE_MAP = {
    'L1': ROUTE_L1,
    'L2': ROUTE_L2,
}

# Festivos Canarias 2026
FESTIVOS_2026 = [
    ('2026-01-01', 'Ano Nuevo'),
    ('2026-01-06', 'Reyes'),
    ('2026-02-02', 'Dia de la Candelaria'),  # Autonomico Canarias
    ('2026-04-02', 'Jueves Santo'),
    ('2026-04-03', 'Viernes Santo'),
    ('2026-05-01', 'Dia del Trabajo'),
    ('2026-05-30', 'Dia de Canarias'),  # Autonomico Canarias
    ('2026-08-15', 'Asuncion'),
    ('2026-10-12', 'Fiesta Nacional'),
    ('2026-11-01', 'Todos los Santos'),
    ('2026-12-06', 'Constitucion'),
    ('2026-12-08', 'Inmaculada'),
    ('2026-12-25', 'Navidad'),
]


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
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def map_stop_id(gtfs_stop_id: str) -> str:
    """Map GTFS stop_id (01, 02, etc.) to our stop_id (METRO_TENERIFE_01, etc.)."""
    # GTFS uses 01, 02, ..., 26 (no 25)
    return f"{PREFIX}{gtfs_stop_id.zfill(2)}"


def load_csv(directory: str, filename: str) -> List[Dict]:
    """Load a CSV file from the GTFS directory."""
    filepath = os.path.join(directory, filename)
    if not os.path.exists(filepath):
        return []

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        return [row for row in reader]


def load_stop_times_templates(directory: str) -> Dict[str, List[Tuple[str, int, int]]]:
    """Load base stop_times and compute time offsets from first stop.

    Returns dict mapping trip_id -> [(stop_id, stop_sequence, offset_seconds), ...]
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
        result[trip_id] = [(stop_id, seq, arr_secs - first_time) for stop_id, seq, arr_secs in stops]

    return result


def load_trips_info(directory: str) -> Dict[str, Dict]:
    """Load trip information (route_id, service_id, direction, headsign, shape_id)."""
    rows = load_csv(directory, 'trips.txt')

    trips = {}
    for row in rows:
        trip_id = row['trip_id'].strip()
        trips[trip_id] = {
            'route_id': row['route_id'].strip(),
            'service_id': row['service_id'].strip(),
            'direction_id': int(row.get('direction_id', '0').strip() or '0'),
            'headsign': row.get('trip_headsign', '').strip(),
            'shape_id': row.get('shape_id', '').strip(),
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


def load_shapes(directory: str) -> Dict[str, List[Tuple[float, float, int]]]:
    """Load shapes.txt and return dict of shape_id -> [(lat, lon, sequence), ...]."""
    rows = load_csv(directory, 'shapes.txt')

    shapes = defaultdict(list)
    for row in rows:
        shape_id = row['shape_id'].strip()
        lat = float(row['shape_pt_lat'].strip())
        lon = float(row['shape_pt_lon'].strip())
        seq = int(row['shape_pt_sequence'].strip())
        shapes[shape_id].append((lat, lon, seq))

    # Sort by sequence
    for shape_id in shapes:
        shapes[shape_id].sort(key=lambda x: x[2])

    return shapes


def load_transfers(directory: str) -> List[Dict]:
    """Load transfers.txt."""
    rows = load_csv(directory, 'transfers.txt')

    transfers = []
    for row in rows:
        from_stop = row.get('from_stop_id', '').strip()
        to_stop = row.get('to_stop_id', '').strip()
        if from_stop and to_stop:
            transfers.append({
                'from_stop_id': from_stop,
                'to_stop_id': to_stop,
                'transfer_type': int(row.get('transfer_type', '0').strip() or '0'),
            })

    return transfers


def expand_frequencies(
    frequencies: List[Dict],
    trips_info: Dict[str, Dict],
    stop_times_templates: Dict[str, List[Tuple[str, int, int]]]
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

        # Map route_id and shape_id
        our_route_id = GTFS_ROUTE_MAP.get(trip_info['route_id'], trip_info['route_id'])
        our_service_id = f"{PREFIX}{trip_info['service_id']}"
        gtfs_shape_id = trip_info['shape_id']
        our_shape_id = GTFS_SHAPE_MAP.get(gtfs_shape_id, None)

        # Generate trips at each headway interval
        current_time = start_time
        while current_time < end_time:
            trip_counter[base_trip_id] += 1
            trip_num = trip_counter[base_trip_id]

            # Create unique trip_id
            new_trip_id = f"{PREFIX}{base_trip_id}_{trip_num:04d}"

            expanded_trips.append({
                'id': new_trip_id,
                'route_id': our_route_id,
                'service_id': our_service_id,
                'headsign': trip_info['headsign'],
                'short_name': None,
                'direction_id': trip_info['direction_id'],
                'block_id': None,
                'shape_id': our_shape_id,
                'wheelchair_accessible': 1,
                'bikes_allowed': 1,
            })

            # Generate stop_times with offset from current_time
            for gtfs_stop_id, seq, offset_secs in template:
                our_stop_id = map_stop_id(gtfs_stop_id)

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


def verify_stops_exist(db) -> Dict[str, str]:
    """Verify our Metro Tenerife stops exist."""
    result = db.execute(text(
        "SELECT id, name FROM gtfs_stops WHERE id LIKE 'METRO_TENERIFE_%'"
    )).fetchall()

    stops = {row[0]: row[1] for row in result}
    logger.info(f"Found {len(stops)} METRO_TENERIFE stops in database")

    return stops


def verify_routes_exist(db) -> bool:
    """Verify Metro Tenerife routes exist."""
    result = db.execute(text(
        "SELECT id, short_name FROM gtfs_routes WHERE id LIKE 'METRO_TENERIFE_%'"
    )).fetchall()

    if len(result) < 2:
        logger.error(f"Expected 2 routes, found {len(result)}")
        return False

    for row in result:
        logger.info(f"Found route: {row[0]} ({row[1]})")

    return True


def clear_existing_data(db):
    """Clear existing Metro Tenerife trips, stop_times, and shapes."""
    logger.info("Clearing existing Metro Tenerife schedule data...")

    # Delete stop_times
    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id IN (
            SELECT id FROM gtfs_trips WHERE route_id LIKE 'METRO_TENERIFE_%'
        )
    """))
    db.commit()
    logger.info(f"  Cleared {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id LIKE 'METRO_TENERIFE_%'"
    ))
    db.commit()
    logger.info(f"  Cleared {result.rowcount} trips")

    # Delete shape points first (FK constraint)
    result = db.execute(text(
        "DELETE FROM gtfs_shape_points WHERE shape_id LIKE 'METRO_TENERIFE_%'"
    ))
    db.commit()
    logger.info(f"  Cleared {result.rowcount} shape points")

    # Delete shapes
    result = db.execute(text(
        "DELETE FROM gtfs_shapes WHERE id LIKE 'METRO_TENERIFE_%'"
    ))
    db.commit()
    logger.info(f"  Cleared {result.rowcount} shapes")

    # Delete transfers (if table exists)
    try:
        result = db.execute(text("""
            DELETE FROM gtfs_transfers
            WHERE from_stop_id LIKE 'METRO_TENERIFE_%'
               OR to_stop_id LIKE 'METRO_TENERIFE_%'
        """))
        db.commit()
        logger.info(f"  Cleared {result.rowcount} transfers")
    except Exception:
        db.rollback()
        logger.info("  Transfers table does not exist, skipping")


def import_shapes(db, shapes: Dict[str, List[Tuple[float, float, int]]]) -> int:
    """Import shapes with our naming convention.

    Uses two tables:
    - gtfs_shapes: Contains shape IDs
    - gtfs_shape_points: Contains the actual points (shape_id, sequence, lat, lon)
    """
    logger.info("Importing shapes...")

    shape_ids = []
    shape_points = []

    for gtfs_shape_id, points in shapes.items():
        our_shape_id = GTFS_SHAPE_MAP.get(gtfs_shape_id)
        if not our_shape_id:
            logger.warning(f"Unknown shape_id: {gtfs_shape_id}")
            continue

        shape_ids.append({'id': our_shape_id})

        for lat, lon, seq in points:
            shape_points.append({
                'shape_id': our_shape_id,
                'sequence': seq,
                'lat': lat,
                'lon': lon,
                'dist_traveled': None,
            })

    # Insert shape IDs
    if shape_ids:
        for shape in shape_ids:
            db.execute(
                text("""
                    INSERT INTO gtfs_shapes (id)
                    VALUES (:id)
                    ON CONFLICT (id) DO NOTHING
                """),
                shape
            )
        db.commit()

    # Insert shape points
    if shape_points:
        for i in range(0, len(shape_points), BATCH_SIZE):
            batch = shape_points[i:i+BATCH_SIZE]
            db.execute(
                text("""
                    INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon, dist_traveled)
                    VALUES (:shape_id, :sequence, :lat, :lon, :dist_traveled)
                """),
                batch
            )
        db.commit()

    logger.info(f"  Imported {len(shape_ids)} shapes with {len(shape_points)} points")
    return len(shape_points)


def import_transfers(db, transfers: List[Dict]) -> int:
    """Import transfers with our stop_id mapping."""
    logger.info("Importing transfers...")

    transfer_rows = []
    for t in transfers:
        from_stop = map_stop_id(t['from_stop_id'])
        to_stop = map_stop_id(t['to_stop_id'])

        transfer_rows.append({
            'from_stop_id': from_stop,
            'to_stop_id': to_stop,
            'transfer_type': t['transfer_type'],
            'min_transfer_time': 60,  # 1 minute default
        })

    if transfer_rows:
        try:
            db.execute(
                text("""
                    INSERT INTO gtfs_transfers (from_stop_id, to_stop_id, transfer_type, min_transfer_time)
                    VALUES (:from_stop_id, :to_stop_id, :transfer_type, :min_transfer_time)
                    ON CONFLICT (from_stop_id, to_stop_id) DO UPDATE SET
                        transfer_type = EXCLUDED.transfer_type,
                        min_transfer_time = EXCLUDED.min_transfer_time
                """),
                transfer_rows
            )
            db.commit()
            logger.info(f"  Imported {len(transfer_rows)} transfers")
            return len(transfer_rows)
        except Exception as e:
            db.rollback()
            logger.warning(f"  Could not import transfers (table may not exist): {e}")
            return 0

    return 0


def import_calendar_dates(db) -> int:
    """Add calendar_dates for Canarias holidays 2026."""
    logger.info("Adding calendar_dates for festivos...")

    # Delete existing
    db.execute(text("DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_TENERIFE_%'"))
    db.commit()

    calendar_dates = []
    for fecha, nombre in FESTIVOS_2026:
        # On festivos, use S3 (domingo) service instead of S1 (laborable)
        # Add S3 service
        calendar_dates.append({
            'service_id': f'{PREFIX}S3',
            'date': fecha,
            'exception_type': 1,  # Service added
        })
        # Remove S1 service
        calendar_dates.append({
            'service_id': f'{PREFIX}S1',
            'date': fecha,
            'exception_type': 2,  # Service removed
        })

    if calendar_dates:
        db.execute(
            text("""
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :date, :exception_type)
                ON CONFLICT (service_id, date) DO UPDATE SET
                    exception_type = EXCLUDED.exception_type
            """),
            calendar_dates
        )
        db.commit()

    logger.info(f"  Added {len(calendar_dates)} calendar_dates for {len(FESTIVOS_2026)} festivos")
    return len(calendar_dates)


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
            """),
            batch
        )

        if (i + BATCH_SIZE) % 5000 == 0 or i + BATCH_SIZE >= len(trips):
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
    print("METRO TENERIFE GTFS ANALYSIS")
    print("=" * 70)

    # Trips
    trips_info = load_trips_info(directory)
    print(f"\nBase trips: {len(trips_info)}")
    for trip_id, info in trips_info.items():
        print(f"  {trip_id}: {info['route_id']} -> {info['headsign']} ({info['service_id']})")

    # Frequencies
    frequencies = load_frequencies(directory)
    print(f"\nFrequency entries: {len(frequencies)}")

    # Stop times templates
    templates = load_stop_times_templates(directory)
    print(f"\nStop times templates: {len(templates)} base trips")
    for trip_id, stops in templates.items():
        print(f"  {trip_id}: {len(stops)} stops, {stops[-1][2]//60} min total")

    # Shapes
    shapes = load_shapes(directory)
    print(f"\nShapes: {len(shapes)}")
    for shape_id, points in shapes.items():
        print(f"  {shape_id}: {len(points)} points")

    # Transfers
    transfers = load_transfers(directory)
    print(f"\nTransfers: {len(transfers)}")
    for t in transfers:
        print(f"  {t['from_stop_id']} -> {t['to_stop_id']} (type {t['transfer_type']})")

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

    # By route
    print("\n" + "-" * 70)
    print("TRIPS BY ROUTE (estimated)")
    print("-" * 70)

    by_route = defaultdict(int)
    for freq in frequencies:
        base_trip_id = freq['trip_id']
        if base_trip_id not in trips_info:
            continue

        route_id = trips_info[base_trip_id]['route_id']

        start_time = freq['start_time']
        end_time = freq['end_time']
        headway_secs = freq['headway_secs']

        num_trips = 0
        current_time = start_time
        while current_time < end_time:
            num_trips += 1
            current_time += headway_secs

        by_route[route_id] += num_trips

    for route_id in sorted(by_route.keys()):
        print(f"  {route_id}: {by_route[route_id]:,} trips")

    # Festivos
    print("\n" + "-" * 70)
    print("FESTIVOS CANARIAS 2026")
    print("-" * 70)

    for fecha, nombre in FESTIVOS_2026:
        print(f"  {fecha}: {nombre}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Import and expand GTFS data for Metro de Tenerife'
    )
    parser.add_argument('gtfs_dir', help='Path to GTFS directory (e.g., /tmp/gtfs_metro_tenerife)')
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

    shapes = load_shapes(args.gtfs_dir)
    logger.info(f"Loaded {len(shapes)} shapes")

    transfers = load_transfers(args.gtfs_dir)
    logger.info(f"Loaded {len(transfers)} transfers")

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
        for trip in expanded_trips[:10]:
            print(f"  {trip['id']}: {trip['route_id']} -> {trip['headsign']} ({trip['service_id']})")

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
        if not verify_routes_exist(db):
            sys.exit(1)

        our_stops = verify_stops_exist(db)
        if not our_stops:
            logger.error("No METRO_TENERIFE stops found! Import stops first.")
            sys.exit(1)

        # Clear existing data
        clear_existing_data(db)

        # Import shapes
        shape_count = import_shapes(db, shapes)
        logger.info(f"Imported {shape_count} shape points")

        # Import transfers
        transfer_count = import_transfers(db, transfers)
        logger.info(f"Imported {transfer_count} transfers")

        # Import calendar_dates for festivos
        calendar_dates_count = import_calendar_dates(db)
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
        print("IMPORT SUMMARY - Metro de Tenerife")
        print("=" * 70)
        print(f"Shapes: {shape_count} points")
        print(f"Transfers: {transfer_count}")
        print(f"Calendar dates: {calendar_dates_count}")
        print(f"Trips: {trips_count:,}")
        print(f"Stop times: {stop_times_count:,}")
        print(f"Elapsed time: {elapsed}")
        print("=" * 70)
        print("\nMetro Tenerife GTFS import completed successfully!")
        print("\nNext steps:")
        print("  1. Restart the server to reload GTFSStore")
        print("  2. Verify with: SELECT COUNT(*) FROM gtfs_trips WHERE route_id LIKE 'METRO_TENERIFE%';")
        print("  3. Test departures: curl 'http://localhost:8002/api/v1/gtfs/stops/METRO_TENERIFE_01/departures?limit=5'")

    except Exception as e:
        db.rollback()
        logger.error(f"Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
