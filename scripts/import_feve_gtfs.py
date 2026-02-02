#!/usr/bin/env python3
"""Import GTFS data from RENFE FEVE feed (separate from Cercanías).

This script imports the FEVE (Ferrocarriles de Vía Estrecha) lines that are NOT
included in the main fomento_transit.zip file:
- 45T: Cartagena - Los Nietos (Murcia)
- 46T: Ferrol - Ortigueira (Galicia)
- 47T: León - Cistierna (León)

Usage:
    # Import all FEVE networks
    python scripts/import_feve_gtfs.py /path/to/RENFE_FEVE/

    # Import specific network
    python scripts/import_feve_gtfs.py /path/to/RENFE_FEVE/ --network 46T

    # List available networks
    python scripts/import_feve_gtfs.py /path/to/RENFE_FEVE/ --list-networks

Note: The FEVE GTFS is distributed as a separate folder, not a zip file.
Download from: https://ssl.renfe.com/ftransit/Fichero_FEVE_FOMENTO/
"""

import sys
import os
import csv
import logging
import argparse
from datetime import datetime
from typing import Optional
from sqlalchemy import text
from core.database import SessionLocal, engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FEVE Network definitions
FEVE_NETWORKS = {
    '45T': {
        'name': 'Cartagena - Los Nietos',
        'region': 'Murcia',
        'lines': ['C4'],
        'province': 'Murcia',
        'color': '00FFFF',  # Cyan - FEVE Cartagena
        'text_color': '000000',
    },
    '46T': {
        'name': 'Ferrol - Ortigueira',
        'region': 'Galicia',
        'lines': ['C1'],
        'province': 'A Coruña',
        'color': '00FF00',  # Green - FEVE Ferrol
        'text_color': '000000',
    },
    '47T': {
        'name': 'León - Cistierna',
        'region': 'León',
        'lines': ['C1', 'BUS'],
        'province': 'León',
        'color': 'FF6600',  # Orange - FEVE León
        'text_color': 'FFFFFF',
    },
}

BATCH_SIZE = 5000


def time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS to seconds since midnight."""
    parts = time_str.strip().split(':')
    if len(parts) != 3:
        return 0
    hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def parse_date(date_str: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD."""
    date_str = date_str.strip()
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


def normalize_stop_id(stop_id: str) -> str:
    """Normalize stop_id to handle leading zeros.

    FEVE uses stop_ids like '05102' but we store as 'RENFE_5102'.
    This function handles both formats.
    """
    # Strip leading zeros but keep at least one digit
    normalized = stop_id.lstrip('0') or '0'
    return normalized


def read_csv_file(folder_path: str, filename: str):
    """Read a CSV file from the GTFS folder."""
    filepath = os.path.join(folder_path, filename)
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        return list(reader)


def list_networks(folder_path: str):
    """List available networks in the FEVE GTFS."""
    routes = read_csv_file(folder_path, 'routes.txt')

    networks_found = {}
    for route in routes:
        route_id = route['route_id'].strip()
        network_id = route_id[:3]  # e.g., '45T', '46T', '47T'

        if network_id not in networks_found:
            networks_found[network_id] = {
                'routes': [],
                'info': FEVE_NETWORKS.get(network_id, {'name': 'Unknown', 'region': 'Unknown'})
            }
        networks_found[network_id]['routes'].append({
            'id': route_id,
            'short_name': route['route_short_name'].strip(),
            'long_name': route['route_long_name'].strip(),
        })

    print("\nFEVE Networks available:")
    print("=" * 60)
    for network_id, data in sorted(networks_found.items()):
        info = data['info']
        print(f"\n{network_id}: {info['name']} ({info['region']})")
        for route in data['routes']:
            print(f"  - {route['short_name']}: {route['long_name']}")
    print()


def import_networks(db, network_filter: str = None) -> int:
    """Create FEVE networks in gtfs_networks table."""
    logger.info("Creating FEVE networks...")

    imported = 0
    for network_id, info in FEVE_NETWORKS.items():
        if network_filter and network_id != network_filter:
            continue

        db.execute(
            text("""
                INSERT INTO gtfs_networks (code, name, region, color, text_color)
                VALUES (:code, :name, :region, :color, :text_color)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    region = EXCLUDED.region,
                    color = EXCLUDED.color,
                    text_color = EXCLUDED.text_color
            """),
            {
                'code': network_id,
                'name': f"Cercanías {info['name']}",
                'region': info['region'],
                'color': info['color'],
                'text_color': info['text_color'],
            }
        )
        imported += 1

    db.commit()
    logger.info(f"Created {imported} networks")
    return imported


def import_stops(db, folder_path: str, network_filter: str = None) -> int:
    """Import stops from FEVE GTFS."""
    logger.info("Importing FEVE stops...")

    stops = read_csv_file(folder_path, 'stops.txt')
    routes = read_csv_file(folder_path, 'routes.txt')
    trips = read_csv_file(folder_path, 'trips.txt')
    stop_times = read_csv_file(folder_path, 'stop_times.txt')

    # Build route_id -> network_id mapping
    route_to_network = {}
    for route in routes:
        route_id = route['route_id'].strip()
        network_id = route_id[:3]
        route_to_network[route_id] = network_id

    # Build trip_id -> network_id mapping
    trip_to_network = {}
    for trip in trips:
        trip_id = trip['trip_id'].strip()
        route_id = trip['route_id'].strip()
        trip_to_network[trip_id] = route_to_network.get(route_id)

    # Find which stops belong to which network
    stop_networks = {}
    for st in stop_times:
        trip_id = st['trip_id'].strip()
        stop_id = st['stop_id'].strip()
        network_id = trip_to_network.get(trip_id)
        if network_id:
            if stop_id not in stop_networks:
                stop_networks[stop_id] = set()
            stop_networks[stop_id].add(network_id)

    # Get existing stops
    existing = set()
    result = db.execute(text("SELECT id FROM gtfs_stops WHERE id LIKE 'RENFE_%'"))
    for row in result:
        existing.add(row[0])

    # Import stops
    imported = 0
    skipped = 0

    for stop in stops:
        gtfs_stop_id = stop['stop_id'].strip()

        # Filter by network if specified
        if network_filter:
            networks = stop_networks.get(gtfs_stop_id, set())
            if network_filter not in networks:
                continue

        # Normalize stop_id (handle leading zeros)
        normalized_id = normalize_stop_id(gtfs_stop_id)
        our_stop_id = f"RENFE_{normalized_id}"

        # Skip if already exists
        if our_stop_id in existing:
            skipped += 1
            continue

        # Get province from network
        networks = stop_networks.get(gtfs_stop_id, set())
        province = None
        for net_id in networks:
            if net_id in FEVE_NETWORKS:
                province = FEVE_NETWORKS[net_id]['province']
                break

        # Clean up stop name
        stop_name = stop.get('stop_name', '').strip()
        stop_name = stop_name.replace('Estación de tren ', '').title()

        lat = float(stop.get('stop_lat', '0').strip() or '0')
        lon = float(stop.get('stop_lon', '0').strip() or '0')

        db.execute(
            text("""
                INSERT INTO gtfs_stops (id, name, lat, lon, location_type, province)
                VALUES (:id, :name, :lat, :lon, 0, :province)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    lat = EXCLUDED.lat,
                    lon = EXCLUDED.lon,
                    province = EXCLUDED.province
            """),
            {
                'id': our_stop_id,
                'name': stop_name,
                'lat': lat,
                'lon': lon,
                'province': province,
            }
        )
        imported += 1
        existing.add(our_stop_id)

    db.commit()
    logger.info(f"Imported {imported} stops, skipped {skipped} (already exist)")
    return imported


def import_routes(db, folder_path: str, network_filter: str = None) -> dict:
    """Import routes from FEVE GTFS."""
    logger.info("Importing FEVE routes...")

    routes = read_csv_file(folder_path, 'routes.txt')
    route_mapping = {}
    imported = 0

    for route in routes:
        gtfs_route_id = route['route_id'].strip()
        network_id = gtfs_route_id[:3]

        # Filter by network if specified
        if network_filter and network_id != network_filter:
            continue

        short_name = route['route_short_name'].strip()
        long_name = route['route_long_name'].strip()
        color = route.get('route_color', '00FFFF').strip() or '00FFFF'
        text_color = route.get('route_text_color', 'FFFFFF').strip() or 'FFFFFF'

        # Create our route_id
        our_route_id = f"RENFE_{short_name}_{network_id}"
        route_mapping[gtfs_route_id] = our_route_id

        # Determine route type name
        if short_name == 'BUS':
            type_name = 'bus'
        else:
            type_name = 'cercanias'

        db.execute(
            text("""
                INSERT INTO gtfs_routes (id, agency_id, short_name, long_name, route_type, color, text_color, network_id)
                VALUES (:id, :agency_id, :short_name, :long_name, 2, :color, :text_color, :network_id)
                ON CONFLICT (id) DO UPDATE SET
                    short_name = EXCLUDED.short_name,
                    long_name = EXCLUDED.long_name,
                    color = EXCLUDED.color,
                    text_color = EXCLUDED.text_color,
                    network_id = EXCLUDED.network_id
            """),
            {
                'id': our_route_id,
                'agency_id': '1071VC',  # Same as other RENFE routes
                'short_name': short_name,
                'long_name': long_name.strip(),
                'color': color,
                'text_color': text_color,
                'network_id': network_id,
            }
        )
        imported += 1

    db.commit()
    logger.info(f"Imported {imported} routes")
    return route_mapping


def import_calendar(db, folder_path: str, network_filter: str = None) -> set:
    """Import calendar from FEVE GTFS."""
    logger.info("Importing FEVE calendar...")

    calendar = read_csv_file(folder_path, 'calendar.txt')
    trips = read_csv_file(folder_path, 'trips.txt')
    routes = read_csv_file(folder_path, 'routes.txt')

    # Build route_id -> network_id mapping
    route_to_network = {}
    for route in routes:
        route_id = route['route_id'].strip()
        network_id = route_id[:3]
        route_to_network[route_id] = network_id

    # Find which service_ids belong to which network
    service_networks = {}
    for trip in trips:
        service_id = trip['service_id'].strip()
        route_id = trip['route_id'].strip()
        network_id = route_to_network.get(route_id)
        if network_id:
            if service_id not in service_networks:
                service_networks[service_id] = set()
            service_networks[service_id].add(network_id)

    imported = 0
    service_ids = set()

    for cal in calendar:
        service_id = cal['service_id'].strip()

        # Filter by network if specified
        if network_filter:
            networks = service_networks.get(service_id, set())
            if network_filter not in networks:
                continue

        service_ids.add(service_id)

        db.execute(
            text("""
                INSERT INTO gtfs_calendar
                (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                VALUES (:service_id, :monday, :tuesday, :wednesday, :thursday, :friday, :saturday, :sunday, :start_date, :end_date)
                ON CONFLICT (service_id) DO UPDATE SET
                    monday = EXCLUDED.monday,
                    tuesday = EXCLUDED.tuesday,
                    wednesday = EXCLUDED.wednesday,
                    thursday = EXCLUDED.thursday,
                    friday = EXCLUDED.friday,
                    saturday = EXCLUDED.saturday,
                    sunday = EXCLUDED.sunday,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date
            """),
            {
                'service_id': service_id,
                'monday': cal['monday'].strip() == '1',
                'tuesday': cal['tuesday'].strip() == '1',
                'wednesday': cal['wednesday'].strip() == '1',
                'thursday': cal['thursday'].strip() == '1',
                'friday': cal['friday'].strip() == '1',
                'saturday': cal['saturday'].strip() == '1',
                'sunday': cal['sunday'].strip() == '1',
                'start_date': parse_date(cal['start_date']),
                'end_date': parse_date(cal['end_date']),
            }
        )
        imported += 1

    db.commit()
    logger.info(f"Imported {imported} calendar entries")
    return service_ids


def import_trips(db, folder_path: str, route_mapping: dict, network_filter: str = None) -> set:
    """Import trips from FEVE GTFS."""
    logger.info("Importing FEVE trips...")

    trips = read_csv_file(folder_path, 'trips.txt')
    stop_times_data = read_csv_file(folder_path, 'stop_times.txt')
    stops = read_csv_file(folder_path, 'stops.txt')

    # Build stop_id -> name mapping
    stop_names = {}
    for stop in stops:
        stop_id = stop['stop_id'].strip()
        name = stop.get('stop_name', '').strip()
        name = name.replace('Estación de tren ', '').title()
        stop_names[stop_id] = name

    # Find last stop for each trip (for headsign)
    trip_last_stop = {}
    for st in stop_times_data:
        trip_id = st['trip_id'].strip()
        stop_id = st['stop_id'].strip()
        sequence = int(st['stop_sequence'].strip())

        if trip_id not in trip_last_stop or sequence > trip_last_stop[trip_id][0]:
            trip_last_stop[trip_id] = (sequence, stop_id)

    # Generate headsigns
    trip_headsigns = {}
    for trip_id, (_, stop_id) in trip_last_stop.items():
        trip_headsigns[trip_id] = stop_names.get(stop_id, '')

    imported = 0
    trip_ids = set()

    for trip in trips:
        trip_id = trip['trip_id'].strip()
        gtfs_route_id = trip['route_id'].strip()
        service_id = trip['service_id'].strip()

        # Skip if route not in our mapping (filtered out)
        if gtfs_route_id not in route_mapping:
            continue

        our_route_id = route_mapping[gtfs_route_id]
        headsign = trip_headsigns.get(trip_id, '')

        db.execute(
            text("""
                INSERT INTO gtfs_trips (id, route_id, service_id, headsign, direction_id)
                VALUES (:id, :route_id, :service_id, :headsign, :direction_id)
                ON CONFLICT (id) DO UPDATE SET
                    route_id = EXCLUDED.route_id,
                    service_id = EXCLUDED.service_id,
                    headsign = EXCLUDED.headsign
            """),
            {
                'id': trip_id,
                'route_id': our_route_id,
                'service_id': service_id,
                'headsign': headsign,
                'direction_id': int(trip.get('direction_id', '0').strip() or '0'),
            }
        )
        trip_ids.add(trip_id)
        imported += 1

    db.commit()
    logger.info(f"Imported {imported} trips")
    return trip_ids


def import_stop_times(db, folder_path: str, trip_ids: set) -> int:
    """Import stop_times from FEVE GTFS."""
    logger.info("Importing FEVE stop_times...")

    stop_times = read_csv_file(folder_path, 'stop_times.txt')

    # Build stop mapping with leading zero handling
    stop_mapping = {}
    result = db.execute(text("SELECT id FROM gtfs_stops WHERE id LIKE 'RENFE_%'"))
    for row in result:
        our_id = row[0]
        gtfs_id = our_id.replace('RENFE_', '')
        stop_mapping[gtfs_id] = our_id
        # Also map with leading zeros
        stop_mapping[gtfs_id.lstrip('0') or '0'] = our_id
        stop_mapping[gtfs_id.zfill(5)] = our_id

    logger.info(f"Built stop mapping with {len(stop_mapping)} entries")

    rows = []
    imported = 0
    skipped_trip = 0
    skipped_stop = 0

    for st in stop_times:
        trip_id = st['trip_id'].strip()
        gtfs_stop_id = st['stop_id'].strip()

        # Skip if trip not imported
        if trip_id not in trip_ids:
            skipped_trip += 1
            continue

        # Map stop_id (handle leading zeros)
        our_stop_id = stop_mapping.get(gtfs_stop_id)
        if not our_stop_id:
            # Try normalized version
            normalized = normalize_stop_id(gtfs_stop_id)
            our_stop_id = stop_mapping.get(normalized)

        if not our_stop_id:
            skipped_stop += 1
            continue

        arrival_time = st['arrival_time'].strip()
        departure_time = st['departure_time'].strip()

        rows.append({
            'trip_id': trip_id,
            'stop_sequence': int(st['stop_sequence'].strip()),
            'stop_id': our_stop_id,
            'arrival_time': arrival_time,
            'departure_time': departure_time,
            'arrival_seconds': time_to_seconds(arrival_time),
            'departure_seconds': time_to_seconds(departure_time),
        })

        if len(rows) >= BATCH_SIZE:
            db.execute(
                text("""
                    INSERT INTO gtfs_stop_times
                    (trip_id, stop_sequence, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds)
                    VALUES (:trip_id, :stop_sequence, :stop_id, :arrival_time, :departure_time, :arrival_seconds, :departure_seconds)
                    ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
                        stop_id = EXCLUDED.stop_id,
                        arrival_time = EXCLUDED.arrival_time,
                        departure_time = EXCLUDED.departure_time,
                        arrival_seconds = EXCLUDED.arrival_seconds,
                        departure_seconds = EXCLUDED.departure_seconds
                """),
                rows
            )
            imported += len(rows)
            rows = []
            db.commit()

    # Insert remaining rows
    if rows:
        db.execute(
            text("""
                INSERT INTO gtfs_stop_times
                (trip_id, stop_sequence, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds)
                VALUES (:trip_id, :stop_sequence, :stop_id, :arrival_time, :departure_time, :arrival_seconds, :departure_seconds)
                ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
                    stop_id = EXCLUDED.stop_id,
                    arrival_time = EXCLUDED.arrival_time,
                    departure_time = EXCLUDED.departure_time,
                    arrival_seconds = EXCLUDED.arrival_seconds,
                    departure_seconds = EXCLUDED.departure_seconds
            """),
            rows
        )
        imported += len(rows)

    db.commit()

    logger.info(f"Imported {imported} stop_times")
    logger.info(f"Skipped {skipped_trip} (trip not found), {skipped_stop} (stop not found)")
    return imported


def clear_network_data(db, network_id: str):
    """Clear existing data for a specific FEVE network."""
    logger.info(f"Clearing existing data for network {network_id}...")

    # Find routes for this network
    result = db.execute(
        text("SELECT id FROM gtfs_routes WHERE network_id = :network_id"),
        {'network_id': network_id}
    )
    route_ids = [row[0] for row in result]

    if not route_ids:
        logger.info(f"No existing routes found for network {network_id}")
        return

    # Delete stop_times for trips on these routes
    result = db.execute(
        text("""
            DELETE FROM gtfs_stop_times
            WHERE trip_id IN (
                SELECT id FROM gtfs_trips WHERE route_id = ANY(:route_ids)
            )
        """),
        {'route_ids': route_ids}
    )
    logger.info(f"  Cleared {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(
        text("DELETE FROM gtfs_trips WHERE route_id = ANY(:route_ids)"),
        {'route_ids': route_ids}
    )
    logger.info(f"  Cleared {result.rowcount} trips")

    db.commit()


def main():
    parser = argparse.ArgumentParser(
        description='Import FEVE GTFS data (Ferrol, Cartagena, León)'
    )
    parser.add_argument('gtfs_folder', nargs='?', help='Path to FEVE GTFS folder')
    parser.add_argument('--network', '-n', help='Import specific network (45T, 46T, 47T)')
    parser.add_argument('--list-networks', '-l', action='store_true', help='List available networks')
    parser.add_argument('--clear', action='store_true', help='Clear existing data before import')

    args = parser.parse_args()

    if not args.gtfs_folder:
        parser.print_help()
        sys.exit(1)

    if not os.path.isdir(args.gtfs_folder):
        logger.error(f"Folder not found: {args.gtfs_folder}")
        sys.exit(1)

    if args.list_networks:
        list_networks(args.gtfs_folder)
        sys.exit(0)

    # Validate network filter
    network_filter = args.network
    if network_filter and network_filter not in FEVE_NETWORKS:
        logger.error(f"Unknown network: {network_filter}")
        logger.error(f"Available networks: {', '.join(FEVE_NETWORKS.keys())}")
        sys.exit(1)

    start_time = datetime.now()

    with SessionLocal() as db:
        try:
            # Clear existing data if requested
            if args.clear:
                if network_filter:
                    clear_network_data(db, network_filter)
                else:
                    for net_id in FEVE_NETWORKS.keys():
                        clear_network_data(db, net_id)

            # Import data
            import_networks(db, network_filter)
            stops_count = import_stops(db, args.gtfs_folder, network_filter)
            route_mapping = import_routes(db, args.gtfs_folder, network_filter)
            import_calendar(db, args.gtfs_folder, network_filter)
            trip_ids = import_trips(db, args.gtfs_folder, route_mapping, network_filter)
            stop_times_count = import_stop_times(db, args.gtfs_folder, trip_ids)

            elapsed = datetime.now() - start_time

            logger.info("")
            logger.info("=" * 60)
            logger.info("FEVE Import Summary")
            logger.info("=" * 60)
            if network_filter:
                info = FEVE_NETWORKS[network_filter]
                logger.info(f"Network: {network_filter} ({info['name']})")
            else:
                logger.info("Networks: All FEVE networks")
            logger.info(f"Stops: {stops_count}")
            logger.info(f"Routes: {len(route_mapping)}")
            logger.info(f"Trips: {len(trip_ids)}")
            logger.info(f"Stop times: {stop_times_count}")
            logger.info(f"Elapsed time: {elapsed}")
            logger.info("=" * 60)
            logger.info("")
            logger.info("FEVE import completed successfully!")

        except Exception as e:
            db.rollback()
            logger.error(f"Import failed: {e}")
            raise


if __name__ == '__main__':
    main()
