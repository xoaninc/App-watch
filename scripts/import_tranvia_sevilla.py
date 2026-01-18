#!/usr/bin/env python3
"""Import Tranvía de Sevilla (MetroCentro T1) from TUSSAM GTFS data.

Usage:
    python scripts/import_tranvia_sevilla.py <gtfs_folder_path>

Example:
    python scripts/import_tranvia_sevilla.py /path/to/20260109_090033_TUSSAM
"""

import sys
import csv
import logging
from pathlib import Path
from datetime import time

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

# Consistent agency ID
TRANVIA_SEVILLA_AGENCY_ID = 'TRANVIA_SEVILLA'

# Network configuration for tranvia
NETWORK_CONFIG = {
    'code': 'TRAM_SEV',  # Must match route ID prefix (max 10 chars)
    'name': 'Tranvía de Sevilla (MetroCentro)',
    'city': 'Sevilla',
    'region': 'Andalucía',
    'color': '#E4002B',  # Red
    'text_color': '#FFFFFF',
    'description': 'Servicio de tranvía en el centro de Sevilla',
    'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/MetroCentro_Sevilla_logo.svg/200px-MetroCentro_Sevilla_logo.svg.png',
}

# MetroCentro T1 route configuration
TRANVIA_CONFIG = {
    'route_id': 'TRAM_SEV_T1',
    'short_name': 'T1',
    'long_name': 'Archivo de Indias - Luis de Morales',
    'route_type': 0,  # Tram/Light Rail
    'color': '#E4002B',  # Red (typical tram color)
    'text_color': '#FFFFFF',
}

# TUSSAM route_id for tranvia
TUSSAM_TRANVIA_ROUTE_ID = '60'


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
        existing.logo_url = NETWORK_CONFIG.get('logo_url')
    else:
        network = NetworkModel(
            code=network_code,
            name=NETWORK_CONFIG['name'],
            city=NETWORK_CONFIG['city'],
            region=NETWORK_CONFIG['region'],
            color=NETWORK_CONFIG['color'],
            text_color=NETWORK_CONFIG['text_color'],
            description=NETWORK_CONFIG['description'],
            logo_url=NETWORK_CONFIG.get('logo_url'),
        )
        db.add(network)
        logger.info(f"Created network: {network_code}")

    db.flush()
    return network_code


def import_agency(db: Session, gtfs_path: Path) -> str:
    """Import/create tranvia agency."""
    agencies = read_csv(gtfs_path / 'agency.txt')
    if not agencies:
        raise ValueError("No agencies found in agency.txt")

    agency_data = agencies[0]
    agency_id = TRANVIA_SEVILLA_AGENCY_ID

    existing = db.query(AgencyModel).filter(AgencyModel.id == agency_id).first()
    if existing:
        logger.info(f"Agency {agency_id} already exists, updating...")
        existing.name = 'Tranvía de Sevilla (MetroCentro)'
        existing.url = agency_data.get('agency_url', 'https://www.tussam.es')
        existing.timezone = 'Europe/Madrid'
        existing.lang = 'es'
        existing.phone = agency_data.get('agency_phone', '')
    else:
        agency = AgencyModel(
            id=agency_id,
            name='Tranvía de Sevilla (MetroCentro)',
            url=agency_data.get('agency_url', 'https://www.tussam.es'),
            timezone='Europe/Madrid',
            lang='es',
            phone=agency_data.get('agency_phone', ''),
        )
        db.add(agency)
        logger.info(f"Created agency: {agency_id}")

    db.flush()
    return agency_id


def import_route(db: Session, agency_id: str) -> str:
    """Import/create the tranvia route."""
    route_id = TRANVIA_CONFIG['route_id']

    existing = db.query(RouteModel).filter(RouteModel.id == route_id).first()

    if existing:
        logger.info(f"Route {route_id} already exists, updating...")
        existing.short_name = TRANVIA_CONFIG['short_name']
        existing.long_name = TRANVIA_CONFIG['long_name']
        existing.route_type = TRANVIA_CONFIG['route_type']
        existing.color = TRANVIA_CONFIG['color']
        existing.text_color = TRANVIA_CONFIG['text_color']
        existing.agency_id = agency_id
        existing.nucleo_id = SEVILLA_NUCLEO_ID
        existing.nucleo_name = "Sevilla"
    else:
        route = RouteModel(
            id=route_id,
            short_name=TRANVIA_CONFIG['short_name'],
            long_name=TRANVIA_CONFIG['long_name'],
            route_type=TRANVIA_CONFIG['route_type'],
            color=TRANVIA_CONFIG['color'],
            text_color=TRANVIA_CONFIG['text_color'],
            agency_id=agency_id,
            nucleo_id=SEVILLA_NUCLEO_ID,
            nucleo_name="Sevilla",
        )
        db.add(route)
        logger.info(f"Created route: {route_id} ({TRANVIA_CONFIG['short_name']})")

    db.flush()
    return route_id


def import_stops(db: Session, gtfs_path: Path) -> dict:
    """Import tranvia stops from GTFS, deduplicating by name."""
    stops = read_csv(gtfs_path / 'stops.txt')
    trips = read_csv(gtfs_path / 'trips.txt')
    stop_times = read_csv(gtfs_path / 'stop_times.txt')

    # Get all trip_ids for tranvia route
    tranvia_trip_ids = {t['trip_id'] for t in trips if t['route_id'] == TUSSAM_TRANVIA_ROUTE_ID}

    # Get all stop_ids used by tranvia trips
    tranvia_stop_ids = set()
    for st in stop_times:
        if st['trip_id'] in tranvia_trip_ids:
            tranvia_stop_ids.add(st['stop_id'])

    logger.info(f"Found {len(tranvia_stop_ids)} stop IDs used by tranvia")

    # Filter stops to only tranvia stops
    tranvia_stops = [s for s in stops if s['stop_id'] in tranvia_stop_ids]

    # Deduplicate by name (keep first occurrence with best data)
    stops_by_name = {}
    for stop_data in tranvia_stops:
        name = stop_data['stop_name'].strip()
        if name not in stops_by_name:
            stops_by_name[name] = stop_data

    stop_mapping = {}  # old_id -> new_id (for all variants)

    for name, stop_data in stops_by_name.items():
        old_stop_id = stop_data['stop_id']
        # Create clean stop ID
        clean_name = name.upper().replace(' ', '_').replace('.', '')
        new_stop_id = f"TRAM_SEV_{clean_name}"

        existing = db.query(StopModel).filter(StopModel.id == new_stop_id).first()

        if existing:
            logger.info(f"Stop {new_stop_id} already exists, updating...")
            existing.name = name
            existing.lat = float(stop_data['stop_lat'])
            existing.lon = float(stop_data['stop_lon'])
            existing.location_type = 1  # Station
            existing.lineas = "T1"
            existing.nucleo_id = SEVILLA_NUCLEO_ID
            existing.nucleo_name = "Sevilla"
        else:
            stop = StopModel(
                id=new_stop_id,
                name=name,
                lat=float(stop_data['stop_lat']),
                lon=float(stop_data['stop_lon']),
                code=stop_data.get('stop_code', ''),
                location_type=1,  # Station (not Stop/Platform)
                lineas="T1",
                nucleo_id=SEVILLA_NUCLEO_ID,
                nucleo_name="Sevilla",
            )
            db.add(stop)
            logger.info(f"Created stop: {new_stop_id} ({name})")

        stop_mapping[old_stop_id] = new_stop_id

    # Map all stop variants to their deduplicated version
    for stop_data in tranvia_stops:
        name = stop_data['stop_name'].strip()
        old_id = stop_data['stop_id']
        if old_id not in stop_mapping:
            # Find the deduplicated ID for this name
            clean_name = name.upper().replace(' ', '_').replace('.', '')
            stop_mapping[old_id] = f"TRAM_SEV_{clean_name}"

    db.flush()
    return stop_mapping


def import_stop_sequences(db: Session, gtfs_path: Path, route_id: str, stop_mapping: dict):
    """Create stop sequences for the tranvia route."""
    trips = read_csv(gtfs_path / 'trips.txt')
    stop_times = read_csv(gtfs_path / 'stop_times.txt')

    # Get all trip_ids for tranvia
    tranvia_trips = [t for t in trips if t['route_id'] == TUSSAM_TRANVIA_ROUTE_ID]

    if not tranvia_trips:
        logger.warning("No tranvia trips found")
        return

    # Find the longest trip (full route) to use as template
    trip_stop_counts = {}
    for st in stop_times:
        trip_id = st['trip_id']
        if any(t['trip_id'] == trip_id for t in tranvia_trips):
            trip_stop_counts[trip_id] = trip_stop_counts.get(trip_id, 0) + 1

    if not trip_stop_counts:
        logger.warning("No stop times found for tranvia")
        return

    # Get trip with most stops
    template_trip_id = max(trip_stop_counts, key=trip_stop_counts.get)
    logger.info(f"Using trip {template_trip_id} as template ({trip_stop_counts[template_trip_id]} stops)")

    # Get stop sequence for template trip
    trip_stops = [st for st in stop_times if st['trip_id'] == template_trip_id]
    trip_stops.sort(key=lambda x: int(x['stop_sequence']))

    # Delete existing sequences
    db.query(StopRouteSequenceModel).filter(
        StopRouteSequenceModel.route_id == route_id
    ).delete()

    # Create sequences (deduplicated)
    seen_stops = set()
    seq = 1
    for st in trip_stops:
        old_stop_id = st['stop_id']
        new_stop_id = stop_mapping.get(old_stop_id)
        if not new_stop_id or new_stop_id in seen_stops:
            continue

        seen_stops.add(new_stop_id)
        sequence = StopRouteSequenceModel(
            route_id=route_id,
            stop_id=new_stop_id,
            sequence=seq,
        )
        db.add(sequence)
        seq += 1

    logger.info(f"Created {seq - 1} stop sequences for {route_id}")
    db.flush()


def import_frequencies(db: Session, gtfs_path: Path, route_id: str):
    """Import frequency data from GTFS, or use defaults if not available.

    Reads frequencies.txt and calendar.txt to get real service frequencies.
    Falls back to hardcoded defaults if no frequency data in GTFS.
    """
    # Delete existing frequencies
    db.query(RouteFrequencyModel).filter(
        RouteFrequencyModel.route_id == route_id
    ).delete()

    frequencies_file = gtfs_path / 'frequencies.txt'
    if frequencies_file.exists():
        # Import from GTFS
        count = _import_frequencies_from_gtfs(db, gtfs_path, route_id)
        if count > 0:
            logger.info(f"Imported {count} frequency entries from GTFS for {route_id}")
            db.flush()
            return

    # Fall back to defaults if no GTFS frequencies
    logger.info("No GTFS frequencies found, using defaults")
    _import_default_frequencies(db, route_id)
    db.flush()


def _import_frequencies_from_gtfs(db: Session, gtfs_path: Path, route_id: str) -> int:
    """Import frequencies from GTFS frequencies.txt and calendar.txt."""
    frequencies = read_csv(gtfs_path / 'frequencies.txt')
    trips = read_csv(gtfs_path / 'trips.txt')
    calendar_file = gtfs_path / 'calendar.txt'

    if not calendar_file.exists():
        logger.warning("No calendar.txt found")
        return 0

    calendars = read_csv(calendar_file)

    # Get trip -> service_id mapping for tranvia route only
    trip_info = {}
    for t in trips:
        if t['route_id'] == TUSSAM_TRANVIA_ROUTE_ID:
            trip_info[t['trip_id']] = t['service_id']

    if not trip_info:
        logger.warning("No tranvia trips found")
        return 0

    # Get service_id -> day_type mapping
    service_days = {}
    for cal in calendars:
        service_id = cal['service_id']
        # Determine day type based on service days
        sat = cal.get('saturday', '0') == '1'
        sun = cal.get('sunday', '0') == '1'
        mon = cal.get('monday', '0') == '1'

        if sat and not sun:
            service_days[service_id] = 'saturday'
        elif sun and not sat:
            service_days[service_id] = 'sunday'
        elif mon:
            service_days[service_id] = 'weekday'
        else:
            service_days[service_id] = 'weekday'

    # Group frequencies by time period and day type
    route_frequencies = {}  # (day_type, start, end) -> headway_secs

    for freq in frequencies:
        trip_id = freq['trip_id']
        service_id = trip_info.get(trip_id)
        if not service_id:
            continue  # Not a tranvia trip

        day_type = service_days.get(service_id, 'weekday')
        start_time = freq['start_time']
        end_time = freq['end_time']
        headway_secs = int(freq['headway_secs'])

        key = (day_type, start_time, end_time)
        # Use minimum headway for same period (more frequent = better)
        if key not in route_frequencies or headway_secs < route_frequencies[key]:
            route_frequencies[key] = headway_secs

    # Insert frequencies
    count = 0
    for (day_type, start_str, end_str), headway_secs in route_frequencies.items():
        # Parse time strings (handle >24h for overnight service)
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
        count += 1

    return count


def _import_default_frequencies(db: Session, route_id: str):
    """Add default frequency data for tranvia when GTFS data not available.

    MetroCentro typically runs every 5-7 minutes during peak hours.
    """
    default_frequencies = [
        # Weekday
        {'day_type': 'weekday', 'start': (6, 30), 'end': (9, 0), 'headway': 360},   # 6min peak
        {'day_type': 'weekday', 'start': (9, 0), 'end': (14, 0), 'headway': 480},   # 8min
        {'day_type': 'weekday', 'start': (14, 0), 'end': (17, 0), 'headway': 420},  # 7min
        {'day_type': 'weekday', 'start': (17, 0), 'end': (21, 0), 'headway': 360},  # 6min peak
        {'day_type': 'weekday', 'start': (21, 0), 'end': (23, 30), 'headway': 600}, # 10min
        # Saturday
        {'day_type': 'saturday', 'start': (7, 0), 'end': (14, 0), 'headway': 480},  # 8min
        {'day_type': 'saturday', 'start': (14, 0), 'end': (21, 0), 'headway': 420}, # 7min
        {'day_type': 'saturday', 'start': (21, 0), 'end': (23, 30), 'headway': 600},# 10min
        # Sunday
        {'day_type': 'sunday', 'start': (8, 0), 'end': (14, 0), 'headway': 600},    # 10min
        {'day_type': 'sunday', 'start': (14, 0), 'end': (22, 0), 'headway': 540},   # 9min
    ]

    for freq in default_frequencies:
        freq_model = RouteFrequencyModel(
            route_id=route_id,
            start_time=time(freq['start'][0], freq['start'][1]),
            end_time=time(freq['end'][0], freq['end'][1]),
            headway_secs=freq['headway'],
            day_type=freq['day_type'],
        )
        db.add(freq_model)

    logger.info(f"Created {len(default_frequencies)} default frequency entries for {route_id}")


def main():
    """Main import function."""
    if len(sys.argv) < 2:
        print("Usage: python import_tranvia_sevilla.py <gtfs_folder_path>")
        print("Example: python import_tranvia_sevilla.py ./data/20260109_090033_TUSSAM")
        sys.exit(1)

    gtfs_path = Path(sys.argv[1])
    if not gtfs_path.exists():
        print(f"Error: Path not found: {gtfs_path}")
        sys.exit(1)

    logger.info(f"Starting Tranvía de Sevilla import from {gtfs_path}...")

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
        route_id = import_route(db, agency_id)
        stop_mapping = import_stops(db, gtfs_path)
        import_stop_sequences(db, gtfs_path, route_id, stop_mapping)
        import_frequencies(db, gtfs_path, route_id)

        db.commit()

        # Automatically calculate correspondences with other transit systems in the same núcleo
        logger.info("Calculating correspondences with Metro Sevilla and Cercanías...")
        populate_connections_for_nucleo(db, SEVILLA_NUCLEO_ID)

        logger.info("=" * 60)
        logger.info("TRANVÍA DE SEVILLA IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Network: {network_code}")
        logger.info(f"Agency: {agency_id}")
        logger.info(f"Route: {route_id} ({TRANVIA_CONFIG['short_name']})")
        logger.info(f"Stops: {len(set(stop_mapping.values()))} (location_type=1)")
        logger.info("Correspondences: automatically calculated from Metro Sevilla and Cercanías")

    except Exception as e:
        logger.error(f"Import failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
