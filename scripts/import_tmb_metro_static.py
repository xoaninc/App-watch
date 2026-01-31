#!/usr/bin/env python3
"""
Import TMB Metro static GTFS data (shapes, calendar_dates, transfers).

This script imports the missing static data for TMB Metro Barcelona.
It only imports Metro data (route_type=1), not buses (route_type=3).

Usage:
    python scripts/import_tmb_metro_static.py [--dry-run]

Prerequisites:
    - TMB GTFS extracted to /tmp/tmb_gtfs/
    - Database connection configured in .env.local
"""

import csv
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv('.env')  # Load database config first
load_dotenv('.env.local', override=True)  # Then override with local secrets

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'renfeserver_dev')
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

GTFS_PATH = "/tmp/tmb_gtfs"
PREFIX = "TMB_METRO_"

# Metro route IDs (from routes.txt, route_type=1 or 7 for funicular)
METRO_ROUTE_PREFIXES = ['1.1.', '1.2.', '1.3.', '1.4.', '1.5.',
                        '1.91.', '1.94.', '1.101.', '1.104.', '1.11.', '1.99.']


def is_metro_id(id_str: str) -> bool:
    """Check if an ID belongs to Metro (starts with 1.)"""
    return id_str.startswith('1.')


def import_shapes(session, dry_run=False):
    """Import Metro shapes from shapes.txt"""
    print("\n=== Importing Shapes ===")

    shapes_file = os.path.join(GTFS_PATH, "shapes.txt")
    if not os.path.exists(shapes_file):
        print("  shapes.txt not found!")
        return 0

    # Read shapes
    shapes_data = {}  # shape_id -> [(lat, lon, sequence), ...]
    with open(shapes_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            shape_id = row['shape_id']
            if not is_metro_id(shape_id):
                continue

            if shape_id not in shapes_data:
                shapes_data[shape_id] = []

            shapes_data[shape_id].append({
                'lat': float(row['shape_pt_lat']),
                'lon': float(row['shape_pt_lon']),
                'sequence': int(row['shape_pt_sequence']),
            })

    print(f"  Found {len(shapes_data)} Metro shapes")

    if dry_run:
        for shape_id in sorted(shapes_data.keys()):
            print(f"    {PREFIX}{shape_id}: {len(shapes_data[shape_id])} points")
        return len(shapes_data)

    # Delete existing TMB Metro shapes
    deleted = session.execute(text(
        "DELETE FROM gtfs_shape_points WHERE shape_id LIKE :prefix"
    ), {"prefix": f"{PREFIX}%"})
    print(f"  Deleted {deleted.rowcount} existing shape points")

    # Insert new shapes
    total_points = 0
    for shape_id, points in shapes_data.items():
        prefixed_id = f"{PREFIX}{shape_id}"
        for pt in sorted(points, key=lambda x: x['sequence']):
            session.execute(text("""
                INSERT INTO gtfs_shape_points (shape_id, lat, lon, sequence)
                VALUES (:shape_id, :lat, :lon, :sequence)
            """), {
                "shape_id": prefixed_id,
                "lat": pt['lat'],
                "lon": pt['lon'],
                "sequence": pt['sequence'],
            })
            total_points += 1

    session.commit()
    print(f"  Inserted {total_points} shape points for {len(shapes_data)} shapes")
    return len(shapes_data)


def import_calendar_dates(session, dry_run=False):
    """Import Metro calendar_dates from calendar_dates.txt"""
    print("\n=== Importing Calendar Dates ===")

    cal_file = os.path.join(GTFS_PATH, "calendar_dates.txt")
    if not os.path.exists(cal_file):
        print("  calendar_dates.txt not found!")
        return 0

    # Read calendar dates for Metro services
    dates_data = []
    with open(cal_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            service_id = row['service_id']
            if not is_metro_id(service_id):
                continue

            dates_data.append({
                'service_id': f"{PREFIX}{service_id}",
                'date': datetime.strptime(row['date'], '%Y%m%d').date(),
                'exception_type': int(row['exception_type']),
            })

    print(f"  Found {len(dates_data)} Metro calendar dates")

    if dry_run:
        # Show sample
        services = set(d['service_id'] for d in dates_data)
        print(f"  Services: {len(services)}")
        dates = set(d['date'] for d in dates_data)
        print(f"  Date range: {min(dates)} to {max(dates)}")
        return len(dates_data)

    # Delete existing TMB Metro calendar dates
    deleted = session.execute(text(
        "DELETE FROM gtfs_calendar_dates WHERE service_id LIKE :prefix"
    ), {"prefix": f"{PREFIX}%"})
    print(f"  Deleted {deleted.rowcount} existing calendar dates")

    # Insert new calendar dates
    for cd in dates_data:
        session.execute(text("""
            INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
            VALUES (:service_id, :date, :exception_type)
            ON CONFLICT (service_id, date) DO UPDATE SET
                exception_type = EXCLUDED.exception_type
        """), cd)

    session.commit()
    print(f"  Inserted {len(dates_data)} calendar dates")
    return len(dates_data)


def import_transfers(session, dry_run=False):
    """Import Metro transfers from transfers.txt"""
    print("\n=== Importing Transfers ===")

    transfers_file = os.path.join(GTFS_PATH, "transfers.txt")
    if not os.path.exists(transfers_file):
        print("  transfers.txt not found!")
        return 0

    # Read transfers
    transfers_data = []
    with open(transfers_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_stop = row['from_stop_id']
            to_stop = row['to_stop_id']

            # All transfers in TMB GTFS are Metro (1.xxx format)
            if not is_metro_id(from_stop) or not is_metro_id(to_stop):
                continue

            transfers_data.append({
                'from_stop_id': f"{PREFIX}{from_stop}",
                'to_stop_id': f"{PREFIX}{to_stop}",
                'transfer_type': int(row['transfer_type']),
                'min_transfer_time': int(row.get('min_transfer_time', 0)) if row.get('min_transfer_time') else None,
            })

    print(f"  Found {len(transfers_data)} Metro transfers")

    if dry_run:
        for t in transfers_data[:5]:
            print(f"    {t['from_stop_id']} -> {t['to_stop_id']} ({t['min_transfer_time']}s)")
        if len(transfers_data) > 5:
            print(f"    ... and {len(transfers_data) - 5} more")
        return len(transfers_data)

    # Check if line_transfer table exists
    result = session.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'line_transfer'
        )
    """)).scalar()

    if result:
        # Delete existing TMB Metro transfers from line_transfer
        deleted = session.execute(text(
            "DELETE FROM line_transfer WHERE from_stop_id LIKE :prefix OR to_stop_id LIKE :prefix"
        ), {"prefix": f"{PREFIX}%"})
        print(f"  Deleted {deleted.rowcount} existing transfers from line_transfer")

        # Insert into line_transfer
        for t in transfers_data:
            session.execute(text("""
                INSERT INTO line_transfer (from_stop_id, to_stop_id, transfer_type, min_transfer_time)
                VALUES (:from_stop_id, :to_stop_id, :transfer_type, :min_transfer_time)
                ON CONFLICT (from_stop_id, to_stop_id) DO UPDATE SET
                    transfer_type = EXCLUDED.transfer_type,
                    min_transfer_time = EXCLUDED.min_transfer_time
            """), t)
    else:
        print("  line_transfer table not found, skipping")
        return 0

    session.commit()
    print(f"  Inserted {len(transfers_data)} transfers")
    return len(transfers_data)


def update_trips_shape_ids(session, dry_run=False):
    """Update trips to reference the imported shape_ids"""
    print("\n=== Updating Trip Shape References ===")

    trips_file = os.path.join(GTFS_PATH, "trips.txt")
    if not os.path.exists(trips_file):
        print("  trips.txt not found!")
        return 0

    # Read trips with shape_ids
    trip_shapes = {}  # trip_id -> shape_id
    with open(trips_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            route_id = row['route_id']
            if not is_metro_id(route_id):
                continue

            trip_id = row['trip_id']
            shape_id = row.get('shape_id', '')
            if shape_id:
                trip_shapes[f"{PREFIX}{trip_id}"] = f"{PREFIX}{shape_id}"

    print(f"  Found {len(trip_shapes)} Metro trips with shapes")

    if dry_run:
        # Show sample
        for i, (trip, shape) in enumerate(list(trip_shapes.items())[:5]):
            print(f"    {trip} -> {shape}")
        return len(trip_shapes)

    # Update trips with shape_id
    updated = 0
    for trip_id, shape_id in trip_shapes.items():
        result = session.execute(text("""
            UPDATE gtfs_trips SET shape_id = :shape_id
            WHERE id = :trip_id
        """), {"trip_id": trip_id, "shape_id": shape_id})
        updated += result.rowcount

    session.commit()
    print(f"  Updated {updated} trips with shape references")
    return updated


def main():
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print("=== DRY RUN MODE (no changes will be made) ===")

    print(f"\nGTFS Path: {GTFS_PATH}")
    print(f"Prefix: {PREFIX}")

    # Check GTFS exists
    if not os.path.exists(GTFS_PATH):
        print(f"\nError: GTFS directory not found: {GTFS_PATH}")
        print("Please download TMB GTFS first:")
        print("  curl -sL 'https://api.tmb.cat/v1/static/datasets/gtfs.zip?app_id=XXX&app_key=XXX' -o /tmp/tmb.zip")
        print("  unzip /tmp/tmb.zip -d /tmp/tmb_gtfs")
        sys.exit(1)

    # Connect to database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        shapes_count = import_shapes(session, dry_run)
        cal_dates_count = import_calendar_dates(session, dry_run)
        transfers_count = import_transfers(session, dry_run)
        trips_updated = update_trips_shape_ids(session, dry_run)

        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)
        print(f"  Shapes: {shapes_count}")
        print(f"  Calendar dates: {cal_dates_count}")
        print(f"  Transfers: {transfers_count}")
        print(f"  Trips with shapes: {trips_updated}")

        if not dry_run:
            print("\n✅ Import completed successfully!")
        else:
            print("\n(Dry run - no changes made)")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
