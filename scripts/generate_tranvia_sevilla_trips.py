#!/usr/bin/env python3
"""Generate trips for Tranvía Sevilla (Metrocentro) T1 line.

Metrocentro is a short tram line in Seville city center:
- Route: Archivo de Indias <-> Luis de Morales
- 7 stops, ~2 km
- Travel time: ~8 minutes end to end

The route and stops exist in the database but there are NO trips.
This script creates trips based on real schedules from TUSSAM.

Schedule (from tussam.es):
- L-V: 7:00 - 22:30, frequency 5-8 min
- Sábados: 9:00 - 22:30, frequency 7-10 min
- Domingos/Festivos: 9:30 - 22:00, frequency 9-12 min

Usage:
    python scripts/generate_tranvia_sevilla_trips.py
    python scripts/generate_tranvia_sevilla_trips.py --dry-run
    python scripts/generate_tranvia_sevilla_trips.py --analyze
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BATCH_SIZE = 5000
ROUTE_ID = 'TRAM_SEV_T1'

# Stop sequence with travel times (seconds from first stop)
# Direction 0: Archivo de Indias -> Luis de Morales
# Based on ~2km, 8 minutes total, roughly even spacing
STOPS_DIR_0 = [
    ('TRAM_SEV_ARCHIVO_DE_INDIAS', 0),      # Start
    ('TRAM_SEV_PUERTA_JEREZ', 60),          # +1 min
    ('TRAM_SEV_PRADO_SAN_SEBASTIÁN', 150),  # +1.5 min
    ('TRAM_SEV_SAN_BERNARDO', 240),         # +1.5 min
    ('TRAM_SEV_SAN_FRANCISCO_JAVIER', 330), # +1.5 min
    ('TRAM_SEV_EDUARDO_DATO', 420),         # +1.5 min
    ('TRAM_SEV_LUIS_DE_MORALES', 480),      # +1 min (end)
]

# Direction 1: Luis de Morales -> Archivo de Indias (reverse)
STOPS_DIR_1 = [
    ('TRAM_SEV_LUIS_DE_MORALES', 0),
    ('TRAM_SEV_EDUARDO_DATO', 60),
    ('TRAM_SEV_SAN_FRANCISCO_JAVIER', 150),
    ('TRAM_SEV_SAN_BERNARDO', 240),
    ('TRAM_SEV_PRADO_SAN_SEBASTIÁN', 330),
    ('TRAM_SEV_PUERTA_JEREZ', 420),
    ('TRAM_SEV_ARCHIVO_DE_INDIAS', 480),
]

# Service IDs and schedules
SERVICE_IDS = {
    'weekday': 'TRAM_SEV_LABORABLE',
    'saturday': 'TRAM_SEV_SABADO',
    'sunday': 'TRAM_SEV_DOMINGO',
}

SCHEDULES = {
    'weekday': {
        'name': 'Laborables (L-V)',
        'periods': [
            # (start_seconds, end_seconds, headway_seconds)
            (7 * 3600, 9 * 3600, 5 * 60),        # 7:00-9:00 - 5 min (peak)
            (9 * 3600, 13 * 3600, 7 * 60),       # 9:00-13:00 - 7 min
            (13 * 3600, 15 * 3600, 5 * 60),      # 13:00-15:00 - 5 min (peak)
            (15 * 3600, 18 * 3600, 7 * 60),      # 15:00-18:00 - 7 min
            (18 * 3600, 21 * 3600, 5 * 60),      # 18:00-21:00 - 5 min (peak)
            (21 * 3600, 22.5 * 3600, 8 * 60),    # 21:00-22:30 - 8 min
        ],
    },
    'saturday': {
        'name': 'Sábado',
        'periods': [
            (9 * 3600, 14 * 3600, 7 * 60),       # 9:00-14:00 - 7 min
            (14 * 3600, 21 * 3600, 10 * 60),     # 14:00-21:00 - 10 min
            (21 * 3600, 22.5 * 3600, 10 * 60),   # 21:00-22:30 - 10 min
        ],
    },
    'sunday': {
        'name': 'Domingo/Festivo',
        'periods': [
            (9.5 * 3600, 14 * 3600, 10 * 60),    # 9:30-14:00 - 10 min
            (14 * 3600, 21 * 3600, 12 * 60),     # 14:00-21:00 - 12 min
            (21 * 3600, 22 * 3600, 12 * 60),     # 21:00-22:00 - 12 min
        ],
    },
}


def seconds_to_time_str(secs: int) -> str:
    """Convert seconds to HH:MM:SS."""
    secs = int(secs)
    hours = secs // 3600
    mins = (secs % 3600) // 60
    seconds = secs % 60
    return f"{hours:02d}:{mins:02d}:{seconds:02d}"


def verify_stops(db) -> bool:
    """Verify that all required stops exist."""
    result = db.execute(text("""
        SELECT id, name FROM gtfs_stops WHERE id LIKE 'TRAM_SEV%'
    """)).fetchall()

    stops = {row[0]: row[1] for row in result}
    logger.info(f"Found {len(stops)} TRAM_SEV stops")

    # Check all required stops
    required = set(s[0] for s in STOPS_DIR_0)
    missing = required - set(stops.keys())

    if missing:
        logger.error(f"Missing stops: {missing}")
        return False

    for stop_id, name in stops.items():
        logger.info(f"  {stop_id}: {name}")

    return True


def ensure_route_exists(db):
    """Ensure the TRAM_SEV_T1 route exists."""
    result = db.execute(text("""
        SELECT id FROM gtfs_routes WHERE id = :route_id
    """), {'route_id': ROUTE_ID}).fetchone()

    if not result:
        logger.info(f"Creating route {ROUTE_ID}...")
        db.execute(text("""
            INSERT INTO gtfs_routes (id, short_name, long_name, route_type, color, text_color)
            VALUES (:id, 'T1', 'Archivo de Indias - Luis de Morales', 0, 'CC0000', 'FFFFFF')
            ON CONFLICT (id) DO NOTHING
        """), {'id': ROUTE_ID})
        db.commit()
    else:
        logger.info(f"Route {ROUTE_ID} already exists")


def ensure_calendar_entries(db):
    """Ensure calendar entries exist."""
    logger.info("Ensuring calendar entries...")

    calendar_days = {
        'weekday': (True, True, True, True, True, False, False),
        'saturday': (False, False, False, False, False, True, False),
        'sunday': (False, False, False, False, False, False, True),
    }

    for day_type, service_id in SERVICE_IDS.items():
        days = calendar_days[day_type]
        db.execute(text("""
            INSERT INTO gtfs_calendar
            (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
            VALUES (:service_id, :mon, :tue, :wed, :thu, :fri, :sat, :sun, '2025-01-01', '2026-12-31')
            ON CONFLICT (service_id) DO UPDATE SET
                monday = EXCLUDED.monday, tuesday = EXCLUDED.tuesday,
                wednesday = EXCLUDED.wednesday, thursday = EXCLUDED.thursday,
                friday = EXCLUDED.friday, saturday = EXCLUDED.saturday,
                sunday = EXCLUDED.sunday
        """), {
            'service_id': service_id,
            'mon': days[0], 'tue': days[1], 'wed': days[2], 'thu': days[3],
            'fri': days[4], 'sat': days[5], 'sun': days[6],
        })

    db.commit()
    logger.info(f"  Created/updated {len(SERVICE_IDS)} calendar entries")


def analyze_schedule():
    """Analyze and show estimated trip counts."""
    print("\n" + "=" * 70)
    print("TRANVÍA SEVILLA (METROCENTRO) SCHEDULE ANALYSIS")
    print("=" * 70)

    print("\nRoute: TRAM_SEV_T1")
    print("Stops: 7")
    print("Travel time: ~8 minutes")

    print("\nStop sequence (Direction 0 - to Luis de Morales):")
    for i, (stop_id, offset) in enumerate(STOPS_DIR_0, 1):
        name = stop_id.replace('TRAM_SEV_', '').replace('_', ' ')
        print(f"  {i}. {name} (+{offset//60}:{offset%60:02d})")

    print("\nEstimated trips per day type:")
    total_all = 0
    for day_type, schedule in SCHEDULES.items():
        total = 0
        for start, end, headway in schedule['periods']:
            trips_in_period = int((end - start) // headway)
            total += trips_in_period * 2  # 2 directions
        print(f"  {schedule['name']}: ~{total} trips")
        total_all += total

    print(f"\n  TOTAL: ~{total_all} trips")
    print(f"  Estimated stop_times: ~{total_all * 7}")
    print("=" * 70)


def clear_existing_data(db) -> int:
    """Clear existing generated trips."""
    logger.info("Clearing existing Tranvía Sevilla generated trips...")

    result = db.execute(text("""
        DELETE FROM gtfs_stop_times WHERE trip_id LIKE 'TRAM_SEV_GEN_%'
    """))
    db.commit()
    st_deleted = result.rowcount

    result = db.execute(text("""
        DELETE FROM gtfs_trips WHERE id LIKE 'TRAM_SEV_GEN_%'
    """))
    db.commit()
    trips_deleted = result.rowcount

    logger.info(f"  Deleted {trips_deleted} trips, {st_deleted} stop_times")
    return trips_deleted


def generate_trips(db) -> Tuple[int, int]:
    """Generate trips for all schedules."""
    all_trip_rows = []
    all_stop_time_rows = []

    headsigns = {
        0: 'Luis de Morales',
        1: 'Archivo de Indias',
    }
    stop_sequences = {
        0: STOPS_DIR_0,
        1: STOPS_DIR_1,
    }

    for day_type, schedule in SCHEDULES.items():
        service_id = SERVICE_IDS[day_type]
        logger.info(f"Generating trips for {schedule['name']}...")

        for direction in [0, 1]:
            stops = stop_sequences[direction]
            headsign = headsigns[direction]
            trip_num = 0

            for start_secs, end_secs, headway in schedule['periods']:
                current_time = int(start_secs)

                while current_time < int(end_secs):
                    # Create trip ID
                    dir_str = 'A' if direction == 0 else 'B'
                    day_str = day_type[:3].upper()
                    new_trip_id = f"TRAM_SEV_GEN_{day_str}_{dir_str}_{trip_num}"

                    all_trip_rows.append({
                        'id': new_trip_id,
                        'route_id': ROUTE_ID,
                        'service_id': service_id,
                        'headsign': headsign,
                        'direction_id': direction,
                    })

                    # Create stop times
                    for seq, (stop_id, offset) in enumerate(stops, 1):
                        arr_secs = current_time + offset
                        dep_secs = current_time + offset + 20  # 20 sec dwell time

                        all_stop_time_rows.append({
                            'trip_id': new_trip_id,
                            'stop_sequence': seq,
                            'stop_id': stop_id,
                            'arrival_time': seconds_to_time_str(arr_secs),
                            'departure_time': seconds_to_time_str(dep_secs),
                            'arrival_seconds': arr_secs,
                            'departure_seconds': dep_secs,
                        })

                    trip_num += 1
                    current_time += int(headway)

    # Insert trips
    logger.info(f"Inserting {len(all_trip_rows)} trips...")
    for i in range(0, len(all_trip_rows), BATCH_SIZE):
        batch = all_trip_rows[i:i + BATCH_SIZE]
        db.execute(text("""
            INSERT INTO gtfs_trips (id, route_id, service_id, headsign, direction_id)
            VALUES (:id, :route_id, :service_id, :headsign, :direction_id)
            ON CONFLICT (id) DO UPDATE SET
                route_id = EXCLUDED.route_id,
                service_id = EXCLUDED.service_id,
                headsign = EXCLUDED.headsign
        """), batch)
    db.commit()

    # Insert stop_times
    logger.info(f"Inserting {len(all_stop_time_rows)} stop_times...")
    for i in range(0, len(all_stop_time_rows), BATCH_SIZE):
        batch = all_stop_time_rows[i:i + BATCH_SIZE]
        db.execute(text("""
            INSERT INTO gtfs_stop_times
            (trip_id, stop_sequence, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds)
            VALUES (:trip_id, :stop_sequence, :stop_id, :arrival_time, :departure_time, :arrival_seconds, :departure_seconds)
            ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
                stop_id = EXCLUDED.stop_id,
                arrival_seconds = EXCLUDED.arrival_seconds,
                departure_seconds = EXCLUDED.departure_seconds
        """), batch)
    db.commit()

    return len(all_trip_rows), len(all_stop_time_rows)


def main():
    parser = argparse.ArgumentParser(description='Generate Tranvía Sevilla trips')
    parser.add_argument('--analyze', action='store_true', help='Analyze schedule and exit')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()

    if args.analyze or args.dry_run:
        analyze_schedule()
        return

    db = SessionLocal()

    try:
        start_time = datetime.now()

        # Verify stops exist
        if not verify_stops(db):
            logger.error("Cannot proceed - missing stops")
            sys.exit(1)

        # Ensure route and calendars exist
        ensure_route_exists(db)
        ensure_calendar_entries(db)

        # Clear existing and generate
        clear_existing_data(db)
        trips, stop_times = generate_trips(db)

        elapsed = datetime.now() - start_time

        logger.info("\n" + "=" * 60)
        logger.info("TRANVÍA SEVILLA TRIP GENERATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Trips created: {trips:,}")
        logger.info(f"Stop times created: {stop_times:,}")
        logger.info(f"Elapsed time: {elapsed}")
        logger.info("=" * 60)

        # Verify
        result = db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM gtfs_trips WHERE id LIKE 'TRAM_SEV_GEN_%') as trips,
                (SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'TRAM_SEV_GEN_%') as stop_times
        """)).fetchone()
        logger.info(f"Verification: {result[0]:,} trips, {result[1]:,} stop_times")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
