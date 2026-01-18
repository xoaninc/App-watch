#!/usr/bin/env python3
"""Import Metro Ligero GTFS data (trips, stop_times, calendar)."""

import csv
import sys
import os
from pathlib import Path
from datetime import datetime, time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://renfeserver:renfeserver_prod_2026@localhost/renfeserver_prod"
)


def parse_gtfs_time(time_str: str) -> tuple:
    """Parse GTFS time (can be >24:00) to (time object, total_seconds).

    Returns tuple of (time, seconds_from_midnight).
    For times >= 24:00, time is normalized but seconds keeps original value.
    """
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2]) if len(parts) > 2 else 0

    total_seconds = hours * 3600 + minutes * 60 + seconds
    normalized_time = time(hours % 24, minutes, seconds)

    return normalized_time, total_seconds


def build_stop_mapping(gtfs_path: Path, db_session) -> dict:
    """Build mapping from GTFS stop_id to DB stop_id based on name.

    Returns dict: {gtfs_stop_id: db_stop_id}
    """
    from sqlalchemy import text

    # Load DB stops by name (normalize ñ/Ñ to N)
    result = db_session.execute(text(
        "SELECT id, UPPER(REPLACE(REPLACE(name, 'ñ', 'N'), 'Ñ', 'N')) as name FROM gtfs_stops WHERE id LIKE 'ML_%'"
    ))
    db_stops = {row[1]: row[0] for row in result}

    # Load GTFS stops
    gtfs_stops = {}
    with open(gtfs_path / 'stops.txt', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['location_type'] == '0':
                name = row['stop_name'].upper().replace('Ñ', 'N')
                gtfs_stops[row['stop_id']] = name

    # Build mapping
    mapping = {}
    missing = []
    for gtfs_id, name in gtfs_stops.items():
        if name in db_stops:
            mapping[gtfs_id] = db_stops[name]
        else:
            missing.append((gtfs_id, name))

    if missing:
        print(f"  Warning: {len(missing)} GTFS stops not found in DB:")
        for gtfs_id, name in missing[:5]:
            print(f"    {gtfs_id}: {name}")
        if len(missing) > 5:
            print(f"    ... and {len(missing) - 5} more")

    return mapping


def gtfs_route_to_ml_route(gtfs_route_id: str) -> str:
    """Convert GTFS route ID to our ML route ID.

    GTFS: 10__ML1___ -> ML_ML1
    """
    mapping = {
        '10__ML1___': 'ML_ML1',
        '10__ML2___': 'ML_ML2',
        '10__ML3___': 'ML_ML3',
        '10__ML4___': 'ML_ML4',
    }
    return mapping.get(gtfs_route_id)


def import_metro_ligero(gtfs_dir: str, dry_run: bool = False):
    """Import Metro Ligero GTFS data."""
    gtfs_path = Path(gtfs_dir)

    if not gtfs_path.exists():
        print(f"Error: GTFS directory not found: {gtfs_dir}")
        return

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 0. Build stop mapping (GTFS stop_id -> DB stop_id)
        print("Building stop mapping...")
        stop_mapping = build_stop_mapping(gtfs_path, session)
        print(f"  Mapped {len(stop_mapping)} stops")

        # 1. Load calendar (service patterns)
        print("Loading calendar...")
        services = {}
        with open(gtfs_path / 'calendar.txt', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                service_id = row['service_id']
                services[service_id] = {
                    'monday': row['monday'] == '1',
                    'tuesday': row['tuesday'] == '1',
                    'wednesday': row['wednesday'] == '1',
                    'thursday': row['thursday'] == '1',
                    'friday': row['friday'] == '1',
                    'saturday': row['saturday'] == '1',
                    'sunday': row['sunday'] == '1',
                    'start_date': datetime.strptime(row['start_date'], '%Y%m%d').date(),
                    'end_date': datetime.strptime(row['end_date'], '%Y%m%d').date(),
                }
        print(f"  Loaded {len(services)} service patterns")

        # 2. Load calendar_dates (exceptions)
        print("Loading calendar_dates...")
        calendar_dates = []
        with open(gtfs_path / 'calendar_dates.txt', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                calendar_dates.append({
                    'service_id': row['service_id'],
                    'date': datetime.strptime(row['date'], '%Y%m%d').date(),
                    'exception_type': int(row['exception_type']),
                })
        print(f"  Loaded {len(calendar_dates)} calendar date exceptions")

        # 3. Load trips
        print("Loading trips...")
        trips = {}
        with open(gtfs_path / 'trips.txt', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                route_id = gtfs_route_to_ml_route(row['route_id'])
                if not route_id:
                    continue

                trip_id = row['trip_id']
                trips[trip_id] = {
                    'route_id': route_id,
                    'service_id': row['service_id'],
                    'headsign': row.get('trip_headsign', ''),
                    'direction_id': int(row.get('direction_id', 0)),
                    'shape_id': row.get('shape_id', ''),
                }
        print(f"  Loaded {len(trips)} trips")

        # 4. Load stop_times
        print("Loading stop_times...")
        stop_times = []
        with open(gtfs_path / 'stop_times.txt', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trip_id = row['trip_id']
                if trip_id not in trips:
                    continue

                stop_id = stop_mapping.get(row['stop_id'])
                if not stop_id:
                    continue

                arr_time, arr_seconds = parse_gtfs_time(row['arrival_time'])
                dep_time, dep_seconds = parse_gtfs_time(row['departure_time'])

                stop_times.append({
                    'trip_id': trip_id,
                    'stop_id': stop_id,
                    'arrival_time': row['arrival_time'],
                    'departure_time': row['departure_time'],
                    'arrival_seconds': arr_seconds,
                    'departure_seconds': dep_seconds,
                    'stop_sequence': int(row['stop_sequence']),
                })
        print(f"  Loaded {len(stop_times)} stop_times")

        if dry_run:
            print("\n[DRY RUN] Would import:")
            print(f"  - {len(services)} calendar entries")
            print(f"  - {len(calendar_dates)} calendar_dates")
            print(f"  - {len(trips)} trips")
            print(f"  - {len(stop_times)} stop_times")
            return

        # 5. Clear existing ML data
        print("\nClearing existing ML data...")
        session.execute(text("""
            DELETE FROM gtfs_stop_times
            WHERE trip_id IN (SELECT id FROM gtfs_trips WHERE route_id LIKE 'ML_%')
        """))
        session.execute(text("DELETE FROM gtfs_trips WHERE route_id LIKE 'ML_%'"))
        session.execute(text("DELETE FROM gtfs_calendar_dates WHERE service_id LIKE '10_I%'"))
        session.execute(text("DELETE FROM gtfs_calendar WHERE service_id LIKE '10_I%'"))
        print("  Done")

        # 6. Insert calendar
        print("Inserting calendar...")
        for service_id, svc in services.items():
            session.execute(text("""
                INSERT INTO gtfs_calendar
                (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                VALUES (:service_id, :mon, :tue, :wed, :thu, :fri, :sat, :sun, :start, :end)
            """), {
                'service_id': service_id,
                'mon': svc['monday'],
                'tue': svc['tuesday'],
                'wed': svc['wednesday'],
                'thu': svc['thursday'],
                'fri': svc['friday'],
                'sat': svc['saturday'],
                'sun': svc['sunday'],
                'start': svc['start_date'],
                'end': svc['end_date'],
            })
        print(f"  Inserted {len(services)} calendar entries")

        # 7. Insert calendar_dates
        print("Inserting calendar_dates...")
        for cd in calendar_dates:
            session.execute(text("""
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :date, :exception_type)
            """), cd)
        print(f"  Inserted {len(calendar_dates)} calendar_dates")

        # 8. Insert trips
        print("Inserting trips...")
        trip_id_mapping = {}  # GTFS trip_id -> DB trip_id
        for gtfs_trip_id, trip in trips.items():
            # Create a shorter trip ID for DB
            db_trip_id = f"ML_{gtfs_trip_id[-30:]}"  # Take last 30 chars
            trip_id_mapping[gtfs_trip_id] = db_trip_id

            session.execute(text("""
                INSERT INTO gtfs_trips (id, route_id, service_id, headsign, direction_id, shape_id)
                VALUES (:id, :route_id, :service_id, :headsign, :direction_id, :shape_id)
            """), {
                'id': db_trip_id,
                'route_id': trip['route_id'],
                'service_id': trip['service_id'],
                'headsign': trip['headsign'],
                'direction_id': trip['direction_id'],
                'shape_id': trip['shape_id'],
            })
        print(f"  Inserted {len(trips)} trips")

        # 9. Insert stop_times in batches
        print("Inserting stop_times...")
        batch_size = 5000
        for i in range(0, len(stop_times), batch_size):
            batch = stop_times[i:i+batch_size]
            for st in batch:
                db_trip_id = trip_id_mapping.get(st['trip_id'])
                if not db_trip_id:
                    continue

                session.execute(text("""
                    INSERT INTO gtfs_stop_times
                    (trip_id, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds, stop_sequence)
                    VALUES (:trip_id, :stop_id, :arrival, :departure, :arr_sec, :dep_sec, :seq)
                """), {
                    'trip_id': db_trip_id,
                    'stop_id': st['stop_id'],
                    'arrival': st['arrival_time'],
                    'departure': st['departure_time'],
                    'arr_sec': st['arrival_seconds'],
                    'dep_sec': st['departure_seconds'],
                    'seq': st['stop_sequence'],
                })
            print(f"  Inserted {min(i+batch_size, len(stop_times))}/{len(stop_times)} stop_times")

        session.commit()
        print("\nImport completed successfully!")

        # Verify
        result = session.execute(text(
            "SELECT COUNT(*) FROM gtfs_trips WHERE route_id LIKE 'ML_%'"
        ))
        print(f"\nVerification - ML trips in DB: {result.fetchone()[0]}")

        result = session.execute(text("""
            SELECT COUNT(*) FROM gtfs_stop_times st
            JOIN gtfs_trips t ON st.trip_id = t.id
            WHERE t.route_id LIKE 'ML_%'
        """))
        print(f"Verification - ML stop_times in DB: {result.fetchone()[0]}")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Import Metro Ligero GTFS data')
    parser.add_argument('gtfs_dir', help='Path to GTFS directory')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without making changes')
    args = parser.parse_args()

    import_metro_ligero(args.gtfs_dir, args.dry_run)
