#!/usr/bin/env python3
"""Import GTFS data from RENFE Proximidad (within AVLD feed).

Proximidad services are commuter-like regional trains in areas without official
Cercanías networks. They are identified by route_short_name = 'PROXIMDAD' in the
AVLD GTFS feed.

Networks:
- PROX_CYL: Castilla y León (Medina del Campo - Valladolid - Palencia)
- PROX_MAD: Madrid-Illescas (Atocha - Illescas)
- PROX_COR: Córdoba (Córdoba - Palma del Río - Villa del Río)
- PROX_MAL: Málaga (Málaga - El Chorro)
- PROX_MUR: Murcia-Cartagena (Murcia - Cartagena)

Usage:
    # Import all Proximidad networks
    python scripts/import_proximidad_gtfs.py /path/to/RENFE_AVLD/

    # Import specific network
    python scripts/import_proximidad_gtfs.py /path/to/RENFE_AVLD/ --network PROX_MAL

    # List available networks
    python scripts/import_proximidad_gtfs.py /path/to/RENFE_AVLD/ --list-networks

Note: Uses same stop_id as Cercanías (RENFE_xxxxx) to avoid duplicate stations.
"""

import sys
import os
import csv
import logging
import argparse
from datetime import datetime, date
from typing import Optional, Dict, Set, List, Tuple
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Proximidad Network definitions based on station code prefixes
PROXIMIDAD_NETWORKS = {
    'PROX_CYL': {
        'name': 'Proximidad Castilla y León',
        'region': 'Castilla y León',
        'prefixes': ['105', '106', '110', '141'],
        'color': '8B4513',  # Brown - regional CyL
        'text_color': 'FFFFFF',
        'description': 'Medina del Campo - Valladolid - Palencia',
    },
    'PROX_MAD': {
        'name': 'Proximidad Madrid-Illescas',
        'region': 'Madrid/Toledo',
        'prefixes': ['180', '350'],
        'color': '004B87',  # Dark blue - Madrid extension
        'text_color': 'FFFFFF',
        'description': 'Madrid Atocha - Illescas',
    },
    'PROX_COR': {
        'name': 'Proximidad Córdoba',
        'region': 'Córdoba',
        'prefixes': ['504', '505'],
        'color': '228B22',  # Green - Córdoba
        'text_color': 'FFFFFF',
        'description': 'Córdoba - Palma del Río - Villa del Río',
    },
    'PROX_MAL': {
        'name': 'Proximidad Málaga',
        'region': 'Málaga',
        'prefixes': ['544', '545'],
        'color': '9400D3',  # Purple - Málaga Proximidad
        'text_color': 'FFFFFF',
        'description': 'Málaga - El Chorro (Caminito del Rey)',
    },
    'PROX_MUR': {
        'name': 'Proximidad Murcia-Cartagena',
        'region': 'Murcia',
        'prefixes': ['612', '613'],
        'color': 'FF4500',  # Orange-red - Murcia
        'text_color': 'FFFFFF',
        'description': 'Murcia - Cartagena',
    },
}

BATCH_SIZE = 5000


def time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS to seconds since midnight."""
    parts = time_str.strip().split(':')
    if len(parts) != 3:
        return 0
    hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2].split('.')[0])
    return hours * 3600 + minutes * 60 + seconds


def parse_date(date_str: str) -> str:
    """Convert YYYYMMDD or YYYY-MM-DD to YYYY-MM-DD."""
    date_str = date_str.strip().replace('-', '')
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


def get_network_for_stop(stop_id: str) -> Optional[str]:
    """Determine which Proximidad network a stop belongs to."""
    for network_id, info in PROXIMIDAD_NETWORKS.items():
        for prefix in info['prefixes']:
            if stop_id.startswith(prefix):
                return network_id
    return None


def read_csv_file(folder_path: str, filename: str) -> List[Dict]:
    """Read a CSV file from the GTFS folder."""
    filepath = os.path.join(folder_path, filename)
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # Clean field names
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        return list(reader)


def list_networks(folder_path: str):
    """List available Proximidad networks in the GTFS."""
    routes = read_csv_file(folder_path, 'routes.txt')
    trips = read_csv_file(folder_path, 'trips.txt')
    stop_times = read_csv_file(folder_path, 'stop_times.txt')

    # Filter only PROXIMDAD routes
    proximidad_routes = {r['route_id'].strip() for r in routes
                         if r.get('route_short_name', '').strip() == 'PROXIMDAD'}

    if not proximidad_routes:
        print("No PROXIMIDAD routes found in this GTFS feed.")
        return

    # Build trip -> route mapping
    trip_to_route = {t['trip_id'].strip(): t['route_id'].strip()
                     for t in trips if t['route_id'].strip() in proximidad_routes}

    # Find stops per network
    networks_found = {net_id: {'stops': set(), 'trips': 0} for net_id in PROXIMIDAD_NETWORKS}

    for st in stop_times:
        trip_id = st['trip_id'].strip()
        if trip_id in trip_to_route:
            stop_id = st['stop_id'].strip()
            network = get_network_for_stop(stop_id)
            if network:
                networks_found[network]['stops'].add(stop_id)

    # Count trips per network
    for trip_id, route_id in trip_to_route.items():
        # Get first stop to determine network
        for st in stop_times:
            if st['trip_id'].strip() == trip_id:
                network = get_network_for_stop(st['stop_id'].strip())
                if network:
                    networks_found[network]['trips'] += 1
                break

    print("\nProximidad Networks available:")
    print("=" * 70)
    for network_id, data in sorted(networks_found.items()):
        info = PROXIMIDAD_NETWORKS[network_id]
        if data['stops']:
            print(f"\n{network_id}: {info['name']}")
            print(f"  Region: {info['region']}")
            print(f"  Description: {info['description']}")
            print(f"  Stops: {len(data['stops'])}")
            print(f"  Trips: {data['trips']}")
    print()


def import_networks(db, network_filter: str = None) -> int:
    """Create Proximidad networks in gtfs_networks table."""
    logger.info("Creating Proximidad networks...")

    imported = 0
    for network_id, info in PROXIMIDAD_NETWORKS.items():
        if network_filter and network_id != network_filter:
            continue

        db.execute(
            text("""
                INSERT INTO gtfs_networks (code, name, region, color, text_color, description, logo_url)
                VALUES (:code, :name, :region, :color, :text_color, :description, :logo_url)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    region = EXCLUDED.region,
                    color = EXCLUDED.color,
                    text_color = EXCLUDED.text_color,
                    description = EXCLUDED.description,
                    logo_url = EXCLUDED.logo_url
            """),
            {
                'code': network_id,
                'name': info['name'],
                'region': info['region'],
                'color': info['color'],
                'text_color': info['text_color'],
                'description': info['description'],
                'logo_url': '/static/logos/proximidad.png',
            }
        )
        imported += 1

    db.commit()
    logger.info(f"Created {imported} networks")
    return imported


def import_stops(db, folder_path: str, network_filter: str = None) -> Tuple[int, int]:
    """Import stops from Proximidad GTFS. Uses RENFE_xxxxx format (same as Cercanías)."""
    logger.info("Importing Proximidad stops...")

    stops = read_csv_file(folder_path, 'stops.txt')
    routes = read_csv_file(folder_path, 'routes.txt')
    trips = read_csv_file(folder_path, 'trips.txt')
    stop_times = read_csv_file(folder_path, 'stop_times.txt')

    # Filter only PROXIMDAD routes
    proximidad_routes = {r['route_id'].strip() for r in routes
                         if r.get('route_short_name', '').strip() == 'PROXIMDAD'}

    # Build trip -> route mapping
    trip_to_route = {t['trip_id'].strip(): t['route_id'].strip()
                     for t in trips if t['route_id'].strip() in proximidad_routes}

    # Find which stops are used by Proximidad
    proximidad_stops = set()
    for st in stop_times:
        if st['trip_id'].strip() in trip_to_route:
            stop_id = st['stop_id'].strip()
            network = get_network_for_stop(stop_id)
            if network:
                if network_filter and network != network_filter:
                    continue
                proximidad_stops.add(stop_id)

    logger.info(f"Found {len(proximidad_stops)} Proximidad stops")

    # Get existing stops
    existing = set()
    result = db.execute(text("SELECT id FROM gtfs_stops WHERE id LIKE 'RENFE_%'"))
    for row in result:
        existing.add(row[0])

    # Build stop info mapping
    stop_info = {s['stop_id'].strip(): s for s in stops}

    imported = 0
    skipped = 0

    for gtfs_stop_id in proximidad_stops:
        our_stop_id = f"RENFE_{gtfs_stop_id}"

        if our_stop_id in existing:
            skipped += 1
            continue

        stop = stop_info.get(gtfs_stop_id)
        if not stop:
            logger.warning(f"Stop {gtfs_stop_id} not found in stops.txt")
            continue

        stop_name = stop.get('stop_name', '').strip()
        lat = float(stop.get('stop_lat', '0').strip() or '0')
        lon = float(stop.get('stop_lon', '0').strip() or '0')

        # Determine province from network
        network = get_network_for_stop(gtfs_stop_id)
        province = PROXIMIDAD_NETWORKS.get(network, {}).get('region')

        db.execute(
            text("""
                INSERT INTO gtfs_stops (id, name, lat, lon, location_type, province)
                VALUES (:id, :name, :lat, :lon, 0, :province)
                ON CONFLICT (id) DO UPDATE SET
                    name = COALESCE(NULLIF(EXCLUDED.name, ''), gtfs_stops.name),
                    lat = CASE WHEN EXCLUDED.lat != 0 THEN EXCLUDED.lat ELSE gtfs_stops.lat END,
                    lon = CASE WHEN EXCLUDED.lon != 0 THEN EXCLUDED.lon ELSE gtfs_stops.lon END,
                    province = COALESCE(EXCLUDED.province, gtfs_stops.province)
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
    return imported, skipped


def import_routes(db, folder_path: str, network_filter: str = None) -> Dict[str, str]:
    """Import Proximidad routes."""
    logger.info("Importing Proximidad routes...")

    routes = read_csv_file(folder_path, 'routes.txt')
    trips = read_csv_file(folder_path, 'trips.txt')
    stop_times = read_csv_file(folder_path, 'stop_times.txt')

    # Filter only PROXIMDAD routes
    proximidad_routes = [r for r in routes
                         if r.get('route_short_name', '').strip() == 'PROXIMDAD']

    # Build trip -> route and find first stop per trip (to determine network)
    trip_first_stop = {}
    for st in stop_times:
        trip_id = st['trip_id'].strip()
        seq = int(st.get('stop_sequence', '0').strip() or '0')
        if trip_id not in trip_first_stop or seq < trip_first_stop[trip_id][0]:
            trip_first_stop[trip_id] = (seq, st['stop_id'].strip())

    # Map route_id to network
    route_networks = {}
    for trip in trips:
        route_id = trip['route_id'].strip()
        trip_id = trip['trip_id'].strip()
        if trip_id in trip_first_stop:
            stop_id = trip_first_stop[trip_id][1]
            network = get_network_for_stop(stop_id)
            if network:
                route_networks[route_id] = network

    route_mapping = {}
    imported = 0

    for route in proximidad_routes:
        gtfs_route_id = route['route_id'].strip()
        network_id = route_networks.get(gtfs_route_id)

        if not network_id:
            continue

        if network_filter and network_id != network_filter:
            continue

        # Create our route_id
        our_route_id = f"RENFE_PROX_{network_id.replace('PROX_', '')}"
        route_mapping[gtfs_route_id] = our_route_id

        # Get network color
        network_info = PROXIMIDAD_NETWORKS.get(network_id, {})
        color = network_info.get('color', 'F2F5F5')
        text_color = network_info.get('text_color', '000000')

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
                'agency_id': '1071VC',  # RENFE Cercanías
                'short_name': 'PROX',
                'long_name': network_info.get('description', 'Proximidad'),
                'color': color,
                'text_color': text_color,
                'network_id': network_id,
            }
        )
        imported += 1

    db.commit()
    # Deduplicate - we might have multiple GTFS routes per our route
    unique_routes = len(set(route_mapping.values()))
    logger.info(f"Imported {unique_routes} routes (from {len(route_mapping)} GTFS routes)")
    return route_mapping


def import_calendar(db, folder_path: str, route_mapping: Dict[str, str]) -> Set[str]:
    """Import calendar from Proximidad GTFS."""
    logger.info("Importing Proximidad calendar...")

    calendar = read_csv_file(folder_path, 'calendar.txt')
    trips = read_csv_file(folder_path, 'trips.txt')

    # Find which service_ids are used by Proximidad trips
    proximidad_services = set()
    for trip in trips:
        if trip['route_id'].strip() in route_mapping:
            proximidad_services.add(trip['service_id'].strip())

    imported = 0
    service_ids = set()

    for cal in calendar:
        service_id = cal['service_id'].strip()

        if service_id not in proximidad_services:
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
                'monday': cal.get('monday', '0').strip() == '1',
                'tuesday': cal.get('tuesday', '0').strip() == '1',
                'wednesday': cal.get('wednesday', '0').strip() == '1',
                'thursday': cal.get('thursday', '0').strip() == '1',
                'friday': cal.get('friday', '0').strip() == '1',
                'saturday': cal.get('saturday', '0').strip() == '1',
                'sunday': cal.get('sunday', '0').strip() == '1',
                'start_date': parse_date(cal['start_date']),
                'end_date': parse_date(cal['end_date']),
            }
        )
        imported += 1

    db.commit()
    logger.info(f"Imported {imported} calendar entries")
    return service_ids


def import_trips(db, folder_path: str, route_mapping: Dict[str, str]) -> Set[str]:
    """Import trips from Proximidad GTFS."""
    logger.info("Importing Proximidad trips...")

    trips = read_csv_file(folder_path, 'trips.txt')
    stop_times = read_csv_file(folder_path, 'stop_times.txt')
    stops = read_csv_file(folder_path, 'stops.txt')

    # Build stop_id -> name mapping
    stop_names = {s['stop_id'].strip(): s['stop_name'].strip() for s in stops}

    # Find last stop for each trip (for headsign)
    trip_last_stop = {}
    for st in stop_times:
        trip_id = st['trip_id'].strip()
        stop_id = st['stop_id'].strip()
        sequence = int(st.get('stop_sequence', '0').strip() or '0')

        if trip_id not in trip_last_stop or sequence > trip_last_stop[trip_id][0]:
            trip_last_stop[trip_id] = (sequence, stop_id)

    trip_headsigns = {tid: stop_names.get(sid, '') for tid, (_, sid) in trip_last_stop.items()}

    imported = 0
    trip_ids = set()

    for trip in trips:
        trip_id = trip['trip_id'].strip()
        gtfs_route_id = trip['route_id'].strip()
        service_id = trip['service_id'].strip()

        if gtfs_route_id not in route_mapping:
            continue

        our_route_id = route_mapping[gtfs_route_id]
        headsign = trip_headsigns.get(trip_id, '')

        # Use RENFE_ prefix for trip_id to match RT data format
        our_trip_id = f"RENFE_{trip_id}"

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
                'id': our_trip_id,
                'route_id': our_route_id,
                'service_id': service_id,
                'headsign': headsign,
                'direction_id': int(trip.get('direction_id', '0').strip() or '0'),
            }
        )
        trip_ids.add(our_trip_id)
        imported += 1

    db.commit()
    logger.info(f"Imported {imported} trips")
    return trip_ids


def import_stop_times(db, folder_path: str, trip_ids: Set[str], network_filter: str = None) -> int:
    """Import stop_times from Proximidad GTFS."""
    logger.info("Importing Proximidad stop_times...")

    stop_times = read_csv_file(folder_path, 'stop_times.txt')

    # Build stop mapping
    stop_mapping = {}
    result = db.execute(text("SELECT id FROM gtfs_stops WHERE id LIKE 'RENFE_%'"))
    for row in result:
        our_id = row[0]
        gtfs_id = our_id.replace('RENFE_', '')
        stop_mapping[gtfs_id] = our_id

    logger.info(f"Built stop mapping with {len(stop_mapping)} entries")

    rows = []
    imported = 0
    skipped_trip = 0
    skipped_stop = 0

    for st in stop_times:
        trip_id = st['trip_id'].strip()
        gtfs_stop_id = st['stop_id'].strip()
        our_trip_id = f"RENFE_{trip_id}"

        # Skip if trip not imported
        if our_trip_id not in trip_ids:
            skipped_trip += 1
            continue

        # Filter by network if specified
        if network_filter:
            network = get_network_for_stop(gtfs_stop_id)
            if network != network_filter:
                continue

        # Map stop_id
        our_stop_id = stop_mapping.get(gtfs_stop_id)
        if not our_stop_id:
            skipped_stop += 1
            continue

        arrival_time = st['arrival_time'].strip()
        departure_time = st['departure_time'].strip()

        rows.append({
            'trip_id': our_trip_id,
            'stop_sequence': int(st.get('stop_sequence', '0').strip() or '0'),
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

    logger.info(f"Imported {imported:,} stop_times")
    logger.info(f"Skipped {skipped_trip:,} (trip not found), {skipped_stop:,} (stop not found)")
    return imported


def create_correspondences(db):
    """Create manual correspondences for Proximidad stops."""
    logger.info("Creating Proximidad correspondences...")

    correspondences = [
        # Cartagena Proximidad ↔ FEVE Cartagena
        ('RENFE_61307', 'RENFE_5951', 500, 360),
    ]

    created = 0
    for from_id, to_id, distance, walk_time in correspondences:
        # Check if stops exist
        result = db.execute(
            text("SELECT COUNT(*) FROM gtfs_stops WHERE id IN (:from_id, :to_id)"),
            {'from_id': from_id, 'to_id': to_id}
        )
        if result.scalar() < 2:
            logger.warning(f"Skipping correspondence {from_id} ↔ {to_id}: stops not found")
            continue

        # Create both directions
        for f, t in [(from_id, to_id), (to_id, from_id)]:
            db.execute(
                text("""
                    INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
                    VALUES (:from_id, :to_id, :distance, :walk_time, 'proximidad_import')
                    ON CONFLICT DO NOTHING
                """),
                {'from_id': f, 'to_id': t, 'distance': distance, 'walk_time': walk_time}
            )
        created += 1

    db.commit()
    logger.info(f"Created {created} correspondences")
    return created


def clear_network_data(db, network_id: str):
    """Clear existing data for a specific Proximidad network."""
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
        description='Import Proximidad GTFS data from AVLD feed'
    )
    parser.add_argument('gtfs_folder', nargs='?', help='Path to RENFE_AVLD GTFS folder')
    parser.add_argument('--network', '-n', help='Import specific network (PROX_CYL, PROX_MAD, PROX_COR, PROX_MAL, PROX_MUR)')
    parser.add_argument('--list-networks', '-l', action='store_true', help='List available networks')
    parser.add_argument('--clear', action='store_true', help='Clear existing data before import')
    parser.add_argument('--skip-correspondences', action='store_true', help='Skip creating correspondences')

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
    if network_filter and network_filter not in PROXIMIDAD_NETWORKS:
        logger.error(f"Unknown network: {network_filter}")
        logger.error(f"Available networks: {', '.join(PROXIMIDAD_NETWORKS.keys())}")
        sys.exit(1)

    start_time = datetime.now()

    with SessionLocal() as db:
        try:
            # Clear existing data if requested
            if args.clear:
                if network_filter:
                    clear_network_data(db, network_filter)
                else:
                    for net_id in PROXIMIDAD_NETWORKS.keys():
                        clear_network_data(db, net_id)

            # Import data
            import_networks(db, network_filter)
            stops_imported, stops_skipped = import_stops(db, args.gtfs_folder, network_filter)
            route_mapping = import_routes(db, args.gtfs_folder, network_filter)
            import_calendar(db, args.gtfs_folder, route_mapping)
            trip_ids = import_trips(db, args.gtfs_folder, route_mapping)
            stop_times_count = import_stop_times(db, args.gtfs_folder, trip_ids, network_filter)

            # Create correspondences
            if not args.skip_correspondences:
                create_correspondences(db)

            elapsed = datetime.now() - start_time

            logger.info("")
            logger.info("=" * 60)
            logger.info("Proximidad Import Summary")
            logger.info("=" * 60)
            if network_filter:
                info = PROXIMIDAD_NETWORKS[network_filter]
                logger.info(f"Network: {network_filter} ({info['name']})")
            else:
                logger.info("Networks: All Proximidad networks")
            logger.info(f"Stops: {stops_imported} imported, {stops_skipped} already existed")
            logger.info(f"Routes: {len(set(route_mapping.values()))}")
            logger.info(f"Trips: {len(trip_ids)}")
            logger.info(f"Stop times: {stop_times_count:,}")
            logger.info(f"Elapsed time: {elapsed}")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Proximidad import completed successfully!")

        except Exception as e:
            db.rollback()
            logger.error(f"Import failed: {e}")
            raise


if __name__ == '__main__':
    main()
