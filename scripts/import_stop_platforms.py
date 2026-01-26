#!/usr/bin/env python3
"""
Import platform coordinates from OSM CSV files into stop_platform table.

This script reads platform coordinates from OSM CSV files and imports them
into the stop_platform table. It matches platform data to stops by name.

Usage:
    .venv/bin/python scripts/import_stop_platforms.py

Data sources:
    - docs/osm_coords/metro_madrid_by_line.csv
    - docs/osm_coords/metro_bcn_by_line.csv
    - docs/osm_coords/metro_bilbao_by_line.csv
    - (add more as they are extracted)

CSV format:
    station_name,line,lat,lon
    Nuevos Ministerios,L6,40.4452235,-3.6913658
"""
import csv
import os
import sys
import unicodedata
import re
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import SessionLocal


def normalize_name(name: str) -> str:
    """Normalize station name for matching."""
    # Remove accents
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    # Lowercase
    name = name.lower().strip()
    # Remove common prefixes
    name = re.sub(r'^(estacion de |estacio de |estacio |station |parada )', '', name)
    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name)
    return name


def get_stop_id_by_name(session, name: str, network_prefixes: list) -> str | None:
    """Find stop_id by normalized name and network prefix."""
    normalized = normalize_name(name)

    # Try to find matching stop
    for prefix in network_prefixes:
        result = session.execute(
            text("""
                SELECT id, name FROM gtfs_stops
                WHERE id LIKE :prefix
                ORDER BY id
            """),
            {"prefix": f"{prefix}%"}
        ).fetchall()

        for stop_id, stop_name in result:
            if normalize_name(stop_name) == normalized:
                return stop_id

    return None


def import_from_csv(session, csv_path: str, network_prefixes: list, source: str = 'osm'):
    """Import platforms from a CSV file."""
    if not os.path.exists(csv_path):
        print(f"  [SKIP] File not found: {csv_path}")
        return 0

    imported = 0
    skipped = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            station_name = row['station_name']
            lines = row['line']  # CSV has 'line' column, we store as 'lines'
            lat = float(row['lat'])
            lon = float(row['lon'])

            # Skip Unknown lines
            if lines == 'Unknown':
                skipped += 1
                continue

            # Find stop_id
            stop_id = get_stop_id_by_name(session, station_name, network_prefixes)

            if not stop_id:
                # Try to find any stop with similar name
                result = session.execute(
                    text("""
                        SELECT id FROM gtfs_stops
                        WHERE LOWER(name) LIKE :pattern
                        LIMIT 1
                    """),
                    {"pattern": f"%{normalize_name(station_name)}%"}
                ).fetchone()

                if result:
                    stop_id = result[0]

            if not stop_id:
                print(f"  [WARN] No stop found for: {station_name}")
                skipped += 1
                continue

            # Insert or update platform
            try:
                session.execute(
                    text("""
                        INSERT INTO stop_platform (stop_id, lines, lat, lon, source)
                        VALUES (:stop_id, :lines, :lat, :lon, :source)
                        ON CONFLICT (stop_id, lines) DO UPDATE SET
                            lat = :lat,
                            lon = :lon,
                            source = :source
                    """),
                    {
                        "stop_id": stop_id,
                        "lines": lines,
                        "lat": lat,
                        "lon": lon,
                        "source": source
                    }
                )
                imported += 1
            except Exception as e:
                print(f"  [ERROR] {station_name} {lines}: {e}")
                skipped += 1

    session.commit()
    return imported


def main():
    print("=" * 60)
    print("Import Stop Platforms from OSM")
    print("=" * 60)

    # Connect to database
    session = SessionLocal()

    # Define CSV files and their network prefixes
    csv_files = [
        {
            "path": "docs/osm_coords/metro_madrid_by_line.csv",
            "prefixes": ["METRO_", "11T"],  # Metro Madrid
            "name": "Metro Madrid"
        },
        {
            "path": "docs/osm_coords/metro_bcn_by_line.csv",
            "prefixes": ["TMB_METRO_", "FGC_"],  # Metro Barcelona + FGC
            "name": "Metro Barcelona"
        },
        {
            "path": "docs/osm_coords/metro_bilbao_by_line.csv",
            "prefixes": ["METRO_BILBAO_"],
            "name": "Metro Bilbao"
        },
    ]

    total_imported = 0

    for csv_info in csv_files:
        print(f"\n[{csv_info['name']}]")
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            csv_info['path']
        )
        count = import_from_csv(session, csv_path, csv_info['prefixes'])
        print(f"  Imported: {count} platforms")
        total_imported += count

    print(f"\n{'=' * 60}")
    print(f"Total imported: {total_imported} platforms")
    print("=" * 60)

    # Show summary
    result = session.execute(text("""
        SELECT
            CASE
                WHEN stop_id LIKE 'METRO\\_%' AND stop_id NOT LIKE 'METRO\\_BILBAO%' THEN 'Metro Madrid'
                WHEN stop_id LIKE 'TMB_METRO%' THEN 'TMB Metro'
                WHEN stop_id LIKE 'FGC%' THEN 'FGC'
                WHEN stop_id LIKE 'METRO_BILBAO%' THEN 'Metro Bilbao'
                ELSE 'Otro'
            END as network,
            COUNT(*) as platforms,
            COUNT(DISTINCT stop_id) as stops
        FROM stop_platform
        GROUP BY 1
        ORDER BY 2 DESC
    """)).fetchall()

    print("\nPlatforms by network:")
    for row in result:
        print(f"  {row[0]}: {row[1]} platforms in {row[2]} stops")

    session.close()


if __name__ == "__main__":
    main()
