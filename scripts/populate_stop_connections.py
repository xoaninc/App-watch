#!/usr/bin/env python3
"""Script to populate cor_metro, cor_ml, cor_cercanias fields based on stop proximity.

Handles:
- RENFE_ (Cercanías)
- METRO_ (Metro Madrid)
- ML_ (Metro Ligero Madrid)
- METRO_SEV_ (Metro Sevilla)
- TRAM_SEV_ (Tranvía Sevilla)

Matching method:
- Proximity (default 100m) - stops within distance are considered connected
"""

import sys
import re
import logging
import unicodedata
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, Set, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from core.database import SessionLocal

# Import all models to ensure relationships are configured
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Default max distance in meters for considering stops as connected
DEFAULT_MAX_DISTANCE = 150

# Stop prefixes by type
STOP_PREFIXES = {
    'renfe': 'RENFE_',
    'metro': 'METRO_',  # Metro Madrid (but not METRO_SEV_)
    'ml': 'ML_',  # Metro Ligero Madrid
    'metro_sev': 'METRO_SEV_',  # Metro Sevilla
    'tranvia_sev': 'TRAM_SEV_',  # Tranvía Sevilla
}


def get_stop_type(stop_id: str) -> str:
    """Get stop type from stop ID prefix."""
    # Order matters - check more specific prefixes first
    if stop_id.startswith('METRO_SEV_'):
        return 'metro_sev'
    if stop_id.startswith('TRAM_SEV_'):
        return 'tranvia_sev'
    if stop_id.startswith('METRO_'):
        return 'metro'
    if stop_id.startswith('ML_'):
        return 'ml'
    if stop_id.startswith('RENFE_'):
        return 'renfe'
    return 'unknown'


def normalize_name(name: str) -> str:
    """Normalize station name for comparison.

    - Lowercase
    - Remove accents
    - Remove common prefixes/suffixes (Estación, Est., Station, etc.)
    - Remove punctuation
    - Collapse whitespace

    Example: "Estación de San Bernardo" -> "san bernardo"
    """
    if not name:
        return ""

    # Lowercase
    name = name.lower()

    # Remove accents
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))

    # Remove common prefixes/suffixes
    prefixes_to_remove = [
        'estacion de ', 'estacion ', 'est. ', 'est ',
        'parada ', 'apeadero ', 'apeadero de ',
        'metro ', 'cercanias ', 'tranvia ',
    ]
    for prefix in prefixes_to_remove:
        if name.startswith(prefix):
            name = name[len(prefix):]

    suffixes_to_remove = [
        ' (metro)', ' (cercanias)', ' (tranvia)', ' (renfe)',
        ' - metro', ' - cercanias',
    ]
    for suffix in suffixes_to_remove:
        if name.endswith(suffix):
            name = name[:-len(suffix)]

    # Remove punctuation except spaces
    name = re.sub(r'[^\w\s]', '', name)

    # Collapse whitespace
    name = ' '.join(name.split())

    return name


def names_match(name1: str, name2: str) -> bool:
    """Check if two station names refer to the same place.

    Uses normalized names and checks for:
    1. Exact match after normalization
    2. One is substring of the other (for partial matches like "San Bernardo" in "San Bernardo Centro")
    """
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    if not norm1 or not norm2:
        return False

    # Exact match
    if norm1 == norm2:
        return True

    # One contains the other (minimum 5 chars to avoid false positives)
    if len(norm1) >= 5 and len(norm2) >= 5:
        if norm1 in norm2 or norm2 in norm1:
            return True

    return False


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two coordinates using Haversine formula."""
    R = 6371000  # Earth's radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def is_metro_line(line: str) -> bool:
    """Check if a line is a valid Metro line (1-12, L1-L12, L7B, L9B, L10B, or R)."""
    line = line.strip()
    # Metro lines: 1-12, L1-L12, R, and B variants (L7B, L9B, L10B)
    if line == 'R':
        return True
    if line in ('L7B', 'L9B', 'L10B', '7B', '9B', '10B'):
        return True
    if line.isdigit() and 1 <= int(line) <= 12:
        return True
    if line.startswith('L') and line[1:].isdigit() and 1 <= int(line[1:]) <= 12:
        return True
    return False


def is_ml_line(line: str) -> bool:
    """Check if a line is a valid Metro Ligero line (1-4, ML1-ML4)."""
    line = line.strip()
    # ML lines: 1-4, ML1-ML4
    if line.isdigit() and 1 <= int(line) <= 4:
        return True
    if line.startswith('ML') and line[2:].isdigit() and 1 <= int(line[2:]) <= 4:
        return True
    return False


def normalize_metro_line(line: str) -> str:
    """Normalize metro line to have L prefix.

    '1' -> 'L1', 'L1' -> 'L1', 'R' -> 'R', '7B' -> 'L7B', 'L7B' -> 'L7B'
    Non-metro lines are filtered out in sort_lines when add_l_prefix=True
    """
    line = line.strip()
    # B variants without L prefix
    if line in ('7B', '9B', '10B'):
        return f'L{line}'
    # If it's a plain number (Metro Madrid line), add L prefix
    if line.isdigit() and 1 <= int(line) <= 12:
        return f'L{line}'
    return line


def normalize_ml_line(line: str) -> str:
    """Normalize Metro Ligero line to have ML prefix.

    '1' -> 'ML1', 'ML1' -> 'ML1'
    """
    line = line.strip()
    # If it's a plain number (1-4), add ML prefix
    if line.isdigit() and 1 <= int(line) <= 4:
        return f'ML{line}'
    return line


def sort_lines(lines: set, add_l_prefix: bool = False, add_ml_prefix: bool = False) -> str:
    """Sort lines: L-lines first (numerically), then ML-lines, then others.

    Args:
        lines: Set of line names
        add_l_prefix: If True, filter to Metro lines only and add 'L' prefix
        add_ml_prefix: If True, filter to ML lines only and add 'ML' prefix
    """
    if add_l_prefix:
        # Filter to only Metro lines (1-12, L1-L12, R) and normalize
        lines = {normalize_metro_line(x) for x in lines if is_metro_line(x)}
    elif add_ml_prefix:
        # Filter to only ML lines (1-4, ML1-ML4) and normalize
        lines = {normalize_ml_line(x) for x in lines if is_ml_line(x)}

    # Separate L-lines, ML-lines, R, and others
    l_lines = []
    ml_lines = []
    r_line = []
    others = []

    for line in lines:
        if line.startswith('ML') and line[2:].isdigit():
            ml_lines.append(line)
        elif line.startswith('L') and line[1:].isdigit():
            l_lines.append(line)
        elif line == 'R':
            r_line.append(line)
        else:
            others.append(line)

    # Sort numerically
    l_lines.sort(key=lambda x: int(x[1:]))
    ml_lines.sort(key=lambda x: int(x[2:]))
    others.sort()

    return ', '.join(l_lines + ml_lines + r_line + others)


def populate_connections(db: Session, max_distance_meters: float = DEFAULT_MAX_DISTANCE) -> dict:
    """Populate cor_metro, cor_ml, cor_cercanias for all stops based on proximity.

    Handles:
    - Madrid: RENFE, METRO, ML stops
    - Sevilla: RENFE, METRO_SEV, TRAM_SEV stops

    Returns:
        Dictionary with statistics about updates made.
    """
    stats = {
        'renfe_updated': 0,
        'metro_updated': 0,
        'ml_updated': 0,
        'metro_sev_updated': 0,
        'tranvia_sev_updated': 0,
        'connections_found': [],
    }

    all_stops = db.query(StopModel).all()
    logger.info(f"Processing {len(all_stops)} stops with max distance {max_distance_meters}m")

    # Group stops by type
    stops_by_type = {
        'renfe': [],
        'metro': [],
        'ml': [],
        'metro_sev': [],
        'tranvia_sev': [],
    }

    for stop in all_stops:
        stop_type = get_stop_type(stop.id)
        if stop_type in stops_by_type:
            stops_by_type[stop_type].append(stop)

    logger.info(f"Found: RENFE={len(stops_by_type['renfe'])}, "
                f"METRO={len(stops_by_type['metro'])}, ML={len(stops_by_type['ml'])}, "
                f"METRO_SEV={len(stops_by_type['metro_sev'])}, "
                f"TRAM_SEV={len(stops_by_type['tranvia_sev'])}")

    # Helper to get lines from nearby stops OR stops with matching names
    def get_matching_lines(source_stop, target_stops, check_same_nucleo: bool = True):
        """Get lines from target stops that match source by proximity OR name.

        Args:
            source_stop: The stop to find connections for
            target_stops: List of potential target stops
            check_same_nucleo: If True, only consider stops in the same núcleo
        """
        lines = set()

        for target in target_stops:
            # Skip if different núcleo (for cross-system in same city)
            if check_same_nucleo and source_stop.nucleo_id != target.nucleo_id:
                continue

            # Check proximity only (name matching removed to avoid false positives)
            dist = haversine_distance(source_stop.lat, source_stop.lon, target.lat, target.lon)
            is_near = dist <= max_distance_meters

            if is_near and target.lineas:
                for line in target.lineas.split(','):
                    line = line.strip()
                    if line:
                        lines.add(line)

        return lines

    # === MADRID CONNECTIONS ===

    # RENFE stops -> Metro/ML connections
    for renfe in stops_by_type['renfe']:
        metro_lines = get_matching_lines(renfe, stops_by_type['metro'])
        ml_lines = get_matching_lines(renfe, stops_by_type['ml'])

        if metro_lines or ml_lines:
            renfe.cor_metro = sort_lines(metro_lines, add_l_prefix=True) if metro_lines else renfe.cor_metro
            renfe.cor_ml = sort_lines(ml_lines, add_ml_prefix=True) if ml_lines else renfe.cor_ml
            stats['renfe_updated'] += 1
            logger.info(f"  {renfe.name}: Metro={renfe.cor_metro}, ML={renfe.cor_ml}")

    # Metro stops -> Cercanías connections
    for metro in stops_by_type['metro']:
        cercanias = get_matching_lines(metro, stops_by_type['renfe'])
        if cercanias:
            metro.cor_cercanias = sort_lines(cercanias)
            stats['metro_updated'] += 1
            logger.info(f"  {metro.name} (Metro): Cercanías={metro.cor_cercanias}")

    # ML stops -> Cercanías connections
    for ml in stops_by_type['ml']:
        cercanias = get_matching_lines(ml, stops_by_type['renfe'])
        if cercanias:
            ml.cor_cercanias = sort_lines(cercanias)
            stats['ml_updated'] += 1
            logger.info(f"  {ml.name} (ML): Cercanías={ml.cor_cercanias}")

    # === SEVILLA CONNECTIONS ===
    # In Sevilla, there's RENFE Cercanías, Metro L1, and Tranvía T1

    # Metro Sevilla -> Cercanías and Tranvía connections
    for metro_sev in stops_by_type['metro_sev']:
        cercanias = get_matching_lines(metro_sev, stops_by_type['renfe'])
        tranvia_lines = get_matching_lines(metro_sev, stops_by_type['tranvia_sev'])

        updated = False
        if cercanias:
            metro_sev.cor_cercanias = sort_lines(cercanias)
            updated = True
        if tranvia_lines:
            metro_sev.cor_tranvia = sort_lines(tranvia_lines)
            updated = True

        if updated:
            stats['metro_sev_updated'] += 1
            logger.info(f"  {metro_sev.name} (Metro SEV): Cercanías={metro_sev.cor_cercanias}, Tranvía={metro_sev.cor_tranvia}")

    # Tranvía Sevilla -> Metro and Cercanías connections
    for tranvia in stops_by_type['tranvia_sev']:
        metro_lines = get_matching_lines(tranvia, stops_by_type['metro_sev'])
        cercanias = get_matching_lines(tranvia, stops_by_type['renfe'])

        updated = False
        if metro_lines:
            tranvia.cor_metro = sort_lines(metro_lines, add_l_prefix=True)
            updated = True
        if cercanias:
            tranvia.cor_cercanias = sort_lines(cercanias)
            updated = True

        if updated:
            stats['tranvia_sev_updated'] += 1
            logger.info(f"  {tranvia.name} (Tranvía): Metro={tranvia.cor_metro}, Cercanías={tranvia.cor_cercanias}")

    # RENFE Sevilla -> Metro Sevilla and Tranvía connections (same nucleo_id = 30)
    sevilla_renfe = [s for s in stops_by_type['renfe'] if s.nucleo_id == 30]
    for renfe in sevilla_renfe:
        metro_sev_lines = get_matching_lines(renfe, stops_by_type['metro_sev'])
        tranvia_lines = get_matching_lines(renfe, stops_by_type['tranvia_sev'])

        updated = False
        if metro_sev_lines:
            # Append to existing cor_metro if present
            existing = set(renfe.cor_metro.split(', ')) if renfe.cor_metro else set()
            all_lines = existing | metro_sev_lines
            renfe.cor_metro = sort_lines(all_lines, add_l_prefix=True)
            updated = True
        if tranvia_lines:
            renfe.cor_tranvia = sort_lines(tranvia_lines)
            updated = True

        if updated:
            logger.info(f"  {renfe.name} (RENFE SEV): Metro={renfe.cor_metro}, Tranvía={renfe.cor_tranvia}")

    db.commit()
    return stats


def populate_connections_for_network(db: Session, network_id: str, max_distance_meters: float = DEFAULT_MAX_DISTANCE) -> dict:
    """Populate connections for stops in a specific network area.

    This function is meant to be called automatically after importing GTFS data
    for a specific transit system. It will find all connections between the
    newly imported stops and existing stops from other systems in the same area.

    Args:
        db: Database session (will commit changes)
        network_id: The network ID (e.g., '11T' for Metro Madrid, '12T' for ML Madrid)
        max_distance_meters: Maximum distance for proximity matching

    Returns:
        Dictionary with statistics about updates made.
    """
    stats = {'stops_updated': 0, 'connections_found': 0}

    # Map network_id to stop prefixes to search for
    # Networks in the same area should find connections
    NETWORK_STOP_PREFIXES = {
        '11T': ['METRO_', 'RENFE_10', 'RENFE_90', 'ML_'],  # Metro Madrid area
        '12T': ['ML_', 'RENFE_10', 'RENFE_90', 'METRO_'],  # Metro Ligero Madrid area
        '10T': ['RENFE_10', 'METRO_', 'ML_'],  # Cercanías Madrid area
        '90T': ['RENFE_90', 'METRO_', 'ML_'],  # C-9 Madrid area
        '32T': ['METRO_SEV_', 'RENFE_30', 'TRAM_SEV_'],  # Metro Sevilla area
        '31T': ['TRAM_SEV_', 'RENFE_30', 'METRO_SEV_'],  # Tram Sevilla area
        '30T': ['RENFE_30', 'METRO_SEV_', 'TRAM_SEV_'],  # Cercanías Sevilla area
    }

    prefixes = NETWORK_STOP_PREFIXES.get(network_id)
    if not prefixes:
        logger.info(f"No stop prefix mapping for network {network_id}")
        return stats

    # Get all stops matching any of the prefixes
    all_stops = []
    for prefix in prefixes:
        stops = db.query(StopModel).filter(StopModel.id.like(f'{prefix}%')).all()
        all_stops.extend(stops)

    if not all_stops:
        logger.info(f"No stops found for network {network_id}")
        return stats

    # Group by type
    stops_by_type = {
        'renfe': [],
        'metro': [],
        'ml': [],
        'metro_sev': [],
        'tranvia_sev': [],
    }

    for stop in all_stops:
        stop_type = get_stop_type(stop.id)
        if stop_type in stops_by_type:
            stops_by_type[stop_type].append(stop)

    logger.info(f"Network {network_id}: RENFE={len(stops_by_type['renfe'])}, "
                f"METRO={len(stops_by_type['metro'])}, ML={len(stops_by_type['ml'])}, "
                f"METRO_SEV={len(stops_by_type['metro_sev'])}, "
                f"TRAM_SEV={len(stops_by_type['tranvia_sev'])}")

    # Helper function (same logic as populate_connections)
    def get_lines(source_stop, target_stops):
        lines = set()
        for target in target_stops:
            dist = haversine_distance(source_stop.lat, source_stop.lon, target.lat, target.lon)
            is_near = dist <= max_distance_meters

            if is_near and target.lineas:
                for line in target.lineas.split(','):
                    line = line.strip()
                    if line:
                        lines.add(line)
        return lines

    # Madrid logic (networks 10T, 11T, 12T, 90T)
    if network_id in ('10T', '11T', '12T', '90T'):
        # RENFE -> Metro/ML
        for renfe in stops_by_type['renfe']:
            metro_lines = get_lines(renfe, stops_by_type['metro'])
            ml_lines = get_lines(renfe, stops_by_type['ml'])
            if metro_lines:
                renfe.cor_metro = sort_lines(metro_lines, add_l_prefix=True)
            if ml_lines:
                renfe.cor_ml = sort_lines(ml_lines, add_ml_prefix=True)
            if metro_lines or ml_lines:
                stats['stops_updated'] += 1

        # Metro -> Cercanías
        for metro in stops_by_type['metro']:
            cercanias = get_lines(metro, stops_by_type['renfe'])
            if cercanias:
                metro.cor_cercanias = sort_lines(cercanias)
                stats['stops_updated'] += 1

        # ML -> Cercanías
        for ml in stops_by_type['ml']:
            cercanias = get_lines(ml, stops_by_type['renfe'])
            if cercanias:
                ml.cor_cercanias = sort_lines(cercanias)
                stats['stops_updated'] += 1

    # Sevilla logic (networks 30T, 31T, 32T)
    elif network_id in ('30T', '31T', '32T'):
        # Metro Sevilla -> Cercanías and Tranvía
        for metro_sev in stops_by_type['metro_sev']:
            cercanias = get_lines(metro_sev, stops_by_type['renfe'])
            tranvia_lines = get_lines(metro_sev, stops_by_type['tranvia_sev'])
            updated = False
            if cercanias:
                metro_sev.cor_cercanias = sort_lines(cercanias)
                updated = True
            if tranvia_lines:
                metro_sev.cor_tranvia = sort_lines(tranvia_lines)
                updated = True
            if updated:
                stats['stops_updated'] += 1
                logger.info(f"  {metro_sev.name} (Metro SEV): Cercanías={metro_sev.cor_cercanias}, Tranvía={metro_sev.cor_tranvia}")

        # Tranvía -> Metro and Cercanías
        for tranvia in stops_by_type['tranvia_sev']:
            metro_lines = get_lines(tranvia, stops_by_type['metro_sev'])
            cercanias = get_lines(tranvia, stops_by_type['renfe'])
            updated = False
            if metro_lines:
                tranvia.cor_metro = sort_lines(metro_lines, add_l_prefix=True)
                updated = True
            if cercanias:
                tranvia.cor_cercanias = sort_lines(cercanias)
                updated = True
            if updated:
                stats['stops_updated'] += 1
                logger.info(f"  {tranvia.name} (Tranvía): Metro={tranvia.cor_metro}, Cercanías={tranvia.cor_cercanias}")

        # RENFE -> Metro Sevilla and Tranvía
        for renfe in stops_by_type['renfe']:
            metro_lines = get_lines(renfe, stops_by_type['metro_sev'])
            tranvia_lines = get_lines(renfe, stops_by_type['tranvia_sev'])
            updated = False
            if metro_lines:
                existing = set(renfe.cor_metro.split(', ')) if renfe.cor_metro else set()
                all_lines = existing | metro_lines
                renfe.cor_metro = sort_lines(all_lines, add_l_prefix=True)
                updated = True
            if tranvia_lines:
                renfe.cor_tranvia = sort_lines(tranvia_lines)
                updated = True
            if updated:
                stats['stops_updated'] += 1
                logger.info(f"  {renfe.name} (RENFE): Metro={renfe.cor_metro}, Tranvía={renfe.cor_tranvia}")

    db.commit()
    logger.info(f"Populated connections for {stats['stops_updated']} stops in network {network_id}")
    return stats


# Backwards compatibility wrapper
def populate_connections_for_nucleo(db: Session, nucleo_id: int, max_distance_meters: float = DEFAULT_MAX_DISTANCE) -> dict:
    """Deprecated: Use populate_connections_for_network instead.

    This wrapper maps old nucleo IDs to new network IDs.
    """
    NUCLEO_TO_NETWORK = {
        10: '10T',  # Madrid Cercanías -> can use 11T/12T for Metro
        30: '30T',  # Sevilla Cercanías
    }
    network_id = NUCLEO_TO_NETWORK.get(nucleo_id, f'{nucleo_id}T')
    return populate_connections_for_network(db, network_id, max_distance_meters)


def main():
    """Run the stop connections population."""
    # Get max distance from command line or use default
    max_distance = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MAX_DISTANCE

    logger.info(f"Starting stop connections population (max distance: {max_distance}m)...")

    db = SessionLocal()
    try:
        stats = populate_connections(db, max_distance)

        logger.info("=" * 60)
        logger.info("POPULATION COMPLETE")
        logger.info("=" * 60)
        logger.info("Madrid:")
        logger.info(f"  RENFE stops with Metro/ML connections: {stats['renfe_updated']}")
        logger.info(f"  Metro stops with Cercanías connections: {stats['metro_updated']}")
        logger.info(f"  ML stops with Cercanías connections: {stats['ml_updated']}")
        logger.info("Sevilla:")
        logger.info(f"  Metro SEV stops with connections: {stats['metro_sev_updated']}")
        logger.info(f"  Tranvía stops with connections: {stats['tranvia_sev_updated']}")

    except Exception as e:
        logger.error(f"Population failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
