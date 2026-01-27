#!/usr/bin/env python3
"""Generate trips and stop_times for Metro Madrid using existing data.

This script uses data already in the database:
- gtfs_stops (242 Metro Madrid stations)
- gtfs_routes (16 lines)
- gtfs_stop_route_sequence (stop order per line)
- gtfs_route_frequencies (service frequencies)

It generates:
- gtfs_calendar (service definitions)
- gtfs_trips (one per route/direction/service)
- gtfs_stop_times (based on stop sequence with ~2min between stations)

Usage:
    python scripts/generate_metro_madrid_trips.py [--dry-run]
"""

import argparse
import logging
from datetime import date
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Average time between Metro Madrid stations (seconds)
AVG_STATION_TIME = 120  # 2 minutes

# Metro Madrid route prefixes to process
METRO_ROUTES = [
    'METRO_1', 'METRO_2', 'METRO_3', 'METRO_4', 'METRO_5', 'METRO_6',
    'METRO_7', 'METRO_7B', 'METRO_8', 'METRO_9', 'METRO_9B',
    'METRO_10', 'METRO_10B', 'METRO_11', 'METRO_12', 'METRO_R'
]

# Service types to create
SERVICE_TYPES = [
    {'id': 'METRO_MAD_LABORABLE', 'days': [True, True, True, True, False, False, False]},  # Mon-Thu
    {'id': 'METRO_MAD_VIERNES', 'days': [False, False, False, False, True, False, False]},  # Fri
    {'id': 'METRO_MAD_SABADO', 'days': [False, False, False, False, False, True, False]},   # Sat
    {'id': 'METRO_MAD_DOMINGO', 'days': [False, False, False, False, False, False, True]},  # Sun
]


def get_route_stops(db, route_id: str) -> list:
    """Get ordered stops for a route from stop_route_sequence."""
    result = db.execute(text("""
        SELECT stop_id, sequence
        FROM gtfs_stop_route_sequence
        WHERE route_id = :route_id
        ORDER BY sequence
    """), {'route_id': route_id}).fetchall()
    return [row[0] for row in result]


def get_route_headsigns(db, route_id: str) -> tuple:
    """Get headsigns for both directions (first and last stop names)."""
    stops = get_route_stops(db, route_id)
    if not stops:
        return None, None

    first = db.execute(text("SELECT name FROM gtfs_stops WHERE id = :id"),
                       {'id': stops[0]}).fetchone()
    last = db.execute(text("SELECT name FROM gtfs_stops WHERE id = :id"),
                      {'id': stops[-1]}).fetchone()

    return (last[0] if last else None, first[0] if first else None)


def create_calendar_entries(db, dry_run: bool) -> int:
    """Create calendar entries for Metro Madrid services."""
    logger.info("Creating calendar entries...")

    rows = []
    for service in SERVICE_TYPES:
        rows.append({
            'service_id': service['id'],
            'monday': service['days'][0],
            'tuesday': service['days'][1],
            'wednesday': service['days'][2],
            'thursday': service['days'][3],
            'friday': service['days'][4],
            'saturday': service['days'][5],
            'sunday': service['days'][6],
            'start_date': '2025-01-01',
            'end_date': '2026-12-31',
        })

    if dry_run:
        logger.info(f"  Would create {len(rows)} calendar entries")
        return len(rows)

    db.execute(text("""
        INSERT INTO gtfs_calendar
        (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
        VALUES (:service_id, :monday, :tuesday, :wednesday, :thursday, :friday, :saturday, :sunday, :start_date, :end_date)
        ON CONFLICT (service_id) DO UPDATE SET
            monday = EXCLUDED.monday, tuesday = EXCLUDED.tuesday, wednesday = EXCLUDED.wednesday,
            thursday = EXCLUDED.thursday, friday = EXCLUDED.friday, saturday = EXCLUDED.saturday,
            sunday = EXCLUDED.sunday, start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date
    """), rows)
    db.commit()

    return len(rows)


def create_trips_and_stop_times(db, dry_run: bool) -> tuple:
    """Create trips and stop_times for all Metro Madrid routes."""
    logger.info("Creating trips and stop_times...")

    total_trips = 0
    total_stop_times = 0

    for route_id in METRO_ROUTES:
        stops = get_route_stops(db, route_id)
        if not stops:
            logger.warning(f"  No stops found for {route_id}, skipping")
            continue

        headsign_0, headsign_1 = get_route_headsigns(db, route_id)

        for service in SERVICE_TYPES:
            for direction in [0, 1]:
                # Create trip
                trip_id = f"{route_id}_{service['id']}_{direction}"
                headsign = headsign_0 if direction == 0 else headsign_1

                trip_data = {
                    'id': trip_id,
                    'route_id': route_id,
                    'service_id': service['id'],
                    'headsign': headsign,
                    'direction_id': direction,
                }

                if not dry_run:
                    db.execute(text("""
                        INSERT INTO gtfs_trips (id, route_id, service_id, headsign, direction_id)
                        VALUES (:id, :route_id, :service_id, :headsign, :direction_id)
                        ON CONFLICT (id) DO UPDATE SET
                            route_id = EXCLUDED.route_id, service_id = EXCLUDED.service_id,
                            headsign = EXCLUDED.headsign, direction_id = EXCLUDED.direction_id
                    """), trip_data)

                total_trips += 1

                # Create stop_times
                stop_list = stops if direction == 0 else list(reversed(stops))
                base_time = 6 * 3600 + 5 * 60  # 06:05:00 (first train)

                for seq, stop_id in enumerate(stop_list):
                    arrival_seconds = base_time + (seq * AVG_STATION_TIME)
                    departure_seconds = arrival_seconds + 30  # 30 sec dwell time

                    arrival_time = f"{arrival_seconds // 3600}:{(arrival_seconds % 3600) // 60:02d}:{arrival_seconds % 60:02d}"
                    departure_time = f"{departure_seconds // 3600}:{(departure_seconds % 3600) // 60:02d}:{departure_seconds % 60:02d}"

                    stop_time_data = {
                        'trip_id': trip_id,
                        'stop_sequence': seq,
                        'stop_id': stop_id,
                        'arrival_time': arrival_time,
                        'departure_time': departure_time,
                        'arrival_seconds': arrival_seconds,
                        'departure_seconds': departure_seconds,
                    }

                    if not dry_run:
                        db.execute(text("""
                            INSERT INTO gtfs_stop_times
                            (trip_id, stop_sequence, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds)
                            VALUES (:trip_id, :stop_sequence, :stop_id, :arrival_time, :departure_time, :arrival_seconds, :departure_seconds)
                            ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
                                stop_id = EXCLUDED.stop_id, arrival_time = EXCLUDED.arrival_time,
                                departure_time = EXCLUDED.departure_time, arrival_seconds = EXCLUDED.arrival_seconds,
                                departure_seconds = EXCLUDED.departure_seconds
                        """), stop_time_data)

                    total_stop_times += 1

        if not dry_run:
            db.commit()

        logger.info(f"  {route_id}: {len(stops)} stops × 4 services × 2 directions")

    return total_trips, total_stop_times


def clear_existing_data(db, dry_run: bool):
    """Clear existing Metro Madrid trips and stop_times."""
    logger.info("Clearing existing Metro Madrid schedule data...")

    if dry_run:
        count = db.execute(text("""
            SELECT COUNT(*) FROM gtfs_stop_times
            WHERE trip_id LIKE 'METRO_%'
            AND trip_id NOT LIKE 'METRO_SEV%'
            AND trip_id NOT LIKE 'METRO_GRANADA%'
        """)).scalar()
        logger.info(f"  Would delete {count} stop_times")
        return

    # Delete stop_times
    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id LIKE 'METRO_%'
        AND trip_id NOT LIKE 'METRO_SEV%'
        AND trip_id NOT LIKE 'METRO_GRANADA%'
    """))
    db.commit()
    logger.info(f"  Deleted {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text("""
        DELETE FROM gtfs_trips
        WHERE route_id LIKE 'METRO_%'
        AND route_id NOT LIKE 'METRO_SEV%'
        AND route_id NOT LIKE 'METRO_GRANADA%'
    """))
    db.commit()
    logger.info(f"  Deleted {result.rowcount} trips")


def main():
    parser = argparse.ArgumentParser(description='Generate Metro Madrid trips and stop_times')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made")

        # Clear existing data
        clear_existing_data(db, args.dry_run)

        # Create calendar
        calendar_count = create_calendar_entries(db, args.dry_run)
        logger.info(f"Calendar entries: {calendar_count}")

        # Create trips and stop_times
        trips_count, stop_times_count = create_trips_and_stop_times(db, args.dry_run)

        logger.info("\n" + "=" * 60)
        logger.info("Summary - Metro Madrid")
        logger.info("=" * 60)
        logger.info(f"Calendar entries: {calendar_count}")
        logger.info(f"Trips: {trips_count}")
        logger.info(f"Stop times: {stop_times_count}")
        logger.info("=" * 60)

        if not args.dry_run:
            logger.info("\nMetro Madrid trips generated successfully!")

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
