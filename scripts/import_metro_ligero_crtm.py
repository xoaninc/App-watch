#!/usr/bin/env python3
"""Import Metro Ligero data from CRTM Feature Service.

Imports:
- Accesos (entrances)
- Vestíbulos (vestibules)
- Andenes (platforms)
- Shapes (track geometry)

Source: Red_MetroLigero Feature Service
https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/Red_MetroLigero/FeatureServer

Usage:
    python scripts/import_metro_ligero_crtm.py [--dry-run]
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

# CRTM Feature Service base URL
BASE_URL = "https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/Red_MetroLigero/FeatureServer"

# Coordinate transformer: UTM Zone 30N (EPSG:25830) -> WGS84 (EPSG:4326)
transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)

# CRTM CODIGOESTACION to GTFS stop_id mapping
# Some CRTM codes don't match our GTFS IDs directly
CRTM_TO_GTFS_STOP_ID = {
    '10': 'ML_24',  # Colonia Jardín (CRTM uses 10, GTFS uses 24)
}


def get_stop_id(codigo: str) -> str:
    """Convert CRTM CODIGOESTACION to GTFS stop_id."""
    codigo_str = str(codigo).strip()
    if codigo_str in CRTM_TO_GTFS_STOP_ID:
        return CRTM_TO_GTFS_STOP_ID[codigo_str]
    return f"ML_{codigo_str}"


def fetch_layer(layer_id: int, fields: str = "*") -> List[Dict]:
    """Fetch all features from a CRTM layer."""
    features = []
    offset = 0
    batch_size = 1000

    url = f"{BASE_URL}/{layer_id}/query"

    while True:
        params = {
            'where': '1=1',
            'outFields': fields,
            'returnGeometry': 'true',
            'f': 'json',
            'outSR': '25830',
            'resultOffset': offset,
            'resultRecordCount': batch_size,
        }

        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            batch_features = data.get('features', [])
            if not batch_features:
                break

            features.extend(batch_features)
            offset += batch_size

            if len(batch_features) < batch_size:
                break

        except Exception as e:
            logger.error(f"Error fetching layer {layer_id}: {e}")
            raise

    return features


def convert_point(x: float, y: float) -> Tuple[float, float]:
    """Convert UTM point to WGS84. Returns (lat, lon)."""
    lon, lat = transformer.transform(x, y)
    return (lat, lon)


def parse_time_str(time_str: Optional[str]) -> Optional[time]:
    """Parse time string from CRTM format."""
    if not time_str:
        return None

    time_str = str(time_str).strip()

    try:
        if ':' in time_str:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        elif len(time_str) == 4:
            hour = int(time_str[:2])
            minute = int(time_str[2:])
        else:
            return None

        if hour >= 24:
            hour = hour - 24

        return time(hour=hour, minute=minute)
    except (ValueError, IndexError):
        return None


def parse_wheelchair(value: Optional[str]) -> Optional[bool]:
    """Parse wheelchair accessibility value."""
    if not value:
        return None

    value_lower = str(value).lower().strip()

    if value_lower in ('si', 'sí', 'yes', 's', '1', 'true', 'a'):
        return True
    elif value_lower in ('no', 'n', '0', 'false'):
        return False

    return None


def import_accesos(db, dry_run: bool = False) -> int:
    """Import access points (entrances)."""
    logger.info("Importing accesos...")

    features = fetch_layer(1, "CODIGOESTACION,DENOMINACION,NOMBREVIA,NUMEROPORTAL,HORAAPERTURA,HORACIERRE,ACCESOMINUSVALIDOS,NIVEL,X,Y")
    logger.info(f"  Fetched {len(features)} accesos")

    if not dry_run:
        # Clear existing
        result = db.execute(text("DELETE FROM stop_access WHERE stop_id LIKE 'ML_%' AND source = 'crtm'"))
        logger.info(f"  Cleared {result.rowcount} existing accesos")

    count = 0
    for feature in features:
        attrs = feature.get('attributes', {})
        geom = feature.get('geometry', {})

        codigo = attrs.get('CODIGOESTACION')
        if not codigo:
            continue

        stop_id = get_stop_id(codigo)
        name = attrs.get('DENOMINACION', f'Acceso {codigo}')
        street = attrs.get('NOMBREVIA')
        street_number = attrs.get('NUMEROPORTAL')
        opening_str = attrs.get('HORAAPERTURA')
        closing_str = attrs.get('HORACIERRE')
        wheelchair_str = attrs.get('ACCESOMINUSVALIDOS')
        nivel = attrs.get('NIVEL')

        x = attrs.get('X') or (geom.get('x') if geom else None)
        y = attrs.get('Y') or (geom.get('y') if geom else None)

        if not x or not y:
            continue

        lat, lon = convert_point(x, y)
        opening_time = parse_time_str(opening_str)
        closing_time = parse_time_str(closing_str)
        wheelchair = parse_wheelchair(wheelchair_str)

        if not dry_run:
            db.execute(text("""
                INSERT INTO stop_access
                (stop_id, name, lat, lon, street, street_number, opening_time, closing_time, wheelchair, level, source)
                VALUES (:stop_id, :name, :lat, :lon, :street, :street_number, :opening_time, :closing_time, :wheelchair, :level, 'crtm')
            """), {
                'stop_id': stop_id,
                'name': name,
                'lat': lat,
                'lon': lon,
                'street': street,
                'street_number': str(street_number) if street_number else None,
                'opening_time': opening_time,
                'closing_time': closing_time,
                'wheelchair': wheelchair,
                'level': nivel,
            })

        count += 1

    if not dry_run:
        db.commit()

    logger.info(f"  Imported {count} accesos")
    return count


def import_vestibulos(db, dry_run: bool = False) -> int:
    """Import vestibules."""
    logger.info("Importing vestíbulos...")

    features = fetch_layer(2, "CODIGOESTACION,DENOMINACION,NIVEL,TIPOVESTIBULO,TIPOTORNIQUETE,HORAAPERTURA,HORACIERRE,ACCESOMINUSVALIDOS,X,Y")
    logger.info(f"  Fetched {len(features)} vestíbulos")

    if not dry_run:
        result = db.execute(text("DELETE FROM stop_vestibule WHERE stop_id LIKE 'ML_%' AND source = 'crtm'"))
        logger.info(f"  Cleared {result.rowcount} existing vestíbulos")

    count = 0
    for feature in features:
        attrs = feature.get('attributes', {})
        geom = feature.get('geometry', {})

        codigo = attrs.get('CODIGOESTACION')
        if not codigo:
            continue

        stop_id = get_stop_id(codigo)
        name = attrs.get('DENOMINACION', f'Vestíbulo {codigo}')
        nivel = attrs.get('NIVEL')
        vestibule_type = attrs.get('TIPOVESTIBULO')
        turnstile_type = attrs.get('TIPOTORNIQUETE')
        opening_str = attrs.get('HORAAPERTURA')
        closing_str = attrs.get('HORACIERRE')
        wheelchair_str = attrs.get('ACCESOMINUSVALIDOS')

        x = attrs.get('X') or (geom.get('x') if geom else None)
        y = attrs.get('Y') or (geom.get('y') if geom else None)

        if not x or not y:
            continue

        lat, lon = convert_point(x, y)
        opening_time = parse_time_str(opening_str)
        closing_time = parse_time_str(closing_str)
        wheelchair = parse_wheelchair(wheelchair_str)

        if not dry_run:
            db.execute(text("""
                INSERT INTO stop_vestibule
                (stop_id, name, lat, lon, level, vestibule_type, turnstile_type, opening_time, closing_time, wheelchair, source)
                VALUES (:stop_id, :name, :lat, :lon, :level, :vestibule_type, :turnstile_type, :opening_time, :closing_time, :wheelchair, 'crtm')
            """), {
                'stop_id': stop_id,
                'name': name,
                'lat': lat,
                'lon': lon,
                'level': nivel,
                'vestibule_type': vestibule_type,
                'turnstile_type': turnstile_type,
                'opening_time': opening_time,
                'closing_time': closing_time,
                'wheelchair': wheelchair,
            })

        count += 1

    if not dry_run:
        db.commit()

    logger.info(f"  Imported {count} vestíbulos")
    return count


def import_andenes(db, dry_run: bool = False) -> int:
    """Import platforms (andenes)."""
    logger.info("Importing andenes...")

    features = fetch_layer(3, "CODIGOESTACION,DENOMINACION,NUMANDEN,NIVEL,ACCESOMINUSVALIDOS,X,Y")
    logger.info(f"  Fetched {len(features)} andenes")

    if not dry_run:
        result = db.execute(text("DELETE FROM stop_platform WHERE stop_id LIKE 'ML_%' AND source = 'crtm'"))
        logger.info(f"  Cleared {result.rowcount} existing andenes CRTM")

    count = 0
    for feature in features:
        attrs = feature.get('attributes', {})
        geom = feature.get('geometry', {})

        codigo = attrs.get('CODIGOESTACION')
        if not codigo:
            continue

        stop_id = get_stop_id(codigo)
        description = attrs.get('DENOMINACION', '')
        anden_num = attrs.get('NUMANDEN', '')
        nivel = attrs.get('NIVEL')

        x = attrs.get('X') or (geom.get('x') if geom else None)
        y = attrs.get('Y') or (geom.get('y') if geom else None)

        if not x or not y:
            continue

        lat, lon = convert_point(x, y)

        # Extract line from description (e.g., "Sentido LAS TABLAS" -> determine line)
        lines = f"Andén {anden_num}" if anden_num else "ML"

        if not dry_run:
            db.execute(text("""
                INSERT INTO stop_platform
                (stop_id, lines, lat, lon, description, source)
                VALUES (:stop_id, :lines, :lat, :lon, :description, 'crtm')
            """), {
                'stop_id': stop_id,
                'lines': lines,
                'lat': lat,
                'lon': lon,
                'description': f"{description} (Nivel {nivel})" if nivel else description,
            })

        count += 1

    if not dry_run:
        db.commit()

    logger.info(f"  Imported {count} andenes")
    return count


def import_shapes(db, dry_run: bool = False) -> int:
    """Import track shapes."""
    logger.info("Importing shapes (tramos)...")

    features = fetch_layer(4, "NUMEROLINEAUSUARIO,SENTIDO,NUMEROORDEN")
    logger.info(f"  Fetched {len(features)} tramos")

    # Group by line and direction
    shapes_data = {}

    for feature in features:
        attrs = feature.get('attributes', {})
        geom = feature.get('geometry', {})

        linea = str(attrs.get('NUMEROLINEAUSUARIO', '')).strip()
        sentido = attrs.get('SENTIDO', 1)
        orden = attrs.get('NUMEROORDEN', 0)

        if not linea or not geom:
            continue

        # Normalize line name
        line_map = {
            '1': 'ML1', '2': 'ML2', '3': 'ML3', '4': 'ML4',
            '51': 'ML1', '52': 'ML2', '53': 'ML3', '54': 'ML4',
        }
        line_name = line_map.get(linea, f'ML{linea}')

        shape_id = f"ML_{line_name}_{sentido}_CRTM"

        if shape_id not in shapes_data:
            shapes_data[shape_id] = []

        # Get path coordinates
        paths = geom.get('paths', [])
        for path in paths:
            for point in path:
                if len(point) >= 2:
                    x, y = point[0], point[1]
                    lat, lon = convert_point(x, y)
                    shapes_data[shape_id].append((orden, lat, lon))

    if not dry_run:
        # Clear existing CRTM shapes for ML
        result = db.execute(text("DELETE FROM gtfs_shape_points WHERE shape_id LIKE 'ML_%CRTM'"))
        logger.info(f"  Cleared {result.rowcount} existing shape points")
        result = db.execute(text("DELETE FROM gtfs_shapes WHERE id LIKE 'ML_%CRTM'"))
        logger.info(f"  Cleared {result.rowcount} existing shapes")

    total_points = 0
    for shape_id, points in shapes_data.items():
        # Sort by orden
        points.sort(key=lambda x: x[0])

        # Create shape entry first
        if not dry_run:
            db.execute(text("""
                INSERT INTO gtfs_shapes (id)
                VALUES (:shape_id)
                ON CONFLICT (id) DO NOTHING
            """), {'shape_id': shape_id})

        # Insert shape points
        for seq, (orden, lat, lon) in enumerate(points):
            if not dry_run:
                db.execute(text("""
                    INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon)
                    VALUES (:shape_id, :sequence, :lat, :lon)
                    ON CONFLICT (shape_id, sequence) DO UPDATE SET lat = EXCLUDED.lat, lon = EXCLUDED.lon
                """), {
                    'shape_id': shape_id,
                    'sequence': seq,
                    'lat': lat,
                    'lon': lon,
                })
            total_points += 1

        logger.info(f"    {shape_id}: {len(points)} points")

    if not dry_run:
        db.commit()

    logger.info(f"  Imported {len(shapes_data)} shapes, {total_points} total points")
    return total_points


def verify_shapes(db):
    """Verify shape order by checking first and last points."""
    logger.info("\nVerifying shape order...")

    result = db.execute(text("""
        WITH shape_bounds AS (
            SELECT
                shape_id,
                MIN(sequence) as min_seq,
                MAX(sequence) as max_seq
            FROM gtfs_shape_points
            WHERE shape_id LIKE 'ML_%CRTM'
            GROUP BY shape_id
        )
        SELECT
            sb.shape_id,
            sp1.lat as first_lat, sp1.lon as first_lon,
            sp2.lat as last_lat, sp2.lon as last_lon,
            sb.max_seq + 1 as total_points
        FROM shape_bounds sb
        JOIN gtfs_shape_points sp1 ON sb.shape_id = sp1.shape_id AND sp1.sequence = sb.min_seq
        JOIN gtfs_shape_points sp2 ON sb.shape_id = sp2.shape_id AND sp2.sequence = sb.max_seq
        ORDER BY sb.shape_id
    """)).fetchall()

    print("\n" + "=" * 80)
    print("SHAPES VERIFICACIÓN")
    print("=" * 80)
    print(f"{'Shape ID':<25} {'Puntos':<8} {'Inicio (lat, lon)':<25} {'Fin (lat, lon)':<25}")
    print("-" * 80)

    for row in result:
        shape_id = row[0]
        first_lat, first_lon = row[1], row[2]
        last_lat, last_lon = row[3], row[4]
        total = row[5]
        print(f"{shape_id:<25} {total:<8} ({first_lat:.4f}, {first_lon:.4f})  ({last_lat:.4f}, {last_lon:.4f})")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Import Metro Ligero data from CRTM')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without saving')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made\n")

        # Import all data
        accesos = import_accesos(db, args.dry_run)
        vestibulos = import_vestibulos(db, args.dry_run)
        andenes = import_andenes(db, args.dry_run)
        shapes = import_shapes(db, args.dry_run)

        # Verify shapes
        if not args.dry_run:
            verify_shapes(db)

        logger.info("\n" + "=" * 60)
        logger.info("IMPORT COMPLETE - Metro Ligero")
        logger.info("=" * 60)
        logger.info(f"Accesos: {accesos}")
        logger.info(f"Vestíbulos: {vestibulos}")
        logger.info(f"Andenes: {andenes}")
        logger.info(f"Shape points: {shapes}")
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
