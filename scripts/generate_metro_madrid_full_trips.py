#!/usr/bin/env python3
"""Generate full-day trips for Metro Madrid based on frequencies.

Metro Madrid publishes frequency data, not individual trip schedules.
This script generates trips throughout the operating day by:
1. Using the existing placeholder trip to get stop sequence and travel times
2. Using frequency data to determine headways
3. Creating trips for every headway interval throughout the day

Run on the server:
    source .venv/bin/activate
    python scripts/generate_metro_madrid_full_trips.py
"""

import os
import sys
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment
load_dotenv('.env.local')

# Metro Madrid lines with their operating hours (approximate)
METRO_LINES = [
    'METRO_1', 'METRO_2', 'METRO_3', 'METRO_4', 'METRO_5', 'METRO_6',
    'METRO_7', 'METRO_7B', 'METRO_8', 'METRO_9', 'METRO_9B',
    'METRO_10', 'METRO_10B', 'METRO_11', 'METRO_12', 'METRO_R'
]

# Operating hours (approximate, actual varies by line)
SERVICE_START = time(6, 0)  # 6:00 AM
SERVICE_END = time(1, 30)   # 1:30 AM (next day)

# Service IDs for different day types
SERVICE_IDS = {
    'weekday': 'METRO_MAD_LABORABLE',
    'friday': 'METRO_MAD_VIERNES',
    'saturday': 'METRO_MAD_SABADO',
    'sunday': 'METRO_MAD_DOMINGO'
}

# Default headway if no frequency data (in seconds)
DEFAULT_HEADWAY = 300  # 5 minutes


def get_database_url() -> str:
    """Get database URL from environment."""
    return os.getenv('DATABASE_URL')


def get_template_trip(conn, route_id: str, direction: int) -> Optional[Dict]:
    """Get a template trip to base new trips on."""
    result = conn.execute(text("""
        SELECT t.id, t.route_id, t.service_id, t.headsign, t.direction_id
        FROM gtfs_trips t
        WHERE t.route_id = :route_id
        AND (t.direction_id = :direction OR t.direction_id IS NULL)
        ORDER BY t.id
        LIMIT 1
    """), {'route_id': route_id, 'direction': direction})

    row = result.fetchone()
    if row:
        return {
            'id': row[0],
            'route_id': row[1],
            'service_id': row[2],
            'headsign': row[3],
            'direction_id': row[4]
        }
    return None


def get_template_stop_times(conn, trip_id: str) -> List[Dict]:
    """Get stop times from template trip."""
    result = conn.execute(text("""
        SELECT stop_id, stop_sequence, arrival_seconds, departure_seconds
        FROM gtfs_stop_times
        WHERE trip_id = :trip_id
        ORDER BY stop_sequence
    """), {'trip_id': trip_id})

    return [
        {
            'stop_id': row[0],
            'stop_sequence': row[1],
            'arrival_seconds': row[2] or 0,
            'departure_seconds': row[3] or 0
        }
        for row in result.fetchall()
    ]


def get_frequencies(conn, route_id: str, day_type: str) -> List[Dict]:
    """Get frequency data for a route."""
    result = conn.execute(text("""
        SELECT start_time, end_time, headway_secs
        FROM gtfs_route_frequencies
        WHERE route_id = :route_id
        AND day_type = :day_type
        ORDER BY start_time
    """), {'route_id': route_id, 'day_type': day_type})

    return [
        {
            'start_time': row[0],
            'end_time': row[1],
            'headway_secs': row[2]
        }
        for row in result.fetchall()
    ]


def time_to_seconds(t: time) -> int:
    """Convert time to seconds since midnight."""
    return t.hour * 3600 + t.minute * 60 + t.second


def seconds_to_time_str(secs: int) -> str:
    """Convert seconds to HH:MM:SS string (handles 25+ hours for GTFS)."""
    hours = secs // 3600
    mins = (secs % 3600) // 60
    seconds = secs % 60
    return f"{hours:02d}:{mins:02d}:{seconds:02d}"


def generate_trips_for_line(
    conn,
    route_id: str,
    service_id: str,
    day_type: str,
    dry_run: bool = False
) -> Tuple[int, int]:
    """Generate trips for a single line and service type.

    Returns: (trips_created, stop_times_created)
    """
    trips_created = 0
    stop_times_created = 0

    # Get frequency data
    frequencies = get_frequencies(conn, route_id, day_type)
    if not frequencies:
        print(f"  No frequency data for {route_id} on {day_type}")
        return 0, 0

    # Process both directions
    for direction in [0, 1]:
        # Get template trip for this direction
        template = get_template_trip(conn, route_id, direction)
        if not template:
            # Try without direction filter
            template = get_template_trip(conn, route_id, 0)
        if not template:
            print(f"  No template trip for {route_id} direction {direction}")
            continue

        # Get stop times from template
        template_stops = get_template_stop_times(conn, template['id'])
        if not template_stops:
            print(f"  No stop times for template {template['id']}")
            continue

        # Calculate relative travel times (time from first stop to each subsequent stop)
        first_departure = template_stops[0]['departure_seconds']
        travel_times = []
        for st in template_stops:
            travel_times.append({
                'stop_id': st['stop_id'],
                'stop_sequence': st['stop_sequence'],
                'arrival_offset': st['arrival_seconds'] - first_departure,
                'departure_offset': st['departure_seconds'] - first_departure
            })

        # Generate trips for each frequency period
        trip_num = 0
        for freq in frequencies:
            start_secs = time_to_seconds(freq['start_time'])

            # Handle end_time that might be past midnight
            end_time_str = str(freq['end_time'])
            if end_time_str == '00:00:00':
                end_secs = 24 * 3600  # Midnight
            elif ':' in end_time_str:
                parts = end_time_str.split(':')
                end_secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                if end_secs < start_secs:  # Past midnight
                    end_secs += 24 * 3600
            else:
                end_secs = start_secs + 3600  # Default 1 hour

            headway = freq['headway_secs'] or DEFAULT_HEADWAY

            # Generate trips every headway seconds
            current_time = start_secs
            while current_time < end_secs:
                trip_id = f"{route_id}_{service_id}_{direction}_{trip_num}"

                if not dry_run:
                    # Insert trip
                    conn.execute(text("""
                        INSERT INTO gtfs_trips (id, route_id, service_id, headsign, direction_id)
                        VALUES (:id, :route_id, :service_id, :headsign, :direction_id)
                        ON CONFLICT (id) DO UPDATE SET
                            route_id = :route_id,
                            service_id = :service_id,
                            headsign = :headsign,
                            direction_id = :direction_id
                    """), {
                        'id': trip_id,
                        'route_id': route_id,
                        'service_id': service_id,
                        'headsign': template['headsign'],
                        'direction_id': direction
                    })

                    # Insert stop times
                    for tt in travel_times:
                        arrival_secs = current_time + tt['arrival_offset']
                        departure_secs = current_time + tt['departure_offset']

                        conn.execute(text("""
                            INSERT INTO gtfs_stop_times
                            (trip_id, stop_id, stop_sequence, arrival_seconds, departure_seconds,
                             arrival_time, departure_time)
                            VALUES (:trip_id, :stop_id, :stop_sequence, :arrival_secs, :departure_secs,
                                    :arrival_time, :departure_time)
                            ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
                                stop_id = :stop_id,
                                arrival_seconds = :arrival_secs,
                                departure_seconds = :departure_secs,
                                arrival_time = :arrival_time,
                                departure_time = :departure_time
                        """), {
                            'trip_id': trip_id,
                            'stop_id': tt['stop_id'],
                            'stop_sequence': tt['stop_sequence'],
                            'arrival_secs': arrival_secs,
                            'departure_secs': departure_secs,
                            'arrival_time': seconds_to_time_str(arrival_secs),
                            'departure_time': seconds_to_time_str(departure_secs)
                        })
                        stop_times_created += 1

                trips_created += 1
                trip_num += 1
                current_time += headway

    return trips_created, stop_times_created


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate Metro Madrid trips from frequencies')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--line', help='Only process specific line (e.g., METRO_1)')
    parser.add_argument('--day-type', choices=['weekday', 'friday', 'saturday', 'sunday'],
                        default='weekday', help='Day type to generate')
    args = parser.parse_args()

    db_url = get_database_url()
    if not db_url:
        print("Error: DATABASE_URL not set")
        sys.exit(1)

    engine = create_engine(db_url)

    # First, let's check existing data
    with engine.connect() as conn:
        # Check existing trips
        result = conn.execute(text("""
            SELECT route_id, COUNT(*) as trip_count
            FROM gtfs_trips
            WHERE route_id LIKE 'METRO\\_%' ESCAPE '\\'
            AND route_id NOT LIKE 'METRO\\_VALENCIA%' ESCAPE '\\'
            AND route_id NOT LIKE 'METRO\\_BILBAO%' ESCAPE '\\'
            AND route_id NOT LIKE 'METRO\\_GRANADA%' ESCAPE '\\'
            AND route_id NOT LIKE 'METRO\\_MALAGA%' ESCAPE '\\'
            AND route_id NOT LIKE 'METRO\\_SEV%' ESCAPE '\\'
            GROUP BY route_id
            ORDER BY route_id
        """))

        print("Current Metro Madrid trips:")
        total_existing = 0
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]} trips")
            total_existing += row[1]
        print(f"  Total: {total_existing} trips\n")

        # Check frequencies
        result = conn.execute(text("""
            SELECT route_id, day_type, COUNT(*) as freq_count
            FROM gtfs_route_frequencies
            WHERE route_id LIKE 'METRO\\_%' ESCAPE '\\'
            AND route_id NOT LIKE 'METRO\\_VALENCIA%' ESCAPE '\\'
            GROUP BY route_id, day_type
            ORDER BY route_id, day_type
        """))

        print("Available frequency data:")
        for row in result.fetchall():
            print(f"  {row[0]} ({row[1]}): {row[2]} periods")

    if args.dry_run:
        print("\n[DRY RUN MODE - no changes will be made]\n")

    # Process lines
    lines_to_process = [args.line] if args.line else METRO_LINES
    day_types_to_process = [args.day_type] if args.day_type else SERVICE_IDS.keys()

    total_trips = 0
    total_stop_times = 0

    with engine.begin() as conn:
        for line in lines_to_process:
            for day_type in day_types_to_process:
                service_id = SERVICE_IDS[day_type]
                print(f"\nProcessing {line} for {day_type} (service: {service_id})...")

                trips, stop_times = generate_trips_for_line(
                    conn, line, service_id, day_type, args.dry_run
                )

                print(f"  Created: {trips} trips, {stop_times} stop_times")
                total_trips += trips
                total_stop_times += stop_times

    print(f"\n{'[DRY RUN] Would have created' if args.dry_run else 'Created'}:")
    print(f"  {total_trips} trips")
    print(f"  {total_stop_times} stop_times")


if __name__ == '__main__':
    main()
