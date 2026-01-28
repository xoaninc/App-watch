#!/usr/bin/env python3
"""Generate trips for Metro Madrid L3.

L3 is not in the CRTM GTFS (was closed for renovation, now reopened).
This script generates trips based on our stop_route_sequence data.

L3 goes from Moncloa to Villaverde Alto (with extension to El Casar).
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# L3 Configuration
ROUTE_ID = 'METRO_3'
BATCH_SIZE = 5000

# Service IDs (same as other Metro Madrid lines)
SERVICE_IDS = {
    'weekday': 'METRO_MAD_LABORABLE',
    'friday': 'METRO_MAD_VIERNES',
    'saturday': 'METRO_MAD_SABADO',
    'sunday': 'METRO_MAD_DOMINGO',
}

# L3 Frequency configuration (similar to other lines)
# Format: (start_hour, end_hour, headway_minutes)
FREQUENCIES = {
    'weekday': [
        (6, 7, 5),      # Early morning: 5 min
        (7, 9, 3),      # Rush hour: 3 min
        (9, 14, 4),     # Midday: 4 min
        (14, 17, 5),    # Afternoon: 5 min
        (17, 21, 3),    # Evening rush: 3 min
        (21, 24, 5),    # Night: 5 min
        (0, 2, 10),     # Late night: 10 min
    ],
    'friday': [
        (6, 7, 5),
        (7, 9, 3),
        (9, 14, 4),
        (14, 17, 5),
        (17, 21, 3),
        (21, 24, 5),
        (0, 2, 10),
    ],
    'saturday': [
        (6, 9, 6),      # Morning: 6 min
        (9, 14, 5),
        (14, 21, 5),
        (21, 24, 6),
        (0, 2, 10),
    ],
    'sunday': [
        (7, 10, 7),     # Morning: 7 min
        (10, 14, 6),
        (14, 21, 6),
        (21, 24, 7),
        (0, 2, 12),
    ],
}

# Average time between stops (seconds) - typical for Metro Madrid
TIME_BETWEEN_STOPS = 120  # 2 minutes
DWELL_TIME = 30  # 30 seconds at each stop


def seconds_to_time_str(secs: int) -> str:
    """Convert seconds to HH:MM:SS."""
    hours = secs // 3600
    mins = (secs % 3600) // 60
    seconds = secs % 60
    return f"{hours:02d}:{mins:02d}:{seconds:02d}"


def get_l3_stops(db) -> List[Dict]:
    """Get L3 stops in correct sequence order."""
    result = db.execute(text('''
        SELECT srs.stop_id, s.name, srs.sequence
        FROM gtfs_stop_route_sequence srs
        JOIN gtfs_stops s ON srs.stop_id = s.id
        WHERE srs.route_id = :route_id
        ORDER BY srs.sequence
    '''), {'route_id': ROUTE_ID}).fetchall()

    stops = []
    for row in result:
        stops.append({
            'stop_id': row[0],
            'name': row[1],
            'sequence': row[2],
        })

    # Fix: Moncloa (sequence=0) should be at the start
    # Currently we have both Argüelles and Moncloa at sequence=0
    # Reorder to put Moncloa first
    moncloa_idx = None
    for i, stop in enumerate(stops):
        if stop['stop_id'] == 'METRO_125':  # Moncloa
            moncloa_idx = i
            break

    if moncloa_idx is not None and moncloa_idx > 0:
        moncloa = stops.pop(moncloa_idx)
        stops.insert(0, moncloa)

    # Reassign sequences
    for i, stop in enumerate(stops):
        stop['sequence'] = i

    return stops


def clear_l3_data(db):
    """Clear existing L3 generated trips."""
    logger.info("Clearing existing L3 data...")

    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id LIKE 'METRO_3_GEN_%'
    """))
    db.commit()
    logger.info(f"  Deleted {result.rowcount} stop_times")

    result = db.execute(text("""
        DELETE FROM gtfs_trips
        WHERE id LIKE 'METRO_3_GEN_%'
    """))
    db.commit()
    logger.info(f"  Deleted {result.rowcount} trips")


def generate_trips(db, stops: List[Dict], dry_run: bool = False):
    """Generate L3 trips for all day types and both directions."""
    all_trips = []
    all_stop_times = []

    # Calculate total travel time
    travel_time = (len(stops) - 1) * (TIME_BETWEEN_STOPS + DWELL_TIME)
    logger.info(f"L3 travel time: {travel_time // 60} minutes ({len(stops)} stops)")

    for day_type, service_id in SERVICE_IDS.items():
        freqs = FREQUENCIES[day_type]

        for direction in [0, 1]:
            # Direction 0: Moncloa -> El Casar
            # Direction 1: El Casar -> Moncloa
            if direction == 1:
                ordered_stops = list(reversed(stops))
                headsign = stops[0]['name']  # Moncloa
            else:
                ordered_stops = stops
                headsign = stops[-1]['name']  # El Casar

            trip_num = 0

            for start_hour, end_hour, headway_min in freqs:
                headway_secs = headway_min * 60

                # Handle overnight periods
                if end_hour <= start_hour:
                    end_hour += 24

                start_secs = start_hour * 3600
                end_secs = end_hour * 3600

                current_time = start_secs
                while current_time < end_secs:
                    trip_id = f"METRO_3_GEN_{day_type[:3]}_{direction}_{trip_num}"

                    all_trips.append({
                        'id': trip_id,
                        'route_id': ROUTE_ID,
                        'service_id': service_id,
                        'headsign': headsign,
                        'direction_id': direction,
                        'wheelchair_accessible': 1,
                    })

                    # Generate stop times
                    stop_offset = 0
                    for seq, stop in enumerate(ordered_stops):
                        arr_secs = current_time + stop_offset
                        dep_secs = arr_secs + DWELL_TIME if seq < len(ordered_stops) - 1 else arr_secs

                        all_stop_times.append({
                            'trip_id': trip_id,
                            'stop_sequence': seq + 1,
                            'stop_id': stop['stop_id'],
                            'arrival_time': seconds_to_time_str(arr_secs),
                            'departure_time': seconds_to_time_str(dep_secs),
                            'arrival_seconds': arr_secs,
                            'departure_seconds': dep_secs,
                            'pickup_type': 0,
                            'drop_off_type': 0,
                            'timepoint': 1,
                        })

                        stop_offset += TIME_BETWEEN_STOPS + DWELL_TIME

                    trip_num += 1
                    current_time += headway_secs

            logger.info(f"  {day_type} direction {direction}: {trip_num} trips")

    logger.info(f"Total: {len(all_trips)} trips, {len(all_stop_times)} stop_times")

    if dry_run:
        logger.info("[DRY RUN - no database changes]")
        return 0, 0

    # Insert trips
    logger.info("Inserting trips...")
    for i in range(0, len(all_trips), BATCH_SIZE):
        batch = all_trips[i:i + BATCH_SIZE]
        db.execute(text("""
            INSERT INTO gtfs_trips
            (id, route_id, service_id, headsign, direction_id, wheelchair_accessible)
            VALUES (:id, :route_id, :service_id, :headsign, :direction_id, :wheelchair_accessible)
            ON CONFLICT (id) DO UPDATE SET
                route_id = EXCLUDED.route_id,
                service_id = EXCLUDED.service_id,
                headsign = EXCLUDED.headsign,
                direction_id = EXCLUDED.direction_id
        """), batch)
    db.commit()

    # Insert stop_times
    logger.info("Inserting stop_times...")
    for i in range(0, len(all_stop_times), BATCH_SIZE):
        batch = all_stop_times[i:i + BATCH_SIZE]
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
        """), batch)
    db.commit()

    return len(all_trips), len(all_stop_times)


def main():
    parser = argparse.ArgumentParser(description='Generate Metro Madrid L3 trips')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        # Get L3 stops
        stops = get_l3_stops(db)
        logger.info(f"L3 has {len(stops)} stops")
        logger.info(f"  From: {stops[0]['name']}")
        logger.info(f"  To: {stops[-1]['name']}")

        if not args.dry_run:
            # Clear existing data
            clear_l3_data(db)

        # Generate trips
        trips, stop_times = generate_trips(db, stops, dry_run=args.dry_run)

        logger.info("=" * 60)
        logger.info("L3 TRIP GENERATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Trips created: {trips:,}")
        logger.info(f"Stop times created: {stop_times:,}")
        logger.info("=" * 60)

    except Exception as e:
        db.rollback()
        logger.error(f"Generation failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
