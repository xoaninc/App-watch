#!/usr/bin/env python3
"""Import real Metro Madrid shapes from CRTM Feature Service.

This script imports actual line geometries from CRTM's M4_Tramos layer,
replacing the BRouter-generated shapes which may not follow actual tracks.

Source: Layer 4 (M4_Tramos) from CRTM Feature Service
- NUMEROLINEAUSUARIO: Line number (1, 2, 7a, 10b, 12-1...)
- SENTIDO: Direction (1 or 2)
- NUMEROORDEN: Sequence order
- geometry: LineString with coordinates

Coordinates are in UTM EPSG:25830 and converted to WGS84 EPSG:4326.

Usage:
    python scripts/import_metro_madrid_shapes.py [--route METRO_X] [--dry-run]
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from pyproj import Transformer
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CRTM Feature Service endpoint
CRTM_TRAMOS_URL = "https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M4_Red/FeatureServer/4/query"

# Coordinate transformer: UTM Zone 30N (EPSG:25830) -> WGS84 (EPSG:4326)
transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)

# Line number normalization mapping
# CRTM uses variants like "7a", "7b", "10a", "12-1" etc.
# We need to map these to our route IDs (METRO_7, METRO_7B, etc.)
LINE_MAPPING = {
    '1': '1',
    '2': '2',
    '3': '3',
    '4': '4',
    '5': '5',
    '6': '6',
    '7': '7',
    '7a': '7',
    '7b': '7B',
    '8': '8',
    '9': '9',
    '9a': '9',
    '9b': '9B',
    '10': '10',
    '10a': '10',
    '10b': '10B',
    '11': '11',
    '12': '12',
    '12-1': '12',  # Circular line variants
    '12-2': '12',
    'R': 'R',
    'r': 'R',
}


def fetch_tramos() -> List[Dict]:
    """Fetch all tramo features from CRTM Feature Service with geometry."""
    features = []
    offset = 0
    batch_size = 1000

    while True:
        params = {
            'where': '1=1',
            'outFields': 'NUMEROLINEAUSUARIO,SENTIDO,NUMEROORDEN',
            'returnGeometry': 'true',
            'f': 'json',
            # Request in native UTM format (we'll convert ourselves for accuracy)
            'outSR': '25830',
            'resultOffset': offset,
            'resultRecordCount': batch_size,
        }

        try:
            response = requests.get(CRTM_TRAMOS_URL, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()

            batch_features = data.get('features', [])
            if not batch_features:
                break

            features.extend(batch_features)
            offset += batch_size
            logger.info(f"  Fetched {len(features)} tramos...")

            if len(batch_features) < batch_size:
                break

        except Exception as e:
            logger.error(f"Error fetching tramos: {e}")
            raise

    logger.info(f"Total tramos fetched: {len(features)}")
    return features


def normalize_line(line_str: str) -> Optional[str]:
    """Normalize CRTM line number to our route line format.

    Args:
        line_str: Raw line from CRTM (e.g., "7a", "10b", "12-1")

    Returns:
        Normalized line for shape_id (e.g., "7", "7B", "10B")
    """
    if not line_str:
        return None

    line_lower = line_str.strip().lower()

    # Direct mapping
    if line_lower in LINE_MAPPING:
        return LINE_MAPPING[line_lower]

    # Try without variants
    base = line_lower.rstrip('ab').replace('-1', '').replace('-2', '')
    if base in LINE_MAPPING:
        return LINE_MAPPING[base]

    logger.warning(f"Unknown line format: {line_str}")
    return None


def convert_coords(utm_coords: List[List[float]]) -> List[Tuple[float, float]]:
    """Convert UTM coordinates to WGS84 (lat, lon) format.

    Args:
        utm_coords: List of [x, y] UTM coordinates

    Returns:
        List of (lat, lon) tuples in WGS84
    """
    result = []
    for coord in utm_coords:
        if len(coord) >= 2:
            # UTM coords are [x, y] = [easting, northing]
            lon, lat = transformer.transform(coord[0], coord[1])
            result.append((lat, lon))
    return result


def process_tramos(features: List[Dict]) -> Dict[str, Dict[str, List[Tuple[int, List[Tuple[float, float]]]]]]:
    """Group and process tramos by line and direction.

    Returns:
        Dict of {line: {sentido: [(orden, coords), ...]}}
    """
    # Structure: {line: {sentido: [(orden, coords), ...]}}
    grouped: Dict[str, Dict[str, List[Tuple[int, List[Tuple[float, float]]]]]] = {}

    for feature in features:
        attrs = feature.get('attributes', {})
        geom = feature.get('geometry', {})

        raw_line = attrs.get('NUMEROLINEAUSUARIO', '')
        sentido = str(attrs.get('SENTIDO', '1'))  # Convert to string for consistent keys
        orden = attrs.get('NUMEROORDEN', 0)

        line = normalize_line(str(raw_line))
        if not line:
            continue

        # Get geometry paths (can be multipath)
        paths = geom.get('paths', [])
        if not paths:
            continue

        # Convert coordinates
        coords = []
        for path in paths:
            converted = convert_coords(path)
            coords.extend(converted)

        if not coords:
            continue

        # Group by line and direction
        if line not in grouped:
            grouped[line] = {}
        if sentido not in grouped[line]:
            grouped[line][sentido] = []

        grouped[line][sentido].append((orden, coords))

    return grouped


def build_shape_coords(tramo_list: List[Tuple[int, List[Tuple[float, float]]]]) -> List[Tuple[float, float]]:
    """Build continuous shape from ordered tramo segments.

    Args:
        tramo_list: List of (orden, coords) tuples

    Returns:
        Continuous list of (lat, lon) coordinates
    """
    # Sort by order
    sorted_tramos = sorted(tramo_list, key=lambda x: x[0])

    all_coords = []
    for orden, coords in sorted_tramos:
        if not coords:
            continue

        if all_coords:
            # Skip first point if it's close to the last point (avoid duplicates)
            if len(coords) > 0:
                last = all_coords[-1]
                first = coords[0]
                # If points are very close (within ~10 meters), skip first
                if abs(last[0] - first[0]) < 0.0001 and abs(last[1] - first[1]) < 0.0001:
                    coords = coords[1:]
        all_coords.extend(coords)

    return all_coords


def save_shape(db, shape_id: str, coords: List[Tuple[float, float]], dry_run: bool) -> int:
    """Save shape to database.

    Returns:
        Number of points saved
    """
    if dry_run:
        return len(coords)

    # Delete existing shape points first (due to FK constraint)
    db.execute(text('DELETE FROM gtfs_shape_points WHERE shape_id = :shape_id'),
               {'shape_id': shape_id})

    # Insert or update shape record
    db.execute(text('''
        INSERT INTO gtfs_shapes (id)
        VALUES (:shape_id)
        ON CONFLICT (id) DO NOTHING
    '''), {'shape_id': shape_id})

    # Insert shape points
    for seq, (lat, lon) in enumerate(coords):
        db.execute(text('''
            INSERT INTO gtfs_shape_points (shape_id, lat, lon, sequence)
            VALUES (:shape_id, :lat, :lon, :seq)
        '''), {'shape_id': shape_id, 'lat': lat, 'lon': lon, 'seq': seq})

    return len(coords)


def update_trips_shape(db, route_id: str, shape_id: str, dry_run: bool) -> int:
    """Update trips to use the new shape.

    Returns:
        Number of trips updated
    """
    if dry_run:
        result = db.execute(text('''
            SELECT COUNT(*) FROM gtfs_trips WHERE route_id = :route_id
        '''), {'route_id': route_id}).scalar()
        return result or 0

    result = db.execute(text('''
        UPDATE gtfs_trips SET shape_id = :shape_id
        WHERE route_id = :route_id
    '''), {'shape_id': shape_id, 'route_id': route_id})

    return result.rowcount


def import_shapes(db, target_route: Optional[str] = None, dry_run: bool = False) -> Dict[str, int]:
    """Import shapes from CRTM for Metro Madrid lines.

    Args:
        db: Database session
        target_route: Optional specific route to import (e.g., "METRO_10")
        dry_run: If True, don't make any changes

    Returns:
        Statistics dict
    """
    stats = {
        'shapes_created': 0,
        'total_points': 0,
        'trips_updated': 0,
    }

    logger.info("Fetching tramos from CRTM...")
    features = fetch_tramos()

    logger.info("Processing tramos...")
    grouped = process_tramos(features)

    logger.info(f"Found {len(grouped)} lines with geometry")

    for line, directions in sorted(grouped.items()):
        route_id = f"METRO_{line}"

        # Skip if targeting a specific route
        if target_route and route_id != target_route:
            continue

        # Use direction '1' as primary (or '2' if '1' not available)
        if '1' in directions:
            tramo_list = directions['1']
        elif '2' in directions:
            tramo_list = directions['2']
        else:
            logger.warning(f"No valid direction for {route_id}")
            continue

        # Build continuous shape
        coords = build_shape_coords(tramo_list)

        if not coords:
            logger.warning(f"No coordinates for {route_id}")
            continue

        # Shape ID format matches existing convention
        shape_id = f"METRO_MAD_{line}_CRTM"

        logger.info(f"  {route_id}: {len(coords)} points")

        # Save shape
        points = save_shape(db, shape_id, coords, dry_run)
        stats['shapes_created'] += 1
        stats['total_points'] += points

        # Update trips
        trips = update_trips_shape(db, route_id, shape_id, dry_run)
        stats['trips_updated'] += trips

    if not dry_run:
        db.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(description='Import Metro Madrid shapes from CRTM')
    parser.add_argument('--route', type=str, help='Import for specific route (e.g., METRO_10)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without saving')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made")

        stats = import_shapes(db, target_route=args.route, dry_run=args.dry_run)

        logger.info("=" * 60)
        logger.info("IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Shapes created: {stats['shapes_created']}")
        logger.info(f"Total points: {stats['total_points']:,}")
        logger.info(f"Trips updated: {stats['trips_updated']}")
        if args.dry_run:
            logger.info("[DRY RUN - no changes saved]")
        logger.info("=" * 60)

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
