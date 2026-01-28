#!/usr/bin/env python3
"""Import Metro Madrid platform data from CRTM Feature Service.

This script imports official platform locations from CRTM's M4_Andenes layer,
replacing the OSM-sourced platform data with authoritative CRTM data.

Source: Layer 3 (M4_Andenes) from CRTM Feature Service
- DENOMINACIONESTACION: Station name
- DENOMINACION: Direction description (e.g., "Sentido LAS ROSAS")
- CODIGOESTACION: Station code for mapping to stop_id
- NIVEL: Platform depth level (-1, -2, etc.)
- NUMANDEN: Platform number
- ACCESOMINUSVALIDOS: Accessibility (Yes/No)
- X, Y: Coordinates in UTM EPSG:25830

Coordinates are converted from UTM EPSG:25830 to WGS84 EPSG:4326.

Usage:
    python scripts/import_metro_madrid_platforms.py [--dry-run]
"""

import os
import sys
import argparse
import logging
import re
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from pyproj import Transformer
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CRTM Feature Service endpoints
CRTM_ANDENES_URL = "https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M4_Red/FeatureServer/3/query"
CRTM_STATIONS_URL = "https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M4_Red/FeatureServer/0/query"

# Coordinate transformer: UTM Zone 30N (EPSG:25830) -> WGS84 (EPSG:4326)
transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)

# Metro line colors (hex without #)
METRO_COLORS = {
    '1': '2DBEF0',
    '2': 'ED1C24',
    '3': 'FFD000',
    '4': 'B65518',
    '5': '8FD400',
    '6': '98989B',
    '7': 'EE7518',
    '7B': 'EE7518',
    '8': 'EC82B1',
    '9': 'A60084',
    '9B': 'A60084',
    '10': '005AA9',
    '10B': '005AA9',
    '11': '009B3A',
    '12': 'A49800',
    'R': '005AA9',
}


def fetch_andenes() -> List[Dict]:
    """Fetch all platform features from CRTM Feature Service."""
    features = []
    offset = 0
    batch_size = 1000

    while True:
        params = {
            'where': '1=1',
            'outFields': 'DENOMINACIONESTACION,DENOMINACION,CODIGOESTACION,NIVEL,NUMANDEN,ACCESOMINUSVALIDOS,X,Y,IDFESTACION',
            'returnGeometry': 'true',
            'f': 'json',
            'outSR': '25830',  # Request in UTM for accurate conversion
            'resultOffset': offset,
            'resultRecordCount': batch_size,
        }

        try:
            response = requests.get(CRTM_ANDENES_URL, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            batch_features = data.get('features', [])
            if not batch_features:
                break

            features.extend(batch_features)
            offset += batch_size
            logger.info(f"  Fetched {len(features)} andenes...")

            if len(batch_features) < batch_size:
                break

        except Exception as e:
            logger.error(f"Error fetching andenes: {e}")
            raise

    logger.info(f"Total andenes fetched: {len(features)}")
    return features


def fetch_station_mapping() -> Dict[str, str]:
    """Fetch station code to stop_id mapping from existing stops.

    Returns:
        Dict mapping station codes to stop_ids
    """
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT id, code FROM gtfs_stops
            WHERE id LIKE 'METRO_%'
            AND code IS NOT NULL
        """)).fetchall()

        mapping = {}
        for row in result:
            if row[1]:  # code not null
                mapping[str(row[1])] = row[0]

        logger.info(f"Loaded {len(mapping)} station code mappings")
        return mapping
    finally:
        db.close()


def extract_line_from_idflinea(idf_linea: str) -> Optional[str]:
    """Extract line number from IDFLINEA field.

    IDFLINEA format: "4__<line>__<version>" or similar
    Examples: "4__1__0", "4__7B__0", "4__10__0"

    Args:
        idf_linea: Raw IDFLINEA value

    Returns:
        Normalized line number (e.g., "1", "7B", "10")
    """
    if not idf_linea:
        return None

    # Try to extract line from format "4__X__Y"
    parts = str(idf_linea).split('__')
    if len(parts) >= 2:
        line = parts[1].strip().upper()
        # Validate it's a known line
        if line in METRO_COLORS:
            return line

    return None


def extract_line_from_description(description: str) -> Optional[str]:
    """Try to extract line from platform description.

    The DENOMINACION field contains direction info like "Sentido LAS ROSAS"
    which doesn't directly tell us the line, but some patterns exist.

    Args:
        description: Platform description text

    Returns:
        Line number if detectable, None otherwise
    """
    # This is a fallback - IDFLINEA is more reliable
    # Could be enhanced with terminal station -> line mapping
    return None


def convert_point(x: float, y: float) -> Tuple[float, float]:
    """Convert UTM point to WGS84.

    Args:
        x: UTM easting
        y: UTM northing

    Returns:
        (lat, lon) tuple
    """
    lon, lat = transformer.transform(x, y)
    return (lat, lon)


def import_platforms(db, dry_run: bool = False) -> Dict[str, int]:
    """Import platform data from CRTM.

    Args:
        db: Database session
        dry_run: If True, don't make any changes

    Returns:
        Statistics dict
    """
    stats = {
        'platforms_imported': 0,
        'platforms_skipped': 0,
        'stations_without_mapping': 0,
    }

    # Get station code -> stop_id mapping
    station_mapping = fetch_station_mapping()

    logger.info("Fetching andenes from CRTM...")
    features = fetch_andenes()

    # Clear existing CRTM-sourced platforms for Metro
    if not dry_run:
        result = db.execute(text("""
            DELETE FROM stop_platform
            WHERE stop_id LIKE 'METRO_%'
            AND source = 'crtm'
        """))
        logger.info(f"Cleared {result.rowcount} existing CRTM platforms")

    # Track unique platforms to avoid duplicates
    seen_platforms = set()

    for feature in features:
        attrs = feature.get('attributes', {})
        geom = feature.get('geometry', {})

        station_name = attrs.get('DENOMINACIONESTACION', '')
        description = attrs.get('DENOMINACION', '')
        codigo = attrs.get('CODIGOESTACION', '')
        nivel = attrs.get('NIVEL')
        num_anden = attrs.get('NUMANDEN')
        accesible = attrs.get('ACCESOMINUSVALIDOS', '')
        idf_estacion = attrs.get('IDFESTACION', '')

        # Get coordinates - can be in attrs (X, Y) or geometry
        x = attrs.get('X') or (geom.get('x') if geom else None)
        y = attrs.get('Y') or (geom.get('y') if geom else None)

        if not codigo or not x or not y:
            stats['platforms_skipped'] += 1
            continue

        # Map station code to stop_id
        codigo_str = str(codigo)
        stop_id = station_mapping.get(codigo_str)

        if not stop_id:
            # Try with padded zeros
            stop_id = station_mapping.get(codigo_str.zfill(3))

        if not stop_id:
            # Create stop_id from code
            stop_id = f"METRO_{codigo_str}"
            stats['stations_without_mapping'] += 1

        # Extract line number - CRTM doesn't provide line info directly
        # We'll use platform number as the line identifier for now
        # This groups all platforms by their number at each station
        line = None

        # Try to extract from IDFESTACION (format: "4_XX" where 4 is MODO=Metro)
        if idf_estacion:
            line = extract_line_from_idflinea(idf_estacion)

        if not line:
            line = extract_line_from_description(description)

        if not line:
            # Use platform number as identifier - each platform serves different lines
            if num_anden:
                line = str(num_anden)
            else:
                stats['platforms_skipped'] += 1
                continue

        # Convert coordinates
        lat, lon = convert_point(x, y)

        # Get color for line
        color = METRO_COLORS.get(line, '')

        # Create unique key to avoid duplicates
        platform_key = (stop_id, line)
        if platform_key in seen_platforms:
            continue
        seen_platforms.add(platform_key)

        # Format description with direction
        platform_desc = description if description else None
        if platform_desc and nivel:
            platform_desc = f"{platform_desc} (Nivel {nivel})"
        elif nivel:
            platform_desc = f"Nivel {nivel}"

        if not dry_run:
            # Format lines field - platform numbers become "Andén X"
            if line.isdigit() and int(line) <= 10:
                lines_str = f"Andén {line}"
            elif line in METRO_COLORS:
                lines_str = f"L{line}"
            else:
                lines_str = line

            # Insert platform
            db.execute(text("""
                INSERT INTO stop_platform (stop_id, lines, lat, lon, source, color, description)
                VALUES (:stop_id, :lines, :lat, :lon, 'crtm', :color, :description)
                ON CONFLICT (stop_id, lines) DO UPDATE SET
                    lat = EXCLUDED.lat,
                    lon = EXCLUDED.lon,
                    source = EXCLUDED.source,
                    color = EXCLUDED.color,
                    description = EXCLUDED.description
            """), {
                'stop_id': stop_id,
                'lines': lines_str,
                'lat': lat,
                'lon': lon,
                'color': color,
                'description': platform_desc,
            })

        stats['platforms_imported'] += 1

    if not dry_run:
        db.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(description='Import Metro Madrid platforms from CRTM')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without saving')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made")

        stats = import_platforms(db, dry_run=args.dry_run)

        logger.info("=" * 60)
        logger.info("IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Platforms imported: {stats['platforms_imported']}")
        logger.info(f"Platforms skipped: {stats['platforms_skipped']}")
        logger.info(f"Stations without mapping: {stats['stations_without_mapping']}")
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
