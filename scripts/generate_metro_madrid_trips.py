#!/usr/bin/env python3
"""Generate trips and stop_times for Metro Madrid using existing data.

This script uses data already in the database:
- gtfs_stops (242 Metro Madrid stations)
- gtfs_routes (16 lines)
- gtfs_stop_route_sequence (stop order per line)
- gtfs_route_frequencies (service frequencies)

It can optionally fetch real travel times from CRTM Feature Service:
- Layer 4 (M4_Tramos): LONGITUDTRAMOANTERIOR, VELOCIDADTRAMOANTERIOR

It generates:
- gtfs_calendar (service definitions)
- gtfs_trips (one per route/direction/service)
- gtfs_stop_times (based on real or estimated travel times)

Usage:
    python scripts/generate_metro_madrid_trips.py [--dry-run] [--use-crtm-times]
"""

import os
import sys
import argparse
import logging
from datetime import date
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CRTM Feature Service endpoint for travel time data
CRTM_PARADAS_URL = "https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M4_Red/FeatureServer/5/query"

# Fallback average time between Metro Madrid stations (seconds)
AVG_STATION_TIME = 120  # 2 minutes

# Dwell time at stations (seconds)
DWELL_TIME = 30

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

# Line number normalization mapping for CRTM data
LINE_MAPPING = {
    '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6',
    '7': '7', '7a': '7', '7b': '7B',
    '8': '8',
    '9': '9', '9a': '9', '9b': '9B',
    '10': '10', '10a': '10', '10b': '10B',
    '11': '11', '12': '12', '12-1': '12', '12-2': '12',
    'R': 'R', 'r': 'R',
}


def fetch_crtm_travel_times() -> Dict[str, Dict[str, List[Tuple[int, float]]]]:
    """Fetch travel time data from CRTM M4_ParadasPorItinerario layer.

    Returns:
        Dict of {line: {sentido: [(orden, travel_time_seconds), ...]}}
    """
    logger.info("Fetching travel times from CRTM...")
    features = []
    offset = 0
    batch_size = 1000

    while True:
        params = {
            'where': '1=1',
            'outFields': 'NUMEROLINEAUSUARIO,SENTIDO,NUMEROORDEN,LONGITUDTRAMOANTERIOR,VELOCIDADTRAMOANTERIOR',
            'f': 'json',
            'resultOffset': offset,
            'resultRecordCount': batch_size,
        }

        try:
            response = requests.get(CRTM_PARADAS_URL, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            batch_features = data.get('features', [])
            if not batch_features:
                break

            features.extend(batch_features)
            offset += batch_size

            if len(batch_features) < batch_size:
                break

        except Exception as e:
            logger.warning(f"Error fetching CRTM travel times: {e}")
            return {}

    logger.info(f"Fetched {len(features)} travel time records")

    # Group by line and direction
    result: Dict[str, Dict[str, List[Tuple[int, float]]]] = {}

    for feature in features:
        attrs = feature.get('attributes', {})

        raw_line = str(attrs.get('NUMEROLINEAUSUARIO', '')).strip().lower()
        sentido = attrs.get('SENTIDO', 1)
        orden = attrs.get('NUMEROORDEN', 0)
        distancia = attrs.get('LONGITUDTRAMOANTERIOR')  # meters
        velocidad = attrs.get('VELOCIDADTRAMOANTERIOR')  # km/h

        # Normalize line
        line = LINE_MAPPING.get(raw_line)
        if not line:
            continue

        # Calculate travel time if we have distance and velocity
        if distancia and velocidad and velocidad > 0:
            # Convert km/h to m/s, then calculate time
            velocidad_ms = velocidad / 3.6
            travel_time = distancia / velocidad_ms
        else:
            # Use fallback
            travel_time = AVG_STATION_TIME

        if line not in result:
            result[line] = {}
        if sentido not in result[line]:
            result[line][sentido] = []

        result[line][sentido].append((orden, travel_time))

    # Sort each direction by order
    for line in result:
        for sentido in result[line]:
            result[line][sentido].sort(key=lambda x: x[0])

    return result


def get_travel_times_for_route(
    crtm_times: Dict[str, Dict[str, List[Tuple[int, float]]]],
    route_id: str,
    num_stops: int
) -> List[float]:
    """Get travel times between stops for a route.

    Args:
        crtm_times: CRTM travel time data
        route_id: Route ID (e.g., "METRO_10")
        num_stops: Number of stops on the route

    Returns:
        List of travel times in seconds (one per stop, first is 0)
    """
    # Extract line number from route_id
    line = route_id.replace('METRO_', '')

    if line not in crtm_times:
        # Use fallback times
        return [0] + [AVG_STATION_TIME] * (num_stops - 1)

    # Use direction 1 as primary (or 2 if not available)
    if 1 in crtm_times[line]:
        times_data = crtm_times[line][1]
    elif 2 in crtm_times[line]:
        times_data = crtm_times[line][2]
    else:
        return [0] + [AVG_STATION_TIME] * (num_stops - 1)

    # Extract just the times (sorted by order)
    times = [t[1] for t in times_data]

    # Ensure we have enough times
    if len(times) < num_stops:
        # Pad with fallback times
        times.extend([AVG_STATION_TIME] * (num_stops - len(times)))
    elif len(times) > num_stops:
        times = times[:num_stops]

    # First stop has 0 travel time
    times[0] = 0

    return times


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


def create_trips_and_stop_times(db, dry_run: bool, use_crtm_times: bool = False) -> tuple:
    """Create trips and stop_times for all Metro Madrid routes.

    Args:
        db: Database session
        dry_run: If True, don't make any changes
        use_crtm_times: If True, fetch real travel times from CRTM

    Returns:
        Tuple of (total_trips, total_stop_times)
    """
    logger.info("Creating trips and stop_times...")

    # Fetch CRTM travel times if requested
    crtm_times = {}
    if use_crtm_times:
        crtm_times = fetch_crtm_travel_times()
        if crtm_times:
            logger.info(f"Using CRTM travel times for {len(crtm_times)} lines")
        else:
            logger.warning("Could not fetch CRTM times, using fallback")

    total_trips = 0
    total_stop_times = 0

    for route_id in METRO_ROUTES:
        stops = get_route_stops(db, route_id)
        if not stops:
            logger.warning(f"  No stops found for {route_id}, skipping")
            continue

        headsign_0, headsign_1 = get_route_headsigns(db, route_id)

        # Get travel times for this route
        travel_times = get_travel_times_for_route(crtm_times, route_id, len(stops))

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
                times_list = travel_times if direction == 0 else list(reversed(travel_times))

                base_time = 6 * 3600 + 5 * 60  # 06:05:00 (first train)
                cumulative_time = 0

                for seq, stop_id in enumerate(stop_list):
                    # Add travel time to this stop
                    cumulative_time += times_list[seq]

                    arrival_seconds = int(base_time + cumulative_time)
                    departure_seconds = arrival_seconds + DWELL_TIME

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

                    # Add dwell time for next segment
                    cumulative_time += DWELL_TIME

        if not dry_run:
            db.commit()

        # Calculate total journey time for logging
        total_journey = sum(travel_times) + (len(stops) - 1) * DWELL_TIME
        logger.info(f"  {route_id}: {len(stops)} stops, {total_journey // 60:.0f} min journey")

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
    parser.add_argument('--use-crtm-times', action='store_true',
                        help='Fetch real travel times from CRTM (distance/velocity data)')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made")

        if args.use_crtm_times:
            logger.info("Using CRTM real travel times")

        # Clear existing data
        clear_existing_data(db, args.dry_run)

        # Create calendar
        calendar_count = create_calendar_entries(db, args.dry_run)
        logger.info(f"Calendar entries: {calendar_count}")

        # Create trips and stop_times
        trips_count, stop_times_count = create_trips_and_stop_times(
            db, args.dry_run, use_crtm_times=args.use_crtm_times
        )

        logger.info("\n" + "=" * 60)
        logger.info("Summary - Metro Madrid")
        logger.info("=" * 60)
        logger.info(f"Calendar entries: {calendar_count}")
        logger.info(f"Trips: {trips_count}")
        logger.info(f"Stop times: {stop_times_count}")
        if args.use_crtm_times:
            logger.info("Travel times: CRTM real data")
        else:
            logger.info(f"Travel times: Fixed {AVG_STATION_TIME}s between stations")
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
