#!/usr/bin/env python3
"""Import missing Renfe GTFS data (stops and shapes).

This script imports:
- 236 missing stops
- 68 shapes (58,487 points)

Usage:
    python scripts/import_renfe_missing.py [--dry-run]
    python scripts/import_renfe_missing.py --gtfs-dir /tmp/renfe_gtfs
"""

import os
import sys
import csv
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_GTFS_DIR = '/tmp/renfe_gtfs'
PREFIX = 'RENFE_'


def clean_row(row: dict) -> dict:
    """Strip whitespace from keys and values."""
    return {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}


def get_existing_stops(db) -> set:
    """Get existing stop IDs (without prefix)."""
    result = db.execute(text("SELECT REPLACE(id, 'RENFE_', '') FROM gtfs_stops WHERE id LIKE 'RENFE_%'"))
    return {row[0] for row in result}


def import_missing_stops(db, gtfs_dir: str, dry_run: bool) -> int:
    """Import stops that exist in GTFS but not in BD."""
    logger.info("Paso 1: Importando stops faltantes...")

    existing = get_existing_stops(db)
    logger.info(f"  Stops existentes en BD: {len(existing)}")

    stops_file = os.path.join(gtfs_dir, 'stops.txt')

    count = 0
    imported = 0

    with open(stops_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = clean_row(row)
            count += 1
            stop_id = row['stop_id']

            if stop_id in existing:
                continue

            our_stop_id = f"{PREFIX}{stop_id}"

            if dry_run:
                if imported < 10:
                    logger.info(f"  [DRY-RUN] Nueva stop: {our_stop_id} - {row['stop_name']}")
            else:
                db.execute(text('''
                    INSERT INTO gtfs_stops (id, name, lat, lon, wheelchair_boarding)
                    VALUES (:id, :name, :lat, :lon, :wheelchair)
                    ON CONFLICT (id) DO NOTHING
                '''), {
                    'id': our_stop_id,
                    'name': row['stop_name'],
                    'lat': float(row['stop_lat']),
                    'lon': float(row['stop_lon']),
                    'wheelchair': int(row.get('wheelchair_boarding', 0)) if row.get('wheelchair_boarding') else 0,
                })

            imported += 1

    logger.info(f"  Total stops en GTFS: {count}")
    logger.info(f"  Stops importadas: {imported}")
    return imported


def import_shapes(db, gtfs_dir: str, dry_run: bool) -> tuple:
    """Import all shapes from GTFS.

    NOTE: Shapes are stored WITHOUT prefix because trips reference them
    without prefix (e.g., trip.shape_id = '10_C1').
    """
    logger.info("Paso 2: Importando shapes...")

    shapes_file = os.path.join(gtfs_dir, 'shapes.txt')

    # Get existing shapes (numeric prefix like 10_C1, 51_R3, etc.)
    existing_shapes = set()
    result = db.execute(text("SELECT DISTINCT shape_id FROM gtfs_shape_points WHERE shape_id ~ '^[0-9]+_'"))
    for row in result:
        existing_shapes.add(row[0])
    logger.info(f"  Shapes existentes: {len(existing_shapes)}")

    # Group points by shape
    shapes = {}
    with open(shapes_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = clean_row(row)
            gtfs_shape = row['shape_id']
            # NO prefix for shapes - trips reference them without prefix
            our_shape = gtfs_shape

            if our_shape not in shapes:
                shapes[our_shape] = []

            shapes[our_shape].append({
                'lat': float(row['shape_pt_lat']),
                'lon': float(row['shape_pt_lon']),
                'sequence': int(row['shape_pt_sequence']),
            })

    # Filter out existing shapes
    new_shapes = {k: v for k, v in shapes.items() if k not in existing_shapes}
    logger.info(f"  Shapes en GTFS: {len(shapes)}")
    logger.info(f"  Shapes nuevos: {len(new_shapes)}")

    if not new_shapes:
        logger.info("  No hay shapes nuevos para importar")
        return 0, 0

    if dry_run:
        total_points = sum(len(pts) for pts in new_shapes.values())
        for shape_id in list(new_shapes.keys())[:5]:
            logger.info(f"  [DRY-RUN] Shape {shape_id}: {len(new_shapes[shape_id])} puntos")
        return len(new_shapes), total_points

    # Insert new shapes only
    total_points = 0
    for shape_id, points in new_shapes.items():
        # Create shape record
        db.execute(text('''
            INSERT INTO gtfs_shapes (id) VALUES (:id)
            ON CONFLICT (id) DO NOTHING
        '''), {'id': shape_id})

        # Insert points in batch
        for pt in sorted(points, key=lambda x: x['sequence']):
            db.execute(text('''
                INSERT INTO gtfs_shape_points (shape_id, lat, lon, sequence)
                VALUES (:shape_id, :lat, :lon, :seq)
            '''), {
                'shape_id': shape_id,
                'lat': pt['lat'],
                'lon': pt['lon'],
                'seq': pt['sequence'],
            })
            total_points += 1

        if total_points % 10000 == 0:
            logger.info(f"  Procesados {total_points} puntos...")

    logger.info(f"  Total shapes nuevos: {len(new_shapes)}")
    logger.info(f"  Total puntos: {total_points}")
    return len(new_shapes), total_points


def verify_import(db) -> dict:
    """Verify the import was successful."""
    logger.info("Paso 3: Verificando importación...")

    stats = {}

    # Stops
    result = db.execute(text("SELECT COUNT(*) FROM gtfs_stops WHERE id LIKE 'RENFE_%'")).scalar()
    stats['stops'] = result
    logger.info(f"  Stops RENFE: {result}")

    # Shapes (Renfe shapes use numeric prefix like 10_C1, 51_R3)
    result = db.execute(text("SELECT COUNT(DISTINCT shape_id) FROM gtfs_shape_points WHERE shape_id ~ '^[0-9]+_'")).scalar()
    stats['shapes'] = result
    logger.info(f"  Shapes Renfe: {result}")

    # Shape points
    result = db.execute(text("SELECT COUNT(*) FROM gtfs_shape_points WHERE shape_id ~ '^[0-9]+_'")).scalar()
    stats['shape_points'] = result
    logger.info(f"  Shape points Renfe: {result}")

    return stats


def main():
    parser = argparse.ArgumentParser(description='Import missing Renfe GTFS data')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--gtfs-dir', default=DEFAULT_GTFS_DIR, help='Path to GTFS directory')
    parser.add_argument('--stops-only', action='store_true', help='Only import stops')
    parser.add_argument('--shapes-only', action='store_true', help='Only import shapes')
    args = parser.parse_args()

    gtfs_dir = args.gtfs_dir

    if not os.path.exists(gtfs_dir):
        logger.error(f"GTFS directory not found: {gtfs_dir}")
        logger.error("Download first:")
        logger.error("  curl -sL 'https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip' -o /tmp/renfe.zip")
        logger.error("  unzip /tmp/renfe.zip -d /tmp/renfe_gtfs")
        sys.exit(1)

    if args.dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN - No se harán cambios en la base de datos")
        logger.info("=" * 60)

    logger.info(f"GTFS directory: {gtfs_dir}")

    db = SessionLocal()

    try:
        stops_imported = 0
        shapes_count = 0
        points_count = 0

        if not args.shapes_only:
            stops_imported = import_missing_stops(db, gtfs_dir, args.dry_run)

        if not args.stops_only:
            shapes_count, points_count = import_shapes(db, gtfs_dir, args.dry_run)

        if not args.dry_run:
            db.commit()
            logger.info("=" * 60)
            logger.info("COMMIT realizado")
            logger.info("=" * 60)

            verify_import(db)

        logger.info("=" * 60)
        logger.info("IMPORTACIÓN COMPLETADA")
        logger.info("=" * 60)
        logger.info(f"  Stops nuevas: {stops_imported}")
        logger.info(f"  Shapes: {shapes_count}")
        logger.info(f"  Shape points: {points_count}")

        if args.dry_run:
            logger.info("")
            logger.info("[DRY RUN - No se guardaron cambios]")

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
