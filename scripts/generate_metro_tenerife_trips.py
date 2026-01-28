#!/usr/bin/env python3
"""Generate full-day trips for Metro Tenerife based on existing templates.

Metro Tenerife has 12 template trips in the database (2 lines x 2 directions x 3 day types),
but RAPTOR needs individual trips throughout the day.

This script expands the template trips into individual trips for each departure.

Lines:
- L1: Intercambiador <-> La Trinidad (21 stops, 37 min)
- L2: La Cuesta <-> Tíncer (6 stops, 10 min)

Schedule (approximate from official website):
- L-J: 6:00 - 23:00, frequency 7-15 min
- Fri: 6:00 - 01:00, frequency 7-15 min
- Sat: 6:00 - 01:00, frequency 8-15 min
- Sun: 7:00 - 23:00, frequency 10-15 min

Usage:
    python scripts/generate_metro_tenerife_trips.py
    python scripts/generate_metro_tenerife_trips.py --dry-run
    python scripts/generate_metro_tenerife_trips.py --analyze
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

# Service schedules - (start_hour, end_hour, peak_headway_min, offpeak_headway_min)
# Peak hours: 7-9, 13-15, 18-21
SCHEDULES = {
    'METRO_TENERIFE_S1': {  # L-V (Mon-Fri)
        'name': 'Laborables (L-V)',
        'periods': [
            # (start_seconds, end_seconds, headway_seconds)
            (6 * 3600, 7 * 3600, 15 * 60),       # 6:00-7:00 - 15 min
            (7 * 3600, 9 * 3600, 7 * 60),        # 7:00-9:00 - 7 min (peak)
            (9 * 3600, 13 * 3600, 10 * 60),      # 9:00-13:00 - 10 min
            (13 * 3600, 15 * 3600, 7 * 60),      # 13:00-15:00 - 7 min (peak)
            (15 * 3600, 18 * 3600, 10 * 60),     # 15:00-18:00 - 10 min
            (18 * 3600, 21 * 3600, 7 * 60),      # 18:00-21:00 - 7 min (peak)
            (21 * 3600, 23 * 3600, 15 * 60),     # 21:00-23:00 - 15 min
        ],
    },
    'METRO_TENERIFE_S2': {  # Saturday
        'name': 'Sábado',
        'periods': [
            (6 * 3600, 9 * 3600, 15 * 60),       # 6:00-9:00 - 15 min
            (9 * 3600, 14 * 3600, 8 * 60),       # 9:00-14:00 - 8 min
            (14 * 3600, 21 * 3600, 10 * 60),     # 14:00-21:00 - 10 min
            (21 * 3600, 25 * 3600, 15 * 60),     # 21:00-01:00 - 15 min (next day)
        ],
    },
    'METRO_TENERIFE_S3': {  # Sunday
        'name': 'Domingo',
        'periods': [
            (7 * 3600, 10 * 3600, 15 * 60),      # 7:00-10:00 - 15 min
            (10 * 3600, 14 * 3600, 10 * 60),     # 10:00-14:00 - 10 min
            (14 * 3600, 21 * 3600, 12 * 60),     # 14:00-21:00 - 12 min
            (21 * 3600, 23 * 3600, 15 * 60),     # 21:00-23:00 - 15 min
        ],
    },
}

# Template trips mapping: (service_id, direction) -> template_trip_id
TEMPLATE_TRIPS = {
    # L1: Intercambiador -> Trinidad
    ('METRO_TENERIFE_S1', 'L1', 0): 'METRO_TENERIFE_IT',    # L-V, L1, to Trinidad
    ('METRO_TENERIFE_S2', 'L1', 0): 'METRO_TENERIFE_ITSA',  # Sab, L1, to Trinidad
    ('METRO_TENERIFE_S3', 'L1', 0): 'METRO_TENERIFE_ITDO',  # Dom, L1, to Trinidad
    # L1: Trinidad -> Intercambiador
    ('METRO_TENERIFE_S1', 'L1', 1): 'METRO_TENERIFE_TI',    # L-V, L1, to Intercambiador
    ('METRO_TENERIFE_S2', 'L1', 1): 'METRO_TENERIFE_TISA',  # Sab, L1, to Intercambiador
    ('METRO_TENERIFE_S3', 'L1', 1): 'METRO_TENERIFE_TIDO',  # Dom, L1, to Intercambiador
    # L2: La Cuesta -> Tíncer
    ('METRO_TENERIFE_S1', 'L2', 0): 'METRO_TENERIFE_LT',    # L-V, L2, to Tincer
    ('METRO_TENERIFE_S2', 'L2', 0): 'METRO_TENERIFE_LTSA',  # Sab, L2, to Tincer
    ('METRO_TENERIFE_S3', 'L2', 0): 'METRO_TENERIFE_LTDO',  # Dom, L2, to Tincer
    # L2: Tíncer -> La Cuesta
    ('METRO_TENERIFE_S1', 'L2', 1): 'METRO_TENERIFE_TL',    # L-V, L2, to La Cuesta
    ('METRO_TENERIFE_S2', 'L2', 1): 'METRO_TENERIFE_TLSA',  # Sab, L2, to La Cuesta
    ('METRO_TENERIFE_S3', 'L2', 1): 'METRO_TENERIFE_TLDO',  # Dom, L2, to La Cuesta
}


def seconds_to_time_str(secs: int) -> str:
    """Convert seconds to HH:MM:SS (handles >24h for GTFS)."""
    hours = secs // 3600
    mins = (secs % 3600) // 60
    seconds = secs % 60
    return f"{hours:02d}:{mins:02d}:{seconds:02d}"


def get_template_stop_times(db, template_trip_id: str) -> List[Dict]:
    """Get stop times for a template trip and calculate offsets."""
    result = db.execute(text("""
        SELECT stop_sequence, stop_id, arrival_seconds, departure_seconds
        FROM gtfs_stop_times
        WHERE trip_id = :trip_id
        ORDER BY stop_sequence
    """), {'trip_id': template_trip_id}).fetchall()

    if not result:
        return []

    first_departure = result[0][3]  # departure_seconds of first stop

    stop_times = []
    for row in result:
        stop_times.append({
            'stop_sequence': row[0],
            'stop_id': row[1],
            'arrival_offset': row[2] - first_departure,
            'departure_offset': row[3] - first_departure,
        })

    return stop_times


def get_trip_info(db, template_trip_id: str) -> Dict:
    """Get trip info (route_id, headsign) from template."""
    result = db.execute(text("""
        SELECT route_id, headsign FROM gtfs_trips WHERE id = :trip_id
    """), {'trip_id': template_trip_id}).fetchone()

    if result:
        return {'route_id': result[0], 'headsign': result[1]}
    return {'route_id': 'METRO_TENERIFE_L1', 'headsign': ''}


def analyze_templates(db):
    """Analyze existing template trips."""
    print("\n" + "=" * 70)
    print("METRO TENERIFE TEMPLATE ANALYSIS")
    print("=" * 70)

    result = db.execute(text("""
        SELECT t.id, t.route_id, t.headsign, t.service_id, COUNT(st.trip_id) as stops
        FROM gtfs_trips t
        LEFT JOIN gtfs_stop_times st ON st.trip_id = t.id
        WHERE t.route_id LIKE 'METRO_TENERIFE%'
        GROUP BY t.id, t.route_id, t.headsign, t.service_id
        ORDER BY t.route_id, t.service_id
    """)).fetchall()

    print(f"\nExisting template trips: {len(result)}")
    for row in result:
        print(f"  {row[0]}: {row[1]} -> {row[2]} ({row[3]}) - {row[4]} stops")

    # Estimate trips to generate
    print("\nEstimated trips to generate per service:")
    total_all = 0
    for service_id, schedule in SCHEDULES.items():
        total = 0
        for start, end, headway in schedule['periods']:
            trips_in_period = (end - start) // headway
            total += trips_in_period * 2 * 2  # 2 directions x 2 lines
        print(f"  {schedule['name']}: ~{total} trips")
        total_all += total

    print(f"\n  TOTAL: ~{total_all} trips")
    print(f"  Estimated stop_times: ~{total_all * 14} avg (21 L1 + 6 L2) / 2")
    print("=" * 70)


def clear_existing_data(db) -> int:
    """Clear existing generated trips."""
    logger.info("Clearing existing generated Metro Tenerife trips...")

    result = db.execute(text("""
        DELETE FROM gtfs_stop_times WHERE trip_id LIKE 'METRO_TEN_GEN_%'
    """))
    db.commit()
    st_deleted = result.rowcount

    result = db.execute(text("""
        DELETE FROM gtfs_trips WHERE id LIKE 'METRO_TEN_GEN_%'
    """))
    db.commit()
    trips_deleted = result.rowcount

    logger.info(f"  Deleted {trips_deleted} trips, {st_deleted} stop_times")
    return trips_deleted


def generate_trips(db) -> Tuple[int, int]:
    """Generate individual trips from templates."""
    all_trip_rows = []
    all_stop_time_rows = []

    # Cache template data
    template_cache = {}
    trip_info_cache = {}

    for (service_id, line, direction), template_id in TEMPLATE_TRIPS.items():
        stop_times = get_template_stop_times(db, template_id)
        if stop_times:
            template_cache[(service_id, line, direction)] = stop_times
            trip_info_cache[(service_id, line, direction)] = get_trip_info(db, template_id)

    logger.info(f"Loaded {len(template_cache)} templates")

    # Generate trips for each service
    for service_id, schedule in SCHEDULES.items():
        logger.info(f"Generating trips for {schedule['name']}...")

        for line in ['L1', 'L2']:
            for direction in [0, 1]:
                key = (service_id, line, direction)
                if key not in template_cache:
                    logger.warning(f"  No template for {key}")
                    continue

                stop_times_template = template_cache[key]
                trip_info = trip_info_cache[key]
                trip_num = 0

                for start_secs, end_secs, headway in schedule['periods']:
                    current_time = start_secs

                    while current_time < end_secs:
                        # Create trip ID
                        dir_str = 'A' if direction == 0 else 'B'
                        new_trip_id = f"METRO_TEN_GEN_{line}_{dir_str}_{service_id[-2:]}_{trip_num}"

                        all_trip_rows.append({
                            'id': new_trip_id,
                            'route_id': trip_info['route_id'],
                            'service_id': service_id,
                            'headsign': trip_info['headsign'],
                            'direction_id': direction,
                        })

                        # Create stop times
                        for st in stop_times_template:
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
                            })

                        trip_num += 1
                        current_time += headway

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
    parser = argparse.ArgumentParser(description='Generate Metro Tenerife trips')
    parser.add_argument('--analyze', action='store_true', help='Analyze templates and exit')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.analyze or args.dry_run:
            analyze_templates(db)
            return

        start_time = datetime.now()

        clear_existing_data(db)
        trips, stop_times = generate_trips(db)

        elapsed = datetime.now() - start_time

        logger.info("\n" + "=" * 60)
        logger.info("METRO TENERIFE TRIP GENERATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Trips created: {trips:,}")
        logger.info(f"Stop times created: {stop_times:,}")
        logger.info(f"Elapsed time: {elapsed}")
        logger.info("=" * 60)

        # Verify
        result = db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM gtfs_trips WHERE id LIKE 'METRO_TEN_GEN_%') as trips,
                (SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'METRO_TEN_GEN_%') as stop_times
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
