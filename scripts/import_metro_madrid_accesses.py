#!/usr/bin/env python3
"""Import Metro Madrid access points (entrances) from CRTM Feature Service.

This script imports station entrance locations from CRTM's M4_Accesos layer,
storing them in the stop_access table.

Source: Layer 1 (M4_Accesos) from CRTM Feature Service
- DENOMINACION: Access name
- CODIGOESTACION: Station code for mapping to stop_id
- NOMBREVIA: Street name
- NUMEROPORTAL: Street number
- HORAAPERTURA: Opening time
- HORACIERRE: Closing time
- ACCESOMINUSVALIDOS: Wheelchair accessibility
- NIVEL: Entry level
- X, Y: Coordinates in UTM EPSG:25830

Coordinates are converted from UTM EPSG:25830 to WGS84 EPSG:4326.

Usage:
    python scripts/import_metro_madrid_accesses.py [--dry-run]
"""

import os
import sys
import argparse
import logging
from datetime import time
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from pyproj import Transformer
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CRTM Feature Service endpoint
CRTM_ACCESOS_URL = "https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M4_Red/FeatureServer/1/query"

# Coordinate transformer: UTM Zone 30N (EPSG:25830) -> WGS84 (EPSG:4326)
transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)


def fetch_accesos() -> List[Dict]:
    """Fetch all access point features from CRTM Feature Service."""
    features = []
    offset = 0
    batch_size = 1000

    while True:
        params = {
            'where': '1=1',
            'outFields': 'DENOMINACION,CODIGOESTACION,NOMBREVIA,NUMEROPORTAL,HORAAPERTURA,HORACIERRE,ACCESOMINUSVALIDOS,NIVEL,X,Y',
            'returnGeometry': 'true',
            'f': 'json',
            'outSR': '25830',  # Request in UTM for accurate conversion
            'resultOffset': offset,
            'resultRecordCount': batch_size,
        }

        try:
            response = requests.get(CRTM_ACCESOS_URL, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            batch_features = data.get('features', [])
            if not batch_features:
                break

            features.extend(batch_features)
            offset += batch_size
            logger.info(f"  Fetched {len(features)} accesos...")

            if len(batch_features) < batch_size:
                break

        except Exception as e:
            logger.error(f"Error fetching accesos: {e}")
            raise

    logger.info(f"Total accesos fetched: {len(features)}")
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


def parse_time(time_str: Optional[str]) -> Optional[time]:
    """Parse time string from CRTM format.

    CRTM times are in format "HH:MM" or "HHMM".

    Args:
        time_str: Time string from CRTM

    Returns:
        time object or None
    """
    if not time_str:
        return None

    time_str = str(time_str).strip()

    try:
        # Try HH:MM format
        if ':' in time_str:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        # Try HHMM format
        elif len(time_str) == 4:
            hour = int(time_str[:2])
            minute = int(time_str[2:])
        # Try HMM format (e.g., "600" for 6:00)
        elif len(time_str) == 3:
            hour = int(time_str[0])
            minute = int(time_str[1:])
        else:
            return None

        # Handle 24:00 and beyond (next day)
        if hour >= 24:
            hour = hour - 24

        return time(hour=hour, minute=minute)
    except (ValueError, IndexError):
        logger.debug(f"Could not parse time: {time_str}")
        return None


def parse_wheelchair(value: Optional[str]) -> Optional[bool]:
    """Parse wheelchair accessibility value from CRTM.

    Args:
        value: Accessibility string from CRTM

    Returns:
        True if accessible, False if not, None if unknown
    """
    if not value:
        return None

    value_lower = str(value).lower().strip()

    if value_lower in ('si', 'sí', 'yes', 's', '1', 'true'):
        return True
    elif value_lower in ('no', 'n', '0', 'false'):
        return False

    return None


def import_accesses(db, dry_run: bool = False) -> Dict[str, int]:
    """Import access point data from CRTM.

    Args:
        db: Database session
        dry_run: If True, don't make any changes

    Returns:
        Statistics dict
    """
    stats = {
        'accesses_imported': 0,
        'accesses_skipped': 0,
        'stations_without_mapping': 0,
    }

    # Get station code -> stop_id mapping
    station_mapping = fetch_station_mapping()

    logger.info("Fetching accesos from CRTM...")
    features = fetch_accesos()

    # Clear existing CRTM-sourced accesses for Metro
    if not dry_run:
        result = db.execute(text("""
            DELETE FROM stop_access
            WHERE stop_id LIKE 'METRO_%'
            AND source = 'crtm'
        """))
        logger.info(f"Cleared {result.rowcount} existing CRTM accesses")

    for feature in features:
        attrs = feature.get('attributes', {})
        geom = feature.get('geometry', {})

        name = attrs.get('DENOMINACION', '')
        codigo = attrs.get('CODIGOESTACION', '')
        street = attrs.get('NOMBREVIA', '')
        street_number = attrs.get('NUMEROPORTAL', '')
        opening_str = attrs.get('HORAAPERTURA', '')
        closing_str = attrs.get('HORACIERRE', '')
        wheelchair_str = attrs.get('ACCESOMINUSVALIDOS', '')
        nivel = attrs.get('NIVEL')

        # Get coordinates - can be in attrs (X, Y) or geometry
        x = attrs.get('X') or (geom.get('x') if geom else None)
        y = attrs.get('Y') or (geom.get('y') if geom else None)

        if not codigo or not x or not y:
            stats['accesses_skipped'] += 1
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

        # Convert coordinates
        lat, lon = convert_point(x, y)

        # Parse times
        opening_time = parse_time(opening_str)
        closing_time = parse_time(closing_str)

        # Parse wheelchair
        wheelchair = parse_wheelchair(wheelchair_str)

        # Use name or generate one
        access_name = name.strip() if name else f"Acceso {codigo}"

        if not dry_run:
            # Insert access
            db.execute(text("""
                INSERT INTO stop_access
                (stop_id, name, lat, lon, street, street_number, opening_time, closing_time, wheelchair, level, source)
                VALUES (:stop_id, :name, :lat, :lon, :street, :street_number, :opening_time, :closing_time, :wheelchair, :level, 'crtm')
            """), {
                'stop_id': stop_id,
                'name': access_name,
                'lat': lat,
                'lon': lon,
                'street': street if street else None,
                'street_number': str(street_number) if street_number else None,
                'opening_time': opening_time,
                'closing_time': closing_time,
                'wheelchair': wheelchair,
                'level': nivel,
            })

        stats['accesses_imported'] += 1

    if not dry_run:
        db.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(description='Import Metro Madrid accesses from CRTM')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without saving')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made")

        stats = import_accesses(db, dry_run=args.dry_run)

        logger.info("=" * 60)
        logger.info("IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Accesses imported: {stats['accesses_imported']}")
        logger.info(f"Accesses skipped: {stats['accesses_skipped']}")
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
