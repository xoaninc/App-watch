#!/usr/bin/env python3
"""Import platform/andén data for Metro de Tenerife from OpenStreetMap.

This script:
1. Downloads platform coordinates from OSM Overpass API
2. Updates existing stops to be parent stations (location_type=1)
3. Creates platform entries (location_type=0) with parent_station_id
4. Updates stop_times to reference platforms instead of stations

Each station gets 2 platforms:
- Platform 1: Direction towards Trinidad (L1) / La Cuesta (L2)
- Platform 2: Direction towards Intercambiador (L1) / Tíncer (L2)

Usage:
    python scripts/import_metro_tenerife_platforms.py
    python scripts/import_metro_tenerife_platforms.py --dry-run
"""

import sys
import os
import json
import requests
import logging
import argparse
from collections import defaultdict
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PREFIX = 'METRO_TENERIFE_'

# Mapping from OSM stop names to our stop IDs
OSM_NAME_TO_STOP_ID = {
    'Intercambiador': 'METRO_TENERIFE_01',
    'Fundación': 'METRO_TENERIFE_02',
    'Teatro Guimerá': 'METRO_TENERIFE_03',
    'Weyler': 'METRO_TENERIFE_04',
    'La Paz': 'METRO_TENERIFE_05',
    'Puente Zurita': 'METRO_TENERIFE_06',
    'Cruz del Señor': 'METRO_TENERIFE_07',
    'Conservatorio': 'METRO_TENERIFE_08',
    'Chimisay': 'METRO_TENERIFE_09',
    'Príncipes de España': 'METRO_TENERIFE_10',
    'Hospital La Candelaria': 'METRO_TENERIFE_11',
    'Taco': 'METRO_TENERIFE_12',
    'El Cardonal': 'METRO_TENERIFE_13',
    'Hospital Universitario': 'METRO_TENERIFE_14',
    'Las Mantecas': 'METRO_TENERIFE_15',
    'Campus Guajara': 'METRO_TENERIFE_16',
    'Gracia': 'METRO_TENERIFE_17',
    'Museo de la Ciencia': 'METRO_TENERIFE_18',
    'Cruz de Piedra': 'METRO_TENERIFE_19',
    'Padre Anchieta': 'METRO_TENERIFE_20',
    'La Trinidad': 'METRO_TENERIFE_21',
    'La Cuesta': 'METRO_TENERIFE_22',
    'Ingenieros': 'METRO_TENERIFE_23',
    'San Jerónimo': 'METRO_TENERIFE_24',
    'Tíncer': 'METRO_TENERIFE_26',
}

# Which line each stop belongs to
STOP_LINES = {
    'METRO_TENERIFE_01': ['L1'],
    'METRO_TENERIFE_02': ['L1'],
    'METRO_TENERIFE_03': ['L1'],
    'METRO_TENERIFE_04': ['L1'],
    'METRO_TENERIFE_05': ['L1'],
    'METRO_TENERIFE_06': ['L1'],
    'METRO_TENERIFE_07': ['L1'],
    'METRO_TENERIFE_08': ['L1'],
    'METRO_TENERIFE_09': ['L1'],
    'METRO_TENERIFE_10': ['L1'],
    'METRO_TENERIFE_11': ['L1'],
    'METRO_TENERIFE_12': ['L1'],
    'METRO_TENERIFE_13': ['L1', 'L2'],  # Transbordo
    'METRO_TENERIFE_14': ['L1', 'L2'],  # Transbordo
    'METRO_TENERIFE_15': ['L1'],
    'METRO_TENERIFE_16': ['L1'],
    'METRO_TENERIFE_17': ['L1'],
    'METRO_TENERIFE_18': ['L1'],
    'METRO_TENERIFE_19': ['L1'],
    'METRO_TENERIFE_20': ['L1'],
    'METRO_TENERIFE_21': ['L1'],
    'METRO_TENERIFE_22': ['L2'],
    'METRO_TENERIFE_23': ['L2'],
    'METRO_TENERIFE_24': ['L2'],
    'METRO_TENERIFE_26': ['L2'],
}


def download_osm_platforms() -> Dict[str, List[Dict]]:
    """Download platform data from OSM Overpass API."""
    logger.info("Downloading platform data from OSM...")

    query = '''
    [out:json][timeout:25];
    (
      node["railway"="tram_stop"]["tram"="yes"](28.44,-16.32,28.49,-16.24);
    );
    out body;
    '''

    response = requests.post(
        'https://overpass-api.de/api/interpreter',
        data=query,
        timeout=30
    )
    response.raise_for_status()
    data = response.json()

    # Group by name
    by_name = defaultdict(list)
    for element in data['elements']:
        if element['type'] == 'node' and 'tags' in element:
            name = element['tags'].get('name', '')
            if name:
                by_name[name].append({
                    'osm_id': element['id'],
                    'lat': element['lat'],
                    'lon': element['lon'],
                    'wheelchair': element['tags'].get('wheelchair'),
                })

    logger.info(f"Downloaded {sum(len(v) for v in by_name.values())} platforms for {len(by_name)} stops")
    return dict(by_name)


def determine_platform_direction(platforms: List[Dict], stop_id: str) -> List[Dict]:
    """Determine which platform is for which direction based on coordinates.

    For L1 stops:
    - Platform with larger longitude (more east) = direction 0 (towards Trinidad)
    - Platform with smaller longitude (more west) = direction 1 (towards Intercambiador)

    For L2 stops:
    - Platform with larger longitude = direction 0 (towards Tíncer)
    - Platform with smaller longitude = direction 1 (towards La Cuesta)

    Actually, looking at the geography, Trinidad is to the WEST and Intercambiador to the EAST.
    So for L1:
    - direction 0 (Trinidad): platform more to the west (smaller lon, or depends on track orientation)
    - direction 1 (Intercambiador): platform more to the east

    Since the tram runs roughly SW-NE, and platforms are on opposite sides:
    - We'll use a simple heuristic: sort by longitude and assign directions
    """
    if len(platforms) < 2:
        return platforms

    # Sort by longitude (west to east)
    sorted_platforms = sorted(platforms, key=lambda x: x['lon'])

    lines = STOP_LINES.get(stop_id, ['L1'])

    # For L1: direction 0 = Trinidad (west), direction 1 = Intercambiador (east)
    # Platform 1 (index 0 after sort) = more west = Trinidad direction = direction 0
    # Platform 2 (index 1 after sort) = more east = Intercambiador direction = direction 1

    result = []
    for i, p in enumerate(sorted_platforms):
        p_copy = p.copy()
        p_copy['platform_num'] = i + 1

        if 'L1' in lines:
            # Direction 0 = Trinidad (more west platform)
            # Direction 1 = Intercambiador (more east platform)
            p_copy['direction'] = i  # 0 for west, 1 for east
            p_copy['headsign'] = 'Trinidad' if i == 0 else 'Intercambiador'
        elif 'L2' in lines:
            # Direction 0 = Tíncer (more west for most of L2)
            # Direction 1 = La Cuesta (more east)
            p_copy['direction'] = i
            p_copy['headsign'] = 'Tíncer' if i == 0 else 'La Cuesta'

        result.append(p_copy)

    return result


def import_platforms(db, osm_data: Dict[str, List[Dict]], dry_run: bool = False):
    """Import platforms into the database."""

    # Get existing stops
    result = db.execute(text(
        "SELECT id, name, lat, lon, wheelchair_boarding FROM gtfs_stops WHERE id LIKE 'METRO_TENERIFE_%' AND id NOT LIKE '%%.%%'"
    )).fetchall()

    existing_stops = {row[0]: {'name': row[1], 'lat': row[2], 'lon': row[3], 'wheelchair': row[4]} for row in result}
    logger.info(f"Found {len(existing_stops)} existing Metro Tenerife stops")

    # Check if platforms already exist
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_stops WHERE id LIKE 'METRO_TENERIFE_%%.%%'"
    )).scalar()

    if result > 0:
        logger.warning(f"Found {result} existing platforms. Clearing them first...")
        if not dry_run:
            # Update stop_times to use parent stations
            db.execute(text("""
                UPDATE gtfs_stop_times
                SET stop_id = SPLIT_PART(stop_id, '.', 1)
                WHERE stop_id LIKE 'METRO_TENERIFE_%%.%%'
            """))
            db.commit()

            # Delete existing platforms
            db.execute(text("DELETE FROM gtfs_stops WHERE id LIKE 'METRO_TENERIFE_%%.%%'"))
            db.commit()
            logger.info("Cleared existing platforms")

    platforms_to_create = []
    stops_to_update = []

    for osm_name, platforms in osm_data.items():
        stop_id = OSM_NAME_TO_STOP_ID.get(osm_name)
        if not stop_id:
            logger.warning(f"Unknown OSM stop name: {osm_name}")
            continue

        if stop_id not in existing_stops:
            logger.warning(f"Stop {stop_id} not found in database")
            continue

        stop_info = existing_stops[stop_id]

        # Determine platform directions
        platforms_with_dir = determine_platform_direction(platforms, stop_id)

        # Mark parent station for update
        stops_to_update.append({
            'id': stop_id,
            'location_type': 1,  # Station
        })

        # Create platform entries
        for p in platforms_with_dir:
            platform_id = f"{stop_id}.{p['platform_num']}"

            # Determine wheelchair from OSM or inherit from parent
            wheelchair = 1 if p.get('wheelchair') == 'yes' else (stop_info.get('wheelchair') or 1)

            # Platform code based on direction
            if 'L1' in STOP_LINES.get(stop_id, []):
                platform_code = f"Dir. {p.get('headsign', 'Trinidad' if p['platform_num'] == 1 else 'Intercambiador')}"
            else:
                platform_code = f"Dir. {p.get('headsign', 'Tíncer' if p['platform_num'] == 1 else 'La Cuesta')}"

            platforms_to_create.append({
                'id': platform_id,
                'name': f"{stop_info['name']} - Andén {p['platform_num']}",
                'lat': p['lat'],
                'lon': p['lon'],
                'location_type': 0,  # Platform/Stop
                'parent_station_id': stop_id,
                'wheelchair_boarding': wheelchair,
                'platform_code': platform_code,
            })

    logger.info(f"Will create {len(platforms_to_create)} platforms for {len(stops_to_update)} stations")

    if dry_run:
        print("\n=== DRY RUN - No changes made ===")
        print(f"\nStations to update: {len(stops_to_update)}")
        print(f"Platforms to create: {len(platforms_to_create)}")
        print("\nSample platforms:")
        for p in platforms_to_create[:6]:
            print(f"  {p['id']}: {p['name']} ({p['lat']}, {p['lon']}) - {p['platform_code']}")
        return

    # Update existing stops to be stations
    logger.info("Updating stops to be parent stations...")
    for stop in stops_to_update:
        db.execute(
            text("UPDATE gtfs_stops SET location_type = :location_type WHERE id = :id"),
            stop
        )
    db.commit()

    # Insert platforms
    logger.info("Creating platforms...")
    for p in platforms_to_create:
        db.execute(
            text("""
                INSERT INTO gtfs_stops
                (id, name, lat, lon, location_type, parent_station_id, wheelchair_boarding, platform_code)
                VALUES (:id, :name, :lat, :lon, :location_type, :parent_station_id, :wheelchair_boarding, :platform_code)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    lat = EXCLUDED.lat,
                    lon = EXCLUDED.lon,
                    location_type = EXCLUDED.location_type,
                    parent_station_id = EXCLUDED.parent_station_id,
                    wheelchair_boarding = EXCLUDED.wheelchair_boarding,
                    platform_code = EXCLUDED.platform_code
            """),
            p
        )
    db.commit()

    logger.info(f"Created {len(platforms_to_create)} platforms")

    # Update stop_times to use platforms based on direction
    logger.info("Updating stop_times to reference platforms...")

    # For each trip, determine direction and update stop_times
    result = db.execute(text("""
        SELECT DISTINCT t.id, t.direction_id, t.route_id
        FROM gtfs_trips t
        WHERE t.route_id LIKE 'METRO_TENERIFE_%'
    """)).fetchall()

    trips_by_direction = defaultdict(list)
    for row in result:
        trip_id, direction_id, route_id = row
        trips_by_direction[(route_id, direction_id)].append(trip_id)

    update_count = 0
    for (route_id, direction_id), trip_ids in trips_by_direction.items():
        # Platform number based on direction
        # direction 0 = platform 1, direction 1 = platform 2
        platform_num = direction_id + 1

        for trip_id in trip_ids:
            # Get stop_times for this trip
            result = db.execute(text("""
                SELECT stop_id FROM gtfs_stop_times
                WHERE trip_id = :trip_id
            """), {'trip_id': trip_id}).fetchall()

            for row in result:
                old_stop_id = row[0]
                if '.' not in old_stop_id:  # Only update if not already a platform
                    new_stop_id = f"{old_stop_id}.{platform_num}"

                    # Check if platform exists
                    exists = db.execute(text(
                        "SELECT 1 FROM gtfs_stops WHERE id = :id"
                    ), {'id': new_stop_id}).scalar()

                    if exists:
                        db.execute(text("""
                            UPDATE gtfs_stop_times
                            SET stop_id = :new_stop_id
                            WHERE trip_id = :trip_id AND stop_id = :old_stop_id
                        """), {
                            'new_stop_id': new_stop_id,
                            'trip_id': trip_id,
                            'old_stop_id': old_stop_id
                        })
                        update_count += 1

        db.commit()

    logger.info(f"Updated {update_count} stop_time entries to use platforms")

    # Summary
    print("\n" + "=" * 70)
    print("IMPORT SUMMARY - Metro Tenerife Platforms")
    print("=" * 70)
    print(f"Stations updated: {len(stops_to_update)}")
    print(f"Platforms created: {len(platforms_to_create)}")
    print(f"Stop times updated: {update_count}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Import Metro Tenerife platforms from OSM')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()

    # Download OSM data
    osm_data = download_osm_platforms()

    if not osm_data:
        logger.error("No OSM data downloaded")
        sys.exit(1)

    # Import to database
    db = SessionLocal()
    try:
        import_platforms(db, osm_data, dry_run=args.dry_run)
    except Exception as e:
        db.rollback()
        logger.error(f"Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
