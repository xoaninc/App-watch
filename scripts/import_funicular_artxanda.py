#!/usr/bin/env python3
"""
Import Funicular de Artxanda GTFS data.

Usage:
    # Download GTFS first:
    curl -sL 'https://opendata.euskadi.eus/transport/moveuskadi/funicular_artxanda/gtfs_funicular_artxanda.zip' -o /tmp/funicular_artxanda.zip
    unzip -o /tmp/funicular_artxanda.zip -d /tmp/funicular_artxanda

    # Run import:
    python scripts/import_funicular_artxanda.py

    # Or dry run:
    python scripts/import_funicular_artxanda.py --dry-run
"""

import os
import sys
import csv
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2

# Load environment variables from .env file
def load_env(filepath):
    """Load environment variables from a file."""
    if not os.path.exists(filepath):
        return
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

load_env('.env')
load_env('.env.local')

# Constants
GTFS_DIR = "/tmp/funicular_artxanda"
PREFIX = "FUNICULAR_ARTXANDA_"
NETWORK_CODE = "FUNICULAR_ARTXANDA"

# Network info
NETWORK = {
    "code": NETWORK_CODE,
    "name": "Funicular de Artxanda",
    "region": "País Vasco",
    "color": "#DC0B0B",  # From GTFS route_color
    "text_color": "#FFFFFF",
    "logo_url": "/static/logos/funicular_artxanda.svg",
    "wikipedia_url": "https://es.wikipedia.org/wiki/Funicular_de_Artxanda",
    "description": "El Funicular de Artxanda es un funicular que conecta Bilbao con el monte Artxanda. Inaugurado en 1915, tiene un recorrido de 770 metros y salva un desnivel de 251 metros."
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        database=os.getenv('POSTGRES_DB', 'renfeserver'),
        user=os.getenv('POSTGRES_USER', 'renfeserver'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )


def read_csv(filename):
    """Read a CSV file and return list of dicts."""
    filepath = os.path.join(GTFS_DIR, filename)
    if not os.path.exists(filepath):
        print(f"  Warning: {filename} not found")
        return []

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return list(reader)


def create_network(cur, dry_run=False):
    """Create the network entry."""
    print(f"\n=== Creating network {NETWORK_CODE} ===")

    # Check if exists
    cur.execute("SELECT code FROM gtfs_networks WHERE code = %s", (NETWORK_CODE,))
    exists = cur.fetchone()

    if exists:
        print(f"  Network {NETWORK_CODE} already exists, updating...")
        if not dry_run:
            cur.execute("""
                UPDATE gtfs_networks SET
                    name = %s, region = %s, color = %s, text_color = %s,
                    logo_url = %s, wikipedia_url = %s, description = %s
                WHERE code = %s
            """, (
                NETWORK['name'], NETWORK['region'], NETWORK['color'],
                NETWORK['text_color'], NETWORK['logo_url'],
                NETWORK['wikipedia_url'], NETWORK['description'],
                NETWORK_CODE
            ))
    else:
        print(f"  Creating new network {NETWORK_CODE}")
        if not dry_run:
            cur.execute("""
                INSERT INTO gtfs_networks
                    (code, name, region, color, text_color, logo_url, wikipedia_url, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                NETWORK_CODE, NETWORK['name'], NETWORK['region'],
                NETWORK['color'], NETWORK['text_color'], NETWORK['logo_url'],
                NETWORK['wikipedia_url'], NETWORK['description']
            ))

    print(f"  Done")


def create_agency(cur, dry_run=False):
    """Create the agency entry."""
    agency_id = f"{PREFIX}Funicular-Artxanda"
    print(f"\n=== Creating agency {agency_id} ===")

    cur.execute("SELECT id FROM gtfs_agencies WHERE id = %s", (agency_id,))
    exists = cur.fetchone()

    if exists:
        print(f"  Agency already exists")
    else:
        print(f"  Creating new agency")
        if not dry_run:
            cur.execute("""
                INSERT INTO gtfs_agencies (id, name, url, timezone, lang, phone)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                agency_id,
                "Artxandako Funikularra",
                "https://funicularartxanda.bilbao.eus",
                "Europe/Madrid",
                "es",
                "+34944454966"
            ))

    print(f"  Done")


def import_stops(cur, dry_run=False):
    """Import stops."""
    print(f"\n=== Importing stops ===")
    stops = read_csv('stops.txt')

    count = 0
    for stop in stops:
        stop_id = f"{PREFIX}{stop['stop_id']}"

        if not dry_run:
            cur.execute("""
                INSERT INTO gtfs_stops (id, name, lat, lon, location_type, parent_station_id, wheelchair_boarding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name, lat = EXCLUDED.lat, lon = EXCLUDED.lon
            """, (
                stop_id,
                stop['stop_name'],
                float(stop['stop_lat']),
                float(stop['stop_lon']),
                int(stop.get('location_type', 0)),
                f"{PREFIX}{stop['parent_station']}" if stop.get('parent_station') else None,
                int(stop.get('wheelchair_boarding', 0))
            ))
        count += 1

    print(f"  Imported {count} stops")
    return count


def import_routes(cur, dry_run=False):
    """Import routes."""
    print(f"\n=== Importing routes ===")
    routes = read_csv('routes.txt')

    count = 0
    for route in routes:
        route_id = f"{PREFIX}{route['route_id']}"

        if not dry_run:
            cur.execute("""
                INSERT INTO gtfs_routes (id, short_name, long_name, route_type, color, text_color, network_id, agency_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    short_name = EXCLUDED.short_name, long_name = EXCLUDED.long_name,
                    color = EXCLUDED.color, network_id = EXCLUDED.network_id
            """, (
                route_id,
                route.get('route_short_name') or 'FA',  # Use FA if empty
                route.get('route_long_name', 'Funicular de Artxanda'),
                int(route.get('route_type', 7)),  # 7 = Funicular
                route.get('route_color', 'DC0B0B'),
                route.get('route_text_color', 'FFFFFF'),
                NETWORK_CODE,
                f"{PREFIX}Funicular-Artxanda"
            ))
        count += 1

    print(f"  Imported {count} routes")
    return count


def import_calendars(cur, dry_run=False):
    """Import calendars."""
    print(f"\n=== Importing calendars ===")

    # Delete existing
    if not dry_run:
        cur.execute("DELETE FROM gtfs_calendar WHERE service_id LIKE %s", (f"{PREFIX}%",))

    calendars = read_csv('calendar.txt')

    count = 0
    for cal in calendars:
        service_id = f"{PREFIX}{cal['service_id']}"

        if not dry_run:
            cur.execute("""
                INSERT INTO gtfs_calendar
                    (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (service_id) DO UPDATE SET
                    monday = EXCLUDED.monday, tuesday = EXCLUDED.tuesday, wednesday = EXCLUDED.wednesday,
                    thursday = EXCLUDED.thursday, friday = EXCLUDED.friday, saturday = EXCLUDED.saturday,
                    sunday = EXCLUDED.sunday, start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date
            """, (
                service_id,
                cal['monday'] == '1', cal['tuesday'] == '1', cal['wednesday'] == '1',
                cal['thursday'] == '1', cal['friday'] == '1', cal['saturday'] == '1',
                cal['sunday'] == '1', cal['start_date'], cal['end_date']
            ))
        count += 1

    print(f"  Imported {count} calendars")
    return count


def import_trips(cur, dry_run=False):
    """Import trips."""
    print(f"\n=== Importing trips ===")

    # Delete existing (respecting FK: stop_times first)
    if not dry_run:
        cur.execute("DELETE FROM gtfs_stop_times WHERE trip_id LIKE %s", (f"{PREFIX}%",))
        cur.execute("DELETE FROM gtfs_trips WHERE id LIKE %s", (f"{PREFIX}%",))

    trips = read_csv('trips.txt')

    count = 0
    for trip in trips:
        trip_id = f"{PREFIX}{trip['trip_id']}"
        route_id = f"{PREFIX}{trip['route_id']}"
        service_id = f"{PREFIX}{trip['service_id']}"
        shape_id = f"{PREFIX}{trip['shape_id']}" if trip.get('shape_id') else None

        if not dry_run:
            cur.execute("""
                INSERT INTO gtfs_trips (id, route_id, service_id, headsign, direction_id, shape_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    route_id = EXCLUDED.route_id, service_id = EXCLUDED.service_id,
                    headsign = EXCLUDED.headsign, direction_id = EXCLUDED.direction_id
            """, (
                trip_id, route_id, service_id,
                trip.get('trip_headsign', ''),
                int(trip.get('direction_id', 0)),
                shape_id
            ))
        count += 1

    print(f"  Imported {count} trips")
    return count


def time_to_seconds(time_str):
    """Convert HH:MM:SS to seconds since midnight."""
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2]) if len(parts) > 2 else 0
    return hours * 3600 + minutes * 60 + seconds


def import_stop_times(cur, dry_run=False):
    """Import stop_times."""
    print(f"\n=== Importing stop_times ===")

    stop_times = read_csv('stop_times.txt')

    count = 0
    batch = []

    for st in stop_times:
        trip_id = f"{PREFIX}{st['trip_id']}"
        stop_id = f"{PREFIX}{st['stop_id']}"
        arrival_time = st['arrival_time']
        departure_time = st['departure_time']

        batch.append((
            trip_id, stop_id,
            int(st['stop_sequence']),
            arrival_time,
            departure_time,
            time_to_seconds(arrival_time),
            time_to_seconds(departure_time),
            int(st.get('pickup_type', 0)),
            int(st.get('drop_off_type', 0))
        ))
        count += 1

        # Insert in batches
        if len(batch) >= 500 and not dry_run:
            cur.executemany("""
                INSERT INTO gtfs_stop_times
                    (trip_id, stop_id, stop_sequence, arrival_time, departure_time,
                     arrival_seconds, departure_seconds, pickup_type, drop_off_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, batch)
            batch = []

    # Insert remaining
    if batch and not dry_run:
        cur.executemany("""
            INSERT INTO gtfs_stop_times
                (trip_id, stop_id, stop_sequence, arrival_time, departure_time,
                 arrival_seconds, departure_seconds, pickup_type, drop_off_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, batch)

    print(f"  Imported {count} stop_times")
    return count


def import_shapes(cur, dry_run=False):
    """Import shapes."""
    print(f"\n=== Importing shapes ===")

    # Delete existing
    if not dry_run:
        cur.execute("DELETE FROM gtfs_shape_points WHERE shape_id LIKE %s", (f"{PREFIX}%",))
        cur.execute("DELETE FROM gtfs_shapes WHERE id LIKE %s", (f"{PREFIX}%",))

    shapes = read_csv('shapes.txt')

    # First, collect unique shape_ids
    shape_ids = set()
    for pt in shapes:
        shape_ids.add(pt['shape_id'])

    # Create shape entries
    for sid in shape_ids:
        shape_id = f"{PREFIX}{sid}"
        if not dry_run:
            cur.execute("""
                INSERT INTO gtfs_shapes (id) VALUES (%s)
                ON CONFLICT (id) DO NOTHING
            """, (shape_id,))
    print(f"  Created {len(shape_ids)} shapes")

    # Now insert points
    count = 0
    for pt in shapes:
        shape_id = f"{PREFIX}{pt['shape_id']}"

        if not dry_run:
            cur.execute("""
                INSERT INTO gtfs_shape_points (shape_id, lat, lon, sequence, dist_traveled)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                shape_id,
                float(pt['shape_pt_lat']),
                float(pt['shape_pt_lon']),
                int(pt['shape_pt_sequence']),
                float(pt.get('shape_dist_traveled', 0))
            ))
        count += 1

    print(f"  Imported {count} shape points")
    return count


def main():
    parser = argparse.ArgumentParser(description='Import Funicular Artxanda GTFS')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()

    # Verify GTFS directory exists
    if not os.path.exists(GTFS_DIR):
        print(f"Error: GTFS directory not found: {GTFS_DIR}")
        print("Download it first with:")
        print("  curl -sL 'https://opendata.euskadi.eus/transport/moveuskadi/funicular_artxanda/gtfs_funicular_artxanda.zip' -o /tmp/funicular_artxanda.zip")
        print("  unzip -o /tmp/funicular_artxanda.zip -d /tmp/funicular_artxanda")
        sys.exit(1)

    print("=" * 60)
    print("FUNICULAR DE ARTXANDA - GTFS IMPORT")
    print("=" * 60)

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Create network and agency
        create_network(cur, args.dry_run)
        create_agency(cur, args.dry_run)

        # Import data
        import_stops(cur, args.dry_run)
        import_routes(cur, args.dry_run)
        import_calendars(cur, args.dry_run)
        import_shapes(cur, args.dry_run)
        import_trips(cur, args.dry_run)
        import_stop_times(cur, args.dry_run)

        if not args.dry_run:
            conn.commit()
            print("\n=== IMPORT COMPLETED SUCCESSFULLY ===")
        else:
            conn.rollback()
            print("\n=== DRY RUN COMPLETED ===")

    except Exception as e:
        conn.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
