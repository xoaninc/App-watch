#!/usr/bin/env python3
"""Import Metro de Sevilla from GTFS data.

Usage:
    python scripts/import_metro_sevilla.py <gtfs_folder_path>

Example:
    python scripts/import_metro_sevilla.py /path/to/20251211_130028_Metro_Sevilla
"""

import sys
import csv
import logging
from pathlib import Path
from datetime import datetime, time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from core.database import SessionLocal

# Import all models
from src.gtfs_bc.nucleo.infrastructure.models import NucleoModel
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel, RouteFrequencyModel
from src.gtfs_bc.agency.infrastructure.models import AgencyModel
from src.gtfs_bc.stop_route_sequence.infrastructure.models import StopRouteSequenceModel
from src.gtfs_bc.network.infrastructure.models import NetworkModel

# Import connection population function
from scripts.populate_stop_connections import populate_connections_for_nucleo

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sevilla nucleo ID
SEVILLA_NUCLEO_ID = 30

# Consistent agency ID (matching METRO_MADRID, METRO_LIGERO pattern)
METRO_SEVILLA_AGENCY_ID = 'METRO_SEVILLA'

# Network configuration
NETWORK_CONFIG = {
    'code': 'METRO_SEV',  # Must match route ID prefix for route_count to work
    'name': 'Metro de Sevilla',
    'city': 'Sevilla',
    'region': 'Andalucía',
    'color': '0D6928',  # Green - official Metro Sevilla color
    'text_color': 'FFFFFF',
    'description': 'Red de metro de Sevilla',
}

# Metro Sevilla route long names (terminus to terminus)
METRO_SEV_LONG_NAMES = {
    'L1': 'Ciudad Expo - Olivar de Quintos',
}

# Default colors for Metro Sevilla (green)
DEFAULT_ROUTE_COLOR = '0D6928'  # Green - official Metro Sevilla color
DEFAULT_TEXT_COLOR = 'FFFFFF'  # White text on green background


def read_csv(file_path: Path) -> list:
    """Read CSV file and return list of dicts."""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return list(reader)


def import_network(db: Session) -> str:
    """Create/update the network entry for route_count to work."""
    network_code = NETWORK_CONFIG['code']

    existing = db.query(NetworkModel).filter(NetworkModel.code == network_code).first()
    if existing:
        logger.info(f"Network {network_code} already exists, updating...")
        existing.name = NETWORK_CONFIG['name']
        existing.city = NETWORK_CONFIG['city']
        existing.region = NETWORK_CONFIG['region']
        existing.color = NETWORK_CONFIG['color']
        existing.text_color = NETWORK_CONFIG['text_color']
        existing.description = NETWORK_CONFIG['description']
    else:
        network = NetworkModel(
            code=network_code,
            name=NETWORK_CONFIG['name'],
            city=NETWORK_CONFIG['city'],
            region=NETWORK_CONFIG['region'],
            color=NETWORK_CONFIG['color'],
            text_color=NETWORK_CONFIG['text_color'],
            description=NETWORK_CONFIG['description'],
        )
        db.add(network)
        logger.info(f"Created network: {network_code}")

    db.flush()
    return network_code


def import_agency(db: Session, gtfs_path: Path) -> str:
    """Import agency from GTFS.

    Uses consistent agency_id METRO_SEVILLA (matching METRO_MADRID pattern).
    """
    agencies = read_csv(gtfs_path / 'agency.txt')
    if not agencies:
        raise ValueError("No agencies found in agency.txt")

    agency_data = agencies[0]
    agency_id = METRO_SEVILLA_AGENCY_ID  # Use consistent ID

    existing = db.query(AgencyModel).filter(AgencyModel.id == agency_id).first()
    if existing:
        logger.info(f"Agency {agency_id} already exists, updating...")
        existing.name = agency_data['agency_name']
        existing.url = agency_data.get('agency_url', '')
        existing.timezone = agency_data.get('agency_timezone', 'Europe/Madrid')
        existing.lang = agency_data.get('agency_lang', 'es')
        existing.phone = agency_data.get('agency_phone', '')
    else:
        agency = AgencyModel(
            id=agency_id,
            name=agency_data['agency_name'],
            url=agency_data.get('agency_url', ''),
            timezone=agency_data.get('agency_timezone', 'Europe/Madrid'),
            lang=agency_data.get('agency_lang', 'es'),
            phone=agency_data.get('agency_phone', ''),
        )
        db.add(agency)
        logger.info(f"Created agency: {agency_id}")

    db.flush()
    return agency_id


def import_routes(db: Session, gtfs_path: Path, agency_id: str) -> tuple:
    """Import routes from GTFS.

    Returns:
        Tuple of (route_mapping dict, list of short_names)
    """
    routes = read_csv(gtfs_path / 'routes.txt')
    route_mapping = {}  # old_id -> new_id
    short_names = []  # List of route short names

    for route_data in routes:
        old_route_id = route_data['route_id']
        new_route_id = f"METRO_SEV_{old_route_id.replace('-', '_')}"

        existing = db.query(RouteModel).filter(RouteModel.id == new_route_id).first()

        short_name = route_data.get('route_short_name', '')
        # Add L prefix if not present
        if short_name and not short_name.startswith('L'):
            short_name = f"L{short_name}"

        if short_name and short_name not in short_names:
            short_names.append(short_name)

        # Use predefined long_name if available, otherwise fall back to GTFS
        long_name = METRO_SEV_LONG_NAMES.get(short_name, route_data.get('route_long_name', ''))

        # Use default text_color if GTFS value is empty
        text_color = route_data.get('route_text_color', '') or DEFAULT_TEXT_COLOR

        if existing:
            logger.info(f"Route {new_route_id} already exists, updating...")
            existing.short_name = short_name
            existing.long_name = long_name
            existing.route_type = int(route_data.get('route_type', 1))
            existing.color = route_data.get('route_color', DEFAULT_ROUTE_COLOR)
            existing.text_color = text_color
            existing.agency_id = agency_id
            existing.nucleo_id = SEVILLA_NUCLEO_ID
            existing.nucleo_name = "Sevilla"
        else:
            route = RouteModel(
                id=new_route_id,
                short_name=short_name,
                long_name=long_name,
                route_type=int(route_data.get('route_type', 1)),
                color=route_data.get('route_color', DEFAULT_ROUTE_COLOR),
                text_color=text_color,
                agency_id=agency_id,
                nucleo_id=SEVILLA_NUCLEO_ID,
                nucleo_name="Sevilla",
            )
            db.add(route)
            logger.info(f"Created route: {new_route_id} ({short_name})")

        route_mapping[old_route_id] = new_route_id

    db.flush()
    return route_mapping, short_names


def import_stops(db: Session, gtfs_path: Path, route_short_names: list) -> dict:
    """Import stops from GTFS (only stations, location_type=1).

    Args:
        db: Database session
        gtfs_path: Path to GTFS folder
        route_short_names: List of route short names (e.g., ['L1']) for lineas field
    """
    stops = read_csv(gtfs_path / 'stops.txt')
    stop_mapping = {}  # old_id -> new_id

    # Build lineas string from route short names (e.g., "L1" or "L1,L2")
    lineas = ','.join(route_short_names) if route_short_names else "L1"

    # Only import stations (location_type=1)
    stations = [s for s in stops if s.get('location_type') == '1']

    for stop_data in stations:
        old_stop_id = stop_data['stop_id']
        new_stop_id = f"METRO_SEV_{old_stop_id.replace('-', '_')}"

        # Parse wheelchair_boarding (0=no info, 1=accessible, 2=not accessible)
        wheelchair_raw = stop_data.get('wheelchair_boarding', '')
        wheelchair_boarding = int(wheelchair_raw) if wheelchair_raw.isdigit() else 0

        existing = db.query(StopModel).filter(StopModel.id == new_stop_id).first()

        if existing:
            logger.info(f"Stop {new_stop_id} already exists, updating...")
            existing.name = stop_data['stop_name']
            existing.lat = float(stop_data['stop_lat'])
            existing.lon = float(stop_data['stop_lon'])
            existing.description = stop_data.get('stop_desc', '')
            existing.zone_id = stop_data.get('zone_id', '')
            existing.location_type = 1
            existing.lineas = lineas
            existing.wheelchair_boarding = wheelchair_boarding
            existing.nucleo_id = SEVILLA_NUCLEO_ID
            existing.nucleo_name = "Sevilla"
        else:
            stop = StopModel(
                id=new_stop_id,
                name=stop_data['stop_name'],
                lat=float(stop_data['stop_lat']),
                lon=float(stop_data['stop_lon']),
                code=stop_data.get('stop_code', ''),
                description=stop_data.get('stop_desc', ''),
                zone_id=stop_data.get('zone_id', ''),
                location_type=1,  # Station
                lineas=lineas,
                wheelchair_boarding=wheelchair_boarding,
                nucleo_id=SEVILLA_NUCLEO_ID,
                nucleo_name="Sevilla",
            )
            db.add(stop)
            logger.info(f"Created stop: {new_stop_id} ({stop_data['stop_name']})")

        stop_mapping[old_stop_id] = new_stop_id

    db.flush()
    return stop_mapping


def import_stop_sequences(db: Session, gtfs_path: Path, route_mapping: dict, stop_mapping: dict):
    """Create stop sequences from stop_times.txt."""
    stop_times = read_csv(gtfs_path / 'stop_times.txt')
    trips = read_csv(gtfs_path / 'trips.txt')

    # Get trip -> route mapping
    trip_to_route = {t['trip_id']: t['route_id'] for t in trips}

    # Get unique stop sequence for each route (use first trip as template)
    route_stops = {}
    for st in sorted(stop_times, key=lambda x: (x['trip_id'], int(x['stop_sequence']))):
        trip_id = st['trip_id']
        route_id = trip_to_route.get(trip_id)
        if not route_id:
            continue

        new_route_id = route_mapping.get(route_id)
        if not new_route_id or new_route_id in route_stops:
            continue

        # Build stop sequence for this route
        trip_stops = [s for s in stop_times if s['trip_id'] == trip_id]
        trip_stops.sort(key=lambda x: int(x['stop_sequence']))

        # Only use parent stations (L1-E1, etc), not platforms (L1-1)
        station_stops = []
        for s in trip_stops:
            stop_id = s['stop_id']
            # Convert platform to station if needed
            if stop_id.startswith('L1-') and not stop_id.startswith('L1-E'):
                stop_id = f"L1-E{stop_id.split('-')[1]}"

            if stop_id in stop_mapping and stop_id not in [ss[0] for ss in station_stops]:
                station_stops.append((stop_id, int(s['stop_sequence'])))

        route_stops[new_route_id] = station_stops

    # Create sequences
    for new_route_id, stops in route_stops.items():
        # Delete existing sequences
        db.query(StopRouteSequenceModel).filter(
            StopRouteSequenceModel.route_id == new_route_id
        ).delete()

        for seq, (old_stop_id, _) in enumerate(stops, start=1):
            new_stop_id = stop_mapping.get(old_stop_id)
            if not new_stop_id:
                continue

            sequence = StopRouteSequenceModel(
                route_id=new_route_id,
                stop_id=new_stop_id,
                sequence=seq,
            )
            db.add(sequence)

        logger.info(f"Created {len(stops)} stop sequences for {new_route_id}")

    db.flush()


def import_frequencies(db: Session, gtfs_path: Path, route_mapping: dict):
    """Import frequencies from GTFS."""
    frequencies_file = gtfs_path / 'frequencies.txt'
    if not frequencies_file.exists():
        logger.info("No frequencies.txt found, skipping frequencies import")
        return

    frequencies = read_csv(frequencies_file)
    trips = read_csv(gtfs_path / 'trips.txt')
    calendars = read_csv(gtfs_path / 'calendar.txt')

    # Get trip -> route and service_id mapping
    trip_info = {t['trip_id']: {'route_id': t['route_id'], 'service_id': t['service_id']} for t in trips}

    # Get service_id -> day_type mapping
    service_days = {}
    for cal in calendars:
        service_id = cal['service_id']
        # Determine day type based on service days
        if cal.get('saturday') == '1' and cal.get('sunday') != '1':
            service_days[service_id] = 'saturday'
        elif cal.get('sunday') == '1' and cal.get('saturday') != '1':
            service_days[service_id] = 'sunday'
        elif cal.get('monday') == '1' or cal.get('tuesday') == '1':
            service_days[service_id] = 'weekday'
        else:
            service_days[service_id] = 'weekday'

    # Group frequencies by route and time period
    route_frequencies = {}  # (route_id, day_type, start, end) -> headway_secs

    for freq in frequencies:
        trip_id = freq['trip_id']
        info = trip_info.get(trip_id)
        if not info:
            continue

        route_id = info['route_id']
        new_route_id = route_mapping.get(route_id)
        if not new_route_id:
            continue

        service_id = info['service_id']
        day_type = service_days.get(service_id, 'weekday')

        start_time = freq['start_time']
        end_time = freq['end_time']
        headway_secs = int(freq['headway_secs'])

        key = (new_route_id, day_type, start_time, end_time)
        # Use minimum headway for same period (more frequent = better)
        if key not in route_frequencies or headway_secs < route_frequencies[key]:
            route_frequencies[key] = headway_secs

    # Delete existing frequencies for Metro Sevilla routes
    for new_route_id in route_mapping.values():
        db.query(RouteFrequencyModel).filter(
            RouteFrequencyModel.route_id == new_route_id
        ).delete()

    # Insert frequencies
    for (route_id, day_type, start_str, end_str), headway_secs in route_frequencies.items():
        # Parse time strings
        start_parts = start_str.split(':')
        end_parts = end_str.split(':')

        start_hour = int(start_parts[0]) % 24
        start_min = int(start_parts[1])
        end_hour = int(end_parts[0]) % 24
        end_min = int(end_parts[1])

        freq_model = RouteFrequencyModel(
            route_id=route_id,
            start_time=time(start_hour, start_min),
            end_time=time(end_hour, end_min),
            headway_secs=headway_secs,
            day_type=day_type,
        )
        db.add(freq_model)

    logger.info(f"Created {len(route_frequencies)} frequency entries")
    db.flush()


def main():
    """Main import function."""
    if len(sys.argv) < 2:
        print("Usage: python import_metro_sevilla.py <gtfs_folder_path>")
        print("Example: python import_metro_sevilla.py ./data/20251211_130028_Metro_Sevilla")
        sys.exit(1)

    gtfs_path = Path(sys.argv[1])
    if not gtfs_path.exists():
        print(f"Error: Path not found: {gtfs_path}")
        sys.exit(1)

    logger.info(f"Starting Metro de Sevilla import from {gtfs_path}...")

    db = SessionLocal()
    try:
        # Check nucleo exists
        nucleo = db.query(NucleoModel).filter(NucleoModel.id == SEVILLA_NUCLEO_ID).first()
        if not nucleo:
            logger.error(f"Nucleo Sevilla (id={SEVILLA_NUCLEO_ID}) not found!")
            return

        logger.info(f"Using nucleo: {nucleo.name} (id={nucleo.id})")

        # Import data
        network_code = import_network(db)
        agency_id = import_agency(db, gtfs_path)
        route_mapping, route_short_names = import_routes(db, gtfs_path, agency_id)
        stop_mapping = import_stops(db, gtfs_path, route_short_names)
        import_stop_sequences(db, gtfs_path, route_mapping, stop_mapping)
        import_frequencies(db, gtfs_path, route_mapping)

        db.commit()

        # Automatically calculate correspondences with Cercanías and Tranvía in the same núcleo
        logger.info("Calculating correspondences with Cercanías and Tranvía Sevilla...")
        populate_connections_for_nucleo(db, SEVILLA_NUCLEO_ID)

        logger.info("=" * 60)
        logger.info("METRO DE SEVILLA IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Network: {network_code}")
        logger.info(f"Agency: {agency_id}")
        logger.info(f"Routes: {len(route_mapping)}")
        logger.info(f"Stops: {len(stop_mapping)}")
        logger.info("Correspondences: automatically calculated")

    except Exception as e:
        logger.error(f"Import failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
