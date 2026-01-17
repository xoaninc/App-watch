#!/usr/bin/env python3
"""Script to populate cor_metro and cor_ml fields based on stop proximity."""

import sys
import logging
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from core.database import SessionLocal

# Import all models to ensure relationships are configured
from src.gtfs_bc.nucleo.infrastructure.models import NucleoModel
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Default max distance in meters for considering stops as connected
DEFAULT_MAX_DISTANCE = 150


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two coordinates using Haversine formula."""
    R = 6371000  # Earth's radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def sort_lines(lines: set) -> str:
    """Sort lines: numbers first (numerically), then letters."""
    numeric = sorted([x for x in lines if x.isdigit()], key=int)
    alpha = sorted([x for x in lines if not x.isdigit()])
    return ', '.join(numeric + alpha)


def populate_connections(db: Session, max_distance_meters: float = DEFAULT_MAX_DISTANCE) -> dict:
    """Populate cor_metro and cor_ml for all stops based on proximity.

    Returns:
        Dictionary with statistics about updates made.
    """
    stats = {
        'renfe_updated': 0,
        'metro_updated': 0,
        'ml_updated': 0,
        'connections_found': [],
    }

    all_stops = db.query(StopModel).all()
    logger.info(f"Processing {len(all_stops)} stops with max distance {max_distance_meters}m")

    # Separate by type
    renfe_stops = [s for s in all_stops if s.id.startswith('RENFE_')]
    metro_stops = [s for s in all_stops if s.id.startswith('METRO_')]
    ml_stops = [s for s in all_stops if s.id.startswith('ML_')]

    logger.info(f"Found {len(renfe_stops)} RENFE, {len(metro_stops)} METRO, {len(ml_stops)} ML stops")

    # For each RENFE stop, find nearby Metro/ML stops
    for renfe in renfe_stops:
        metro_lines = set()
        ml_lines = set()

        for metro in metro_stops:
            dist = haversine_distance(renfe.lat, renfe.lon, metro.lat, metro.lon)
            if dist <= max_distance_meters and metro.lineas:
                for line in metro.lineas.split(','):
                    line = line.strip()
                    if line:
                        metro_lines.add(line)
                if metro_lines:
                    logger.debug(f"{renfe.name} <-> {metro.name} ({dist:.0f}m): Metro {metro.lineas}")

        for ml in ml_stops:
            dist = haversine_distance(renfe.lat, renfe.lon, ml.lat, ml.lon)
            if dist <= max_distance_meters and ml.lineas:
                for line in ml.lineas.split(','):
                    line = line.strip()
                    if line:
                        ml_lines.add(line)
                if ml_lines:
                    logger.debug(f"{renfe.name} <-> {ml.name} ({dist:.0f}m): ML {ml.lineas}")

        # Update if connections found
        if metro_lines or ml_lines:
            renfe.cor_metro = sort_lines(metro_lines) if metro_lines else None
            renfe.cor_ml = sort_lines(ml_lines) if ml_lines else None
            stats['renfe_updated'] += 1
            stats['connections_found'].append({
                'stop': renfe.name,
                'id': renfe.id,
                'cor_metro': renfe.cor_metro,
                'cor_ml': renfe.cor_ml,
            })
            logger.info(f"  {renfe.name}: Metro={renfe.cor_metro}, ML={renfe.cor_ml}")

    # For Metro stops, find nearby RENFE stops and add to cor_cercanias
    for metro in metro_stops:
        cercanias_lines = set()

        for renfe in renfe_stops:
            dist = haversine_distance(metro.lat, metro.lon, renfe.lat, renfe.lon)
            if dist <= max_distance_meters and renfe.lineas:
                for line in renfe.lineas.split(','):
                    line = line.strip()
                    if line:
                        cercanias_lines.add(line)

        if cercanias_lines:
            metro.cor_cercanias = sort_lines(cercanias_lines)
            stats['metro_updated'] += 1
            logger.info(f"  {metro.name} (Metro): Cercanías={metro.cor_cercanias}")

    # For ML stops, find nearby RENFE stops
    for ml in ml_stops:
        cercanias_lines = set()

        for renfe in renfe_stops:
            dist = haversine_distance(ml.lat, ml.lon, renfe.lat, renfe.lon)
            if dist <= max_distance_meters and renfe.lineas:
                for line in renfe.lineas.split(','):
                    line = line.strip()
                    if line:
                        cercanias_lines.add(line)

        if cercanias_lines:
            ml.cor_cercanias = sort_lines(cercanias_lines)
            stats['ml_updated'] += 1
            logger.info(f"  {ml.name} (ML): Cercanías={ml.cor_cercanias}")

    db.commit()
    return stats


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
        logger.info(f"RENFE stops with Metro/ML connections: {stats['renfe_updated']}")
        logger.info(f"Metro stops with Cercanías connections: {stats['metro_updated']}")
        logger.info(f"ML stops with Cercanías connections: {stats['ml_updated']}")

        if stats['connections_found']:
            logger.info("")
            logger.info("Connections found:")
            for conn in stats['connections_found']:
                logger.info(f"  {conn['stop']}: Metro={conn['cor_metro']}, ML={conn['cor_ml']}")

    except Exception as e:
        logger.error(f"Population failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
