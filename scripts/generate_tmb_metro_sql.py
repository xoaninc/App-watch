#!/usr/bin/env python3
"""
Generate SQL files for TMB Metro static GTFS data import.

This script generates SQL files that can be executed on the server.
It reads from the extracted TMB GTFS files and creates:
- tmb_metro_shapes.sql
- tmb_metro_calendar_dates.sql
- tmb_metro_transfers.sql
- tmb_metro_trip_shapes.sql

Usage:
    python scripts/generate_tmb_metro_sql.py

Output:
    /tmp/tmb_metro_sql/*.sql files
"""

import csv
import os
from datetime import datetime

GTFS_PATH = "/tmp/tmb_gtfs"
OUTPUT_PATH = "/tmp/tmb_metro_sql"
PREFIX = "TMB_METRO_"


def is_metro_id(id_str: str) -> bool:
    """Check if an ID belongs to Metro (starts with 1.)"""
    return id_str.startswith('1.')


def escape_sql(s: str) -> str:
    """Escape single quotes for SQL"""
    return s.replace("'", "''") if s else ""


def generate_shapes_sql():
    """Generate SQL for Metro shapes"""
    print("\n=== Generating Shapes SQL ===")

    shapes_file = os.path.join(GTFS_PATH, "shapes.txt")
    if not os.path.exists(shapes_file):
        print("  shapes.txt not found!")
        return

    # Read shapes
    shapes_data = {}
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

    # Generate SQL
    output_file = os.path.join(OUTPUT_PATH, "tmb_metro_shapes.sql")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- TMB Metro Shapes Import\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n")
        f.write(f"-- Total shapes: {len(shapes_data)}\n\n")

        f.write("-- Delete existing TMB Metro shape points\n")
        f.write(f"DELETE FROM gtfs_shape_points WHERE shape_id LIKE '{PREFIX}%';\n")
        f.write("-- Delete existing TMB Metro shapes\n")
        f.write(f"DELETE FROM gtfs_shapes WHERE id LIKE '{PREFIX}%';\n\n")

        f.write("-- Insert shape definitions first (for foreign key)\n")
        for shape_id in sorted(shapes_data.keys()):
            prefixed_id = f"{PREFIX}{shape_id}"
            f.write(f"INSERT INTO gtfs_shapes (id) VALUES ('{prefixed_id}') ON CONFLICT (id) DO NOTHING;\n")

        f.write("\n-- Insert shape points\n")
        total_points = 0
        for shape_id, points in sorted(shapes_data.items()):
            prefixed_id = f"{PREFIX}{shape_id}"
            for pt in sorted(points, key=lambda x: x['sequence']):
                f.write(f"INSERT INTO gtfs_shape_points (shape_id, lat, lon, sequence) VALUES ('{prefixed_id}', {pt['lat']}, {pt['lon']}, {pt['sequence']});\n")
                total_points += 1

        f.write(f"\n-- Total shapes: {len(shapes_data)}, points: {total_points}\n")

    print(f"  Generated {output_file} with {total_points} points")


def generate_calendar_dates_sql():
    """Generate SQL for Metro calendar_dates"""
    print("\n=== Generating Calendar Dates SQL ===")

    cal_file = os.path.join(GTFS_PATH, "calendar_dates.txt")
    if not os.path.exists(cal_file):
        print("  calendar_dates.txt not found!")
        return

    # Read calendar dates
    dates_data = []
    with open(cal_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            service_id = row['service_id']
            if not is_metro_id(service_id):
                continue

            dates_data.append({
                'service_id': f"{PREFIX}{service_id}",
                'date': datetime.strptime(row['date'], '%Y%m%d').strftime('%Y-%m-%d'),
                'exception_type': int(row['exception_type']),
            })

    print(f"  Found {len(dates_data)} Metro calendar dates")

    # Generate SQL
    output_file = os.path.join(OUTPUT_PATH, "tmb_metro_calendar_dates.sql")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- TMB Metro Calendar Dates Import\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n")
        f.write(f"-- Total entries: {len(dates_data)}\n\n")

        f.write("-- Delete existing TMB Metro calendar dates\n")
        f.write(f"DELETE FROM gtfs_calendar_dates WHERE service_id LIKE '{PREFIX}%';\n\n")

        f.write("-- Insert new calendar dates\n")
        for cd in dates_data:
            f.write(f"INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES ('{cd['service_id']}', '{cd['date']}', {cd['exception_type']}) ON CONFLICT (service_id, date) DO UPDATE SET exception_type = EXCLUDED.exception_type;\n")

    print(f"  Generated {output_file}")


def generate_transfers_sql():
    """Generate SQL for Metro transfers"""
    print("\n=== Generating Transfers SQL ===")

    transfers_file = os.path.join(GTFS_PATH, "transfers.txt")
    if not os.path.exists(transfers_file):
        print("  transfers.txt not found!")
        return

    # Read transfers
    transfers_data = []
    with open(transfers_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_stop = row['from_stop_id']
            to_stop = row['to_stop_id']

            if not is_metro_id(from_stop) or not is_metro_id(to_stop):
                continue

            min_time = row.get('min_transfer_time', '')
            transfers_data.append({
                'from_stop_id': f"{PREFIX}{from_stop}",
                'to_stop_id': f"{PREFIX}{to_stop}",
                'transfer_type': int(row['transfer_type']),
                'min_transfer_time': int(min_time) if min_time else 'NULL',
            })

    print(f"  Found {len(transfers_data)} Metro transfers")

    # Generate SQL
    output_file = os.path.join(OUTPUT_PATH, "tmb_metro_transfers.sql")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- TMB Metro Transfers Import\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n")
        f.write(f"-- Total entries: {len(transfers_data)}\n\n")

        f.write("-- Delete existing TMB Metro transfers (from line_transfer table)\n")
        f.write(f"DELETE FROM line_transfer WHERE from_stop_id LIKE '{PREFIX}%' OR to_stop_id LIKE '{PREFIX}%';\n\n")

        f.write("-- Insert new transfers\n")
        for t in transfers_data:
            f.write(f"INSERT INTO line_transfer (from_stop_id, to_stop_id, transfer_type, min_transfer_time) VALUES ('{t['from_stop_id']}', '{t['to_stop_id']}', {t['transfer_type']}, {t['min_transfer_time']});\n")

    print(f"  Generated {output_file}")


def generate_trip_shapes_sql():
    """Generate SQL for updating trips with shape_ids"""
    print("\n=== Generating Trip Shapes SQL ===")

    trips_file = os.path.join(GTFS_PATH, "trips.txt")
    if not os.path.exists(trips_file):
        print("  trips.txt not found!")
        return

    # Read trips with shape_ids
    trip_shapes = {}
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

    # Generate SQL
    output_file = os.path.join(OUTPUT_PATH, "tmb_metro_trip_shapes.sql")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- TMB Metro Trip Shape References Update\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n")
        f.write(f"-- Total updates: {len(trip_shapes)}\n\n")

        f.write("-- Update trips with shape references\n")
        for trip_id, shape_id in sorted(trip_shapes.items()):
            f.write(f"UPDATE gtfs_trips SET shape_id = '{shape_id}' WHERE id = '{trip_id}';\n")

    print(f"  Generated {output_file}")


def main():
    print(f"GTFS Path: {GTFS_PATH}")
    print(f"Output Path: {OUTPUT_PATH}")
    print(f"Prefix: {PREFIX}")

    # Check GTFS exists
    if not os.path.exists(GTFS_PATH):
        print(f"\nError: GTFS directory not found: {GTFS_PATH}")
        return

    # Create output directory
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    generate_shapes_sql()
    generate_calendar_dates_sql()
    generate_transfers_sql()
    generate_trip_shapes_sql()

    print("\n" + "=" * 50)
    print("SQL files generated successfully!")
    print("=" * 50)
    print(f"\nFiles are in: {OUTPUT_PATH}/")
    print("\nTo import on the server, run:")
    print("  psql -d renfeserver -f /tmp/tmb_metro_sql/tmb_metro_shapes.sql")
    print("  psql -d renfeserver -f /tmp/tmb_metro_sql/tmb_metro_calendar_dates.sql")
    print("  psql -d renfeserver -f /tmp/tmb_metro_sql/tmb_metro_transfers.sql")
    print("  psql -d renfeserver -f /tmp/tmb_metro_sql/tmb_metro_trip_shapes.sql")


if __name__ == "__main__":
    main()
