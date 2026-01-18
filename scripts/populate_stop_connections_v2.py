#!/usr/bin/env python3
"""Script to populate cor_metro, cor_ml, cor_cercanias, cor_tranvia fields.

NEW LOGIC (v2):
Each stop's cor_X field contains ALL lines of type X available in its interchange.
This includes the stop's own lines if it's of that type.

Example - Nuevos Ministerios interchange:
  - METRO_XX has lines: 6, 8, 10
  - RENFE_YY has lines: C1, C2, C3, C4a, C4b, C7, C8a, C8b, C10

Result for BOTH stops:
  - cor_metro = "L6, L8, L10"
  - cor_cercanias = "C1, C2, C3, C4a, C4b, C7, C8a, C8b, C10"
"""

import sys
import logging
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
from collections import defaultdict

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from core.database import SessionLocal
# Import all models to ensure relationships are resolved
from src.gtfs_bc.nucleo.infrastructure.models import NucleoModel
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_MAX_DISTANCE = 150  # meters


def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two coordinates."""
    R = 6371000
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def get_stop_type(stop_id):
    """Get stop type from ID prefix."""
    # Check most specific prefixes first
    if stop_id.startswith('METRO_SEV_'):
        return 'metro_sev'
    if stop_id.startswith('TRAM_SEV_'):
        return 'tranvia_sev'
    if stop_id.startswith('METRO_BILBAO_'):
        return 'metro_bilbao'
    if stop_id.startswith('METRO_MALAGA_'):
        return 'metro_malaga'
    if stop_id.startswith('METRO_GRANADA_'):
        return 'metro_granada'
    if stop_id.startswith('METRO_VALENCIA_'):
        return 'metro_valencia'
    if stop_id.startswith('METRO_TENERIFE_'):
        return 'metro_tenerife'
    if stop_id.startswith('TMB_METRO_'):
        return 'tmb_metro'
    if stop_id.startswith('FGC_'):
        return 'fgc'
    if stop_id.startswith('EUSKOTREN_'):
        return 'euskotren'
    if stop_id.startswith('TRAM_BARCELONA_BESOS_'):
        return 'tram_bcn_besos'
    if stop_id.startswith('TRAM_BARCELONA_'):
        return 'tram_bcn'
    if stop_id.startswith('TRAM_ALICANTE_'):
        return 'tram_alicante'
    if stop_id.startswith('TRANVIA_ZARAGOZA_'):
        return 'tranvia_zaragoza'
    if stop_id.startswith('TRANVIA_MURCIA_'):
        return 'tranvia_murcia'
    if stop_id.startswith('SFM_MALLORCA_'):
        return 'sfm_mallorca'
    if stop_id.startswith('METRO_'):
        return 'metro'
    if stop_id.startswith('ML_'):
        return 'ml'
    if stop_id.startswith('RENFE_'):
        return 'renfe'
    return 'unknown'


def normalize_line(line, stop_type):
    """Normalize line name based on stop type."""
    line = line.strip()
    if not line:
        return None

    # Metro Madrid: add L prefix if missing
    if stop_type == 'metro':
        if line.isdigit() and 1 <= int(line) <= 12:
            return f'L{line}'
        if line in ('7B', '9B', '10B'):
            return f'L{line}'
        if line.startswith('L'):
            return line
        if line == 'R':
            return 'R'
        return None

    # Metro Ligero Madrid: add ML prefix if missing
    if stop_type == 'ml':
        if line.isdigit() and 1 <= int(line) <= 4:
            return f'ML{line}'
        if line.startswith('ML'):
            return line
        return None

    # Metro Sevilla: add L prefix
    if stop_type == 'metro_sev':
        if line.isdigit():
            return f'L{line}'
        if line.startswith('L'):
            return line
        return None

    # TMB Metro Barcelona: add L prefix
    if stop_type == 'tmb_metro':
        if line.isdigit():
            return f'L{line}'
        if line.startswith('L'):
            return line
        return line

    # Other metros (Bilbao, Málaga, Granada, Valencia) - keep as-is
    if stop_type in ('metro_bilbao', 'metro_malaga', 'metro_granada', 'metro_valencia'):
        return line

    # Tenerife light rail
    if stop_type == 'metro_tenerife':
        return line

    # Trams (Sevilla, Barcelona, Alicante, Zaragoza, Murcia)
    if stop_type in ('tranvia_sev', 'tram_bcn', 'tram_bcn_besos', 'tram_alicante', 'tranvia_zaragoza', 'tranvia_murcia'):
        return line

    # FGC (suburban rail Barcelona)
    if stop_type == 'fgc':
        return line

    # Euskotren (suburban rail Basque Country)
    if stop_type == 'euskotren':
        return line

    # SFM Mallorca (trains and metro)
    if stop_type == 'sfm_mallorca':
        return line

    # Cercanías RENFE: keep as-is
    if stop_type == 'renfe':
        return line

    return line


# Mapping of stop types to connection field categories
METRO_TYPES = {'metro', 'metro_sev', 'tmb_metro', 'metro_bilbao', 'metro_malaga', 'metro_granada', 'metro_valencia'}
TRAM_TYPES = {'tranvia_sev', 'tram_bcn', 'tram_bcn_besos', 'tram_alicante', 'metro_tenerife', 'tranvia_zaragoza', 'tranvia_murcia'}
CERCANIAS_TYPES = {'renfe', 'fgc', 'euskotren', 'sfm_mallorca'}
ML_TYPES = {'ml'}

# Lines that should be classified as metro even if operator is different
FGC_METRO_LINES = {'L6', 'L7', 'L8', 'L12'}
EUSKOTREN_METRO_LINES = {'L3'}


def classify_line(line, stop_type):
    """Classify a line into metro/tram/cercanias based on operator and line name."""
    # FGC metro lines (L6, L7, L8, L12) should be metro
    if stop_type == 'fgc' and line in FGC_METRO_LINES:
        return 'metro'
    # Euskotren L3 is Metro Bilbao
    if stop_type == 'euskotren' and line in EUSKOTREN_METRO_LINES:
        return 'metro'
    # Default classification by operator type
    if stop_type in METRO_TYPES:
        return 'metro'
    if stop_type in ML_TYPES:
        return 'ml'
    if stop_type in CERCANIAS_TYPES:
        return 'cercanias'
    if stop_type in TRAM_TYPES:
        return 'tranvia'
    return None


def sort_lines(lines):
    """Sort lines: L-lines first (numerically), then C-lines, then others."""
    if not lines:
        return None

    l_lines = []  # L1, L2, etc.
    ml_lines = []  # ML1, ML2, etc.
    c_lines = []  # C1, C2, etc.
    others = []

    for line in lines:
        if line.startswith('ML') and line[2:].isdigit():
            ml_lines.append((int(line[2:]), line))
        elif line.startswith('L') and line[1:].replace('B', '').isdigit():
            # Handle L7B, L9B, L10B
            num = line[1:].replace('B', '')
            ml_lines.append((int(num) + 0.5 if 'B' in line else int(num), line))
        elif line.startswith('C') and line[1:].replace('a', '').replace('b', '').isdigit():
            # Handle C4a, C4b, C8a, C8b
            base = line[1:].replace('a', '').replace('b', '')
            suffix = 0.1 if 'a' in line else 0.2 if 'b' in line else 0
            c_lines.append((int(base) + suffix, line))
        elif line == 'R':
            others.append(('R', line))
        else:
            others.append((line, line))

    l_lines.sort(key=lambda x: x[0])
    ml_lines.sort(key=lambda x: x[0])
    c_lines.sort(key=lambda x: x[0])
    others.sort(key=lambda x: x[0])

    result = [x[1] for x in l_lines + ml_lines + c_lines + others]
    return ', '.join(result) if result else None


def populate_connections(db: Session, max_distance: float = DEFAULT_MAX_DISTANCE):
    """Populate cor_* fields for all stops.

    For each stop, find all stops within max_distance (same interchange),
    then set cor_X = all lines of type X from ALL stops in the interchange.
    """
    logger.info(f"Loading stops...")
    all_stops = db.query(StopModel).all()
    logger.info(f"Found {len(all_stops)} stops")

    # Build index by nucleo for faster lookup
    stops_by_nucleo = defaultdict(list)
    for stop in all_stops:
        if stop.nucleo_id:
            stops_by_nucleo[stop.nucleo_id].append(stop)

    updated = 0

    for stop in all_stops:
        if not stop.nucleo_id or not stop.lat or not stop.lon:
            continue

        # Find all stops in the same interchange (within distance)
        nearby_stops = []
        for other in stops_by_nucleo[stop.nucleo_id]:
            if other.id == stop.id:
                nearby_stops.append(other)  # Include self
            elif haversine(stop.lat, stop.lon, other.lat, other.lon) <= max_distance:
                nearby_stops.append(other)

        if len(nearby_stops) <= 1:
            # No interchange, just self - still populate own lines
            nearby_stops = [stop]

        # Collect ALL lines by type from ALL stops in interchange
        metro_lines = set()
        ml_lines = set()
        cercanias_lines = set()
        tranvia_lines = set()

        for nearby in nearby_stops:
            if not nearby.lineas:
                continue

            nearby_type = get_stop_type(nearby.id)

            for line in nearby.lineas.split(','):
                normalized = normalize_line(line, nearby_type)
                if not normalized:
                    continue

                # Use classify_line to handle special cases (FGC metro, Euskotren L3)
                line_class = classify_line(normalized, nearby_type)
                if line_class == 'metro':
                    metro_lines.add(normalized)
                elif line_class == 'ml':
                    ml_lines.add(normalized)
                elif line_class == 'cercanias':
                    cercanias_lines.add(normalized)
                elif line_class == 'tranvia':
                    tranvia_lines.add(normalized)

        # Update stop with collected lines
        new_cor_metro = sort_lines(metro_lines)
        new_cor_ml = sort_lines(ml_lines)
        new_cor_cercanias = sort_lines(cercanias_lines)
        new_cor_tranvia = sort_lines(tranvia_lines)

        changed = False
        if stop.cor_metro != new_cor_metro:
            stop.cor_metro = new_cor_metro
            changed = True
        if stop.cor_ml != new_cor_ml:
            stop.cor_ml = new_cor_ml
            changed = True
        if stop.cor_cercanias != new_cor_cercanias:
            stop.cor_cercanias = new_cor_cercanias
            changed = True
        if stop.cor_tranvia != new_cor_tranvia:
            stop.cor_tranvia = new_cor_tranvia
            changed = True

        if changed:
            updated += 1
            if len(nearby_stops) > 1:
                logger.info(f"{stop.id} ({stop.name}): metro={new_cor_metro}, ml={new_cor_ml}, "
                           f"cercanias={new_cor_cercanias}, tranvia={new_cor_tranvia}")

    db.commit()
    logger.info(f"Updated {updated} stops")
    return updated


def main():
    max_distance = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MAX_DISTANCE
    logger.info(f"Populating connections (max distance: {max_distance}m)...")

    db = SessionLocal()
    try:
        updated = populate_connections(db, max_distance)
        logger.info(f"Done! Updated {updated} stops")
    finally:
        db.close()


if __name__ == "__main__":
    main()
