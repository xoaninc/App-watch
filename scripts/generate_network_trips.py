#!/usr/bin/env python3
"""Generate trips and stop_times for any transit network using existing data.

Uses data already in the database:
- gtfs_stops, gtfs_routes, gtfs_stop_route_sequence, gtfs_route_frequencies

Usage:
    python scripts/generate_network_trips.py ML_        # Metro Ligero Madrid
    python scripts/generate_network_trips.py TMB_METRO  # TMB Metro Barcelona
    python scripts/generate_network_trips.py FGC_       # FGC
    python scripts/generate_network_trips.py EUSKOTREN_ # Euskotren
    python scripts/generate_network_trips.py METRO_BILBAO_ # Metro Bilbao
"""

import argparse
import logging
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

AVG_STATION_TIME = 120  # 2 minutes between stations

SERVICE_TYPES = [
    {'id': '_LABORABLE', 'days': [True, True, True, True, False, False, False]},
    {'id': '_VIERNES', 'days': [False, False, False, False, True, False, False]},
    {'id': '_SABADO', 'days': [False, False, False, False, False, True, False]},
    {'id': '_DOMINGO', 'days': [False, False, False, False, False, False, True]},
]


def get_routes(db, prefix: str) -> list:
    """Get all routes matching prefix."""
    result = db.execute(text(
        "SELECT id FROM gtfs_routes WHERE id LIKE :prefix ORDER BY id"
    ), {'prefix': f'{prefix}%'}).fetchall()
    return [row[0] for row in result]


def get_route_stops(db, route_id: str) -> list:
    """Get ordered stops for a route."""
    result = db.execute(text("""
        SELECT stop_id FROM gtfs_stop_route_sequence
        WHERE route_id = :route_id ORDER BY sequence
    """), {'route_id': route_id}).fetchall()
    return [row[0] for row in result]


def get_headsigns(db, stops: list) -> tuple:
    """Get headsigns from first and last stop names."""
    if not stops:
        return None, None
    first = db.execute(text("SELECT name FROM gtfs_stops WHERE id = :id"), {'id': stops[0]}).fetchone()
    last = db.execute(text("SELECT name FROM gtfs_stops WHERE id = :id"), {'id': stops[-1]}).fetchone()
    return (last[0] if last else None, first[0] if first else None)


def generate_for_network(db, prefix: str, dry_run: bool):
    """Generate trips and stop_times for a network."""

    # Clean prefix for service_id
    service_prefix = prefix.rstrip('_').replace('.', '_')

    routes = get_routes(db, prefix)
    if not routes:
        logger.error(f"No routes found with prefix '{prefix}'")
        return

    logger.info(f"Found {len(routes)} routes: {routes}")

    # Clear existing data
    logger.info("Clearing existing data...")
    if not dry_run:
        db.execute(text(f"DELETE FROM gtfs_stop_times WHERE trip_id LIKE '{prefix}%'"))
        db.execute(text(f"DELETE FROM gtfs_trips WHERE route_id LIKE '{prefix}%'"))
        db.commit()

    # Create calendar entries
    logger.info("Creating calendar entries...")
    for service in SERVICE_TYPES:
        service_id = f"{service_prefix}{service['id']}"
        if not dry_run:
            db.execute(text("""
                INSERT INTO gtfs_calendar
                (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                VALUES (:service_id, :mon, :tue, :wed, :thu, :fri, :sat, :sun, '2025-01-01', '2026-12-31')
                ON CONFLICT (service_id) DO UPDATE SET
                    monday=EXCLUDED.monday, tuesday=EXCLUDED.tuesday, wednesday=EXCLUDED.wednesday,
                    thursday=EXCLUDED.thursday, friday=EXCLUDED.friday, saturday=EXCLUDED.saturday, sunday=EXCLUDED.sunday
            """), {
                'service_id': service_id,
                'mon': service['days'][0], 'tue': service['days'][1], 'wed': service['days'][2],
                'thu': service['days'][3], 'fri': service['days'][4], 'sat': service['days'][5], 'sun': service['days'][6]
            })
    if not dry_run:
        db.commit()

    # Create trips and stop_times
    total_trips = 0
    total_stop_times = 0

    for route_id in routes:
        stops = get_route_stops(db, route_id)
        if not stops:
            logger.warning(f"  No stops for {route_id}, skipping")
            continue

        headsign_0, headsign_1 = get_headsigns(db, stops)

        for service in SERVICE_TYPES:
            service_id = f"{service_prefix}{service['id']}"

            for direction in [0, 1]:
                trip_id = f"{route_id}_{service_id}_{direction}"
                headsign = headsign_0 if direction == 0 else headsign_1

                if not dry_run:
                    db.execute(text("""
                        INSERT INTO gtfs_trips (id, route_id, service_id, headsign, direction_id)
                        VALUES (:id, :route_id, :service_id, :headsign, :direction_id)
                        ON CONFLICT (id) DO UPDATE SET headsign=EXCLUDED.headsign
                    """), {'id': trip_id, 'route_id': route_id, 'service_id': service_id,
                           'headsign': headsign, 'direction_id': direction})

                total_trips += 1

                # Stop times
                stop_list = stops if direction == 0 else list(reversed(stops))
                base_time = 6 * 3600 + 5 * 60  # 06:05

                for seq, stop_id in enumerate(stop_list):
                    arr_sec = base_time + (seq * AVG_STATION_TIME)
                    dep_sec = arr_sec + 30
                    arr_time = f"{arr_sec // 3600}:{(arr_sec % 3600) // 60:02d}:{arr_sec % 60:02d}"
                    dep_time = f"{dep_sec // 3600}:{(dep_sec % 3600) // 60:02d}:{dep_sec % 60:02d}"

                    if not dry_run:
                        db.execute(text("""
                            INSERT INTO gtfs_stop_times
                            (trip_id, stop_sequence, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds)
                            VALUES (:trip_id, :seq, :stop_id, :arr_time, :dep_time, :arr_sec, :dep_sec)
                            ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET stop_id=EXCLUDED.stop_id
                        """), {'trip_id': trip_id, 'seq': seq, 'stop_id': stop_id,
                               'arr_time': arr_time, 'dep_time': dep_time, 'arr_sec': arr_sec, 'dep_sec': dep_sec})

                    total_stop_times += 1

        if not dry_run:
            db.commit()

        logger.info(f"  {route_id}: {len(stops)} stops")

    logger.info(f"\n{'DRY RUN - ' if dry_run else ''}Summary for {prefix}:")
    logger.info(f"  Trips: {total_trips}")
    logger.info(f"  Stop times: {total_stop_times}")


def main():
    parser = argparse.ArgumentParser(description='Generate trips for a transit network')
    parser.add_argument('prefix', help='Route prefix (e.g., ML_, TMB_METRO, FGC_)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()

    db = SessionLocal()
    try:
        generate_for_network(db, args.prefix, args.dry_run)
        if not args.dry_run:
            logger.info("Done!")
    finally:
        db.close()


if __name__ == '__main__':
    main()
