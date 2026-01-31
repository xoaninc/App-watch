#!/usr/bin/env python3
"""Import Metrovalencia GTFS data.

This script imports the complete GTFS data for Metrovalencia:
- 75 new routes (114 already exist)
- 4 calendar services (L-J, V, S, D/Festivo)
- 14 festivos Valencia 2026
- 10,348 trips
- 181,995 stop_times
- 20 shapes

Source: NAP (Punto de Acceso Nacional)
- conjuntoDatoId: 967
- ficheroId: 1168

Usage:
    python scripts/import_metrovalencia_gtfs.py [--dry-run]
    python scripts/import_metrovalencia_gtfs.py --gtfs-dir /tmp/metrovalencia_gtfs
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

# Path to GTFS files (downloaded from NAP)
DEFAULT_GTFS_DIR = '/tmp/metrovalencia_gtfs'

# ID prefix for Metrovalencia
PREFIX = 'METRO_VALENCIA_'

# Service ID mapping from GTFS to our DB
# GTFS uses: 3091 (L-J), 3093 (V), 3076 (S), 3078 (D)
SERVICE_MAPPING = {
    '3091': f'{PREFIX}3091',  # Laborable L-J
    '3093': f'{PREFIX}3093',  # Viernes
    '3076': f'{PREFIX}3076',  # Sábado
    '3078': f'{PREFIX}3078',  # Domingo/Festivo
    # Especiales - mapear a los principales
    '3128': f'{PREFIX}3078',  # Especial 31 ene -> Domingo
    '3129': f'{PREFIX}3078',  # Especial 1 feb -> Domingo
    '3126': f'{PREFIX}3078',  # Especial 2 feb -> Domingo
}

# Services to import (only the 4 main ones)
SERVICES_TO_IMPORT = ['3091', '3093', '3076', '3078']

# Festivos Valencia 2026 - usar servicio domingo (3078)
FESTIVOS_VALENCIA_2026 = [
    # Nacionales
    '2026-01-01',  # Año Nuevo (Jueves)
    '2026-01-06',  # Reyes (Martes)
    '2026-04-03',  # Viernes Santo
    '2026-05-01',  # Día del Trabajo (Viernes)
    '2026-08-15',  # Asunción (Sábado)
    '2026-10-12',  # Fiesta Nacional (Lunes)
    '2026-12-08',  # Inmaculada (Martes)
    '2026-12-25',  # Navidad (Viernes)
    # Autonómicos Comunitat Valenciana
    '2026-04-06',  # Lunes de Pascua
    '2026-10-09',  # Día de la Comunitat (Viernes)
    # Locales Valencia ciudad
    '2026-01-22',  # San Vicente Mártir (Jueves)
    '2026-03-19',  # San José / Fallas (Jueves)
    '2026-04-13',  # San Vicente Ferrer (Lunes)
    '2026-06-24',  # San Juan (Miércoles)
]


def import_routes(db, gtfs_dir: str, dry_run: bool) -> int:
    """Import new routes from GTFS."""
    logger.info("Paso 1: Importando rutas nuevas...")

    routes_file = os.path.join(gtfs_dir, 'routes.txt')

    # Get existing routes
    existing = set()
    result = db.execute(text("SELECT id FROM gtfs_routes WHERE id LIKE 'METRO_VALENCIA_%'"))
    for row in result:
        existing.add(row[0])
    logger.info(f"  Rutas existentes en BD: {len(existing)}")

    count = 0
    new_count = 0
    with open(routes_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            our_route_id = f"{PREFIX}{row['route_id']}"
            count += 1

            if our_route_id in existing:
                continue

            new_count += 1
            if dry_run:
                if new_count <= 5:
                    logger.info(f"  [DRY-RUN] Nueva ruta: {our_route_id}")
            else:
                db.execute(text('''
                    INSERT INTO gtfs_routes (id, agency_id, short_name, long_name, route_type, color, text_color, network_id)
                    VALUES (:id, :agency_id, :short_name, :long_name, :route_type, :color, :text_color, :network_id)
                    ON CONFLICT (id) DO NOTHING
                '''), {
                    'id': our_route_id,
                    'agency_id': 'METRO_VALENCIA_1',
                    'short_name': row.get('route_short_name', ''),
                    'long_name': row.get('route_long_name', ''),
                    'route_type': int(row.get('route_type', 1)),
                    'color': row.get('route_color', 'FF6600'),
                    'text_color': row.get('route_text_color', 'FFFFFF'),
                    'network_id': '40T',
                })

    logger.info(f"  Total rutas en GTFS: {count}")
    logger.info(f"  Rutas nuevas a importar: {new_count}")
    return new_count


def create_calendars(db, dry_run: bool) -> int:
    """Create the 4 calendar services."""
    logger.info("Paso 2: Creando calendarios...")

    # L-J, V, S, D
    calendars = [
        (f'{PREFIX}3091', True, True, True, True, False, False, False),   # L-J
        (f'{PREFIX}3093', False, False, False, False, True, False, False), # V
        (f'{PREFIX}3076', False, False, False, False, False, True, False), # S
        (f'{PREFIX}3078', False, False, False, False, False, False, True), # D/Festivo
    ]

    if dry_run:
        for cal in calendars:
            logger.info(f"  [DRY-RUN] Crearía calendario: {cal[0]}")
        return len(calendars)

    # Delete existing calendars
    db.execute(text("DELETE FROM gtfs_calendar WHERE service_id LIKE 'METRO_VALENCIA_%'"))

    for cal_id, mon, tue, wed, thu, fri, sat, sun in calendars:
        db.execute(text('''
            INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
            VALUES (:service_id, :mon, :tue, :wed, :thu, :fri, :sat, :sun, '2026-01-01', '2026-12-31')
        '''), {
            'service_id': cal_id, 'mon': mon, 'tue': tue, 'wed': wed,
            'thu': thu, 'fri': fri, 'sat': sat, 'sun': sun
        })
        logger.info(f"  Creado calendario: {cal_id}")

    return len(calendars)


def create_calendar_dates(db, dry_run: bool) -> int:
    """Create calendar_dates for festivos."""
    logger.info("Paso 3: Creando calendar_dates (festivos Valencia 2026)...")

    if not dry_run:
        # Delete existing
        db.execute(text("DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_VALENCIA_%'"))

    count = 0
    domingo_service = f'{PREFIX}3078'

    for fecha in FESTIVOS_VALENCIA_2026:
        if dry_run:
            logger.info(f"  [DRY-RUN] Festivo {fecha}: +{domingo_service}")
        else:
            # Añadir servicio domingo/festivo
            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :fecha, 1)
            '''), {'service_id': domingo_service, 'fecha': fecha})
        count += 1

    logger.info(f"  Total festivos: {count}")
    return count


def import_shapes(db, gtfs_dir: str, dry_run: bool) -> int:
    """Import shapes from GTFS."""
    logger.info("Paso 4: Importando shapes...")

    shapes_file = os.path.join(gtfs_dir, 'shapes.txt')

    if not dry_run:
        # Delete existing shapes
        db.execute(text("DELETE FROM gtfs_shape_points WHERE shape_id LIKE 'METRO_VALENCIA_%'"))
        db.execute(text("DELETE FROM gtfs_shapes WHERE id LIKE 'METRO_VALENCIA_%'"))

    # Group points by shape
    shapes = {}
    with open(shapes_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            gtfs_shape = row['shape_id']
            our_shape = f"{PREFIX}{gtfs_shape}"

            if our_shape not in shapes:
                shapes[our_shape] = []

            shapes[our_shape].append({
                'lat': float(row['shape_pt_lat']),
                'lon': float(row['shape_pt_lon']),
                'sequence': int(row['shape_pt_sequence']),
            })

    count = 0
    for shape_id, points in shapes.items():
        if dry_run:
            logger.info(f"  [DRY-RUN] Shape {shape_id}: {len(points)} puntos")
        else:
            # Create shape record
            db.execute(text('''
                INSERT INTO gtfs_shapes (id) VALUES (:id)
                ON CONFLICT (id) DO NOTHING
            '''), {'id': shape_id})

            # Insert points
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
                count += 1

    logger.info(f"  Total shapes: {len(shapes)}")
    logger.info(f"  Total shape points: {count}")
    return count


def import_trips(db, gtfs_dir: str, dry_run: bool) -> int:
    """Import trips from GTFS."""
    logger.info("Paso 5: Importando trips...")

    trips_file = os.path.join(gtfs_dir, 'trips.txt')

    if not dry_run:
        # Delete existing trips
        db.execute(text("DELETE FROM gtfs_trips WHERE route_id LIKE 'METRO_VALENCIA_%'"))

    count = 0
    skipped = 0
    with open(trips_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            gtfs_service = row['service_id']
            our_service = SERVICE_MAPPING.get(gtfs_service)

            if not our_service:
                skipped += 1
                continue

            our_route = f"{PREFIX}{row['route_id']}"
            our_trip_id = f"{PREFIX}{row['trip_id']}"
            our_shape = f"{PREFIX}{row.get('shape_id', '')}" if row.get('shape_id') else None

            if not dry_run:
                db.execute(text('''
                    INSERT INTO gtfs_trips (id, route_id, service_id, headsign, direction_id, shape_id)
                    VALUES (:id, :route_id, :service_id, :headsign, :direction_id, :shape_id)
                    ON CONFLICT (id) DO UPDATE SET
                        service_id = EXCLUDED.service_id,
                        headsign = EXCLUDED.headsign,
                        direction_id = EXCLUDED.direction_id,
                        shape_id = EXCLUDED.shape_id
                '''), {
                    'id': our_trip_id,
                    'route_id': our_route,
                    'service_id': our_service,
                    'headsign': row.get('trip_headsign', ''),
                    'direction_id': int(row.get('direction_id', 0)) if row.get('direction_id') else 0,
                    'shape_id': our_shape,
                })

            count += 1
            if count % 2000 == 0:
                logger.info(f"  Procesados {count} trips...")

    logger.info(f"  Total trips importados: {count}")
    if skipped:
        logger.info(f"  Trips omitidos (servicio desconocido): {skipped}")
    return count


def import_stop_times(db, gtfs_dir: str, dry_run: bool) -> int:
    """Import stop_times from GTFS."""
    logger.info("Paso 6: Importando stop_times...")

    stop_times_file = os.path.join(gtfs_dir, 'stop_times.txt')

    if not dry_run:
        # Delete existing stop_times
        db.execute(text("DELETE FROM gtfs_stop_times WHERE trip_id LIKE 'METRO_VALENCIA_%'"))

    def time_to_seconds(t):
        parts = t.split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    count = 0
    batch = []
    batch_size = 10000

    with open(stop_times_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            our_trip_id = f"{PREFIX}{row['trip_id']}"
            our_stop_id = f"{PREFIX}{row['stop_id']}"

            arrival = row['arrival_time']
            departure = row['departure_time']

            batch.append({
                'trip_id': our_trip_id,
                'stop_id': our_stop_id,
                'arrival_time': arrival,
                'departure_time': departure,
                'arrival_seconds': time_to_seconds(arrival),
                'departure_seconds': time_to_seconds(departure),
                'stop_sequence': int(row['stop_sequence']),
            })

            count += 1

            if len(batch) >= batch_size:
                if not dry_run:
                    for item in batch:
                        db.execute(text('''
                            INSERT INTO gtfs_stop_times
                            (trip_id, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds, stop_sequence)
                            VALUES (:trip_id, :stop_id, :arrival_time, :departure_time, :arrival_seconds, :departure_seconds, :stop_sequence)
                        '''), item)
                batch = []
                logger.info(f"  Procesados {count} stop_times...")

    # Insert remaining batch
    if batch and not dry_run:
        for item in batch:
            db.execute(text('''
                INSERT INTO gtfs_stop_times
                (trip_id, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds, stop_sequence)
                VALUES (:trip_id, :stop_id, :arrival_time, :departure_time, :arrival_seconds, :departure_seconds, :stop_sequence)
            '''), item)

    logger.info(f"  Total stop_times: {count}")
    return count


def verify_import(db) -> dict:
    """Verify the import was successful."""
    logger.info("Paso 7: Verificando importación...")

    stats = {}

    # Routes
    result = db.execute(text("SELECT COUNT(*) FROM gtfs_routes WHERE id LIKE 'METRO_VALENCIA_%'")).scalar()
    stats['routes'] = result
    logger.info(f"  Rutas: {result}")

    # Calendars
    result = db.execute(text("SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'METRO_VALENCIA_%'")).scalar()
    stats['calendars'] = result
    logger.info(f"  Calendarios: {result}")

    # Calendar dates
    result = db.execute(text("SELECT COUNT(*) FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_VALENCIA_%'")).scalar()
    stats['calendar_dates'] = result
    logger.info(f"  Calendar_dates (festivos): {result}")

    # Trips by service
    result = db.execute(text('''
        SELECT service_id, COUNT(*)
        FROM gtfs_trips
        WHERE route_id LIKE 'METRO_VALENCIA_%'
        GROUP BY service_id
        ORDER BY service_id
    ''')).fetchall()
    stats['trips_by_service'] = {r[0]: r[1] for r in result}
    total_trips = sum(stats['trips_by_service'].values())
    stats['trips'] = total_trips
    logger.info(f"  Trips: {total_trips}")
    for service, cnt in stats['trips_by_service'].items():
        logger.info(f"    {service}: {cnt}")

    # Stop times
    result = db.execute(text("SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'METRO_VALENCIA_%'")).scalar()
    stats['stop_times'] = result
    logger.info(f"  Stop_times: {result}")

    # Shapes
    result = db.execute(text("SELECT COUNT(DISTINCT shape_id) FROM gtfs_shape_points WHERE shape_id LIKE 'METRO_VALENCIA_%'")).scalar()
    stats['shapes'] = result
    logger.info(f"  Shapes: {result}")

    return stats


def main():
    parser = argparse.ArgumentParser(description='Import Metrovalencia GTFS data')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--gtfs-dir', default=DEFAULT_GTFS_DIR, help='Path to GTFS directory')
    args = parser.parse_args()

    gtfs_dir = args.gtfs_dir

    # Verify GTFS directory exists
    if not os.path.exists(gtfs_dir):
        logger.error(f"GTFS directory not found: {gtfs_dir}")
        logger.error("Download from NAP first:")
        logger.error("  curl -s 'https://nap.transportes.gob.es/api/Fichero/download/1168' \\")
        logger.error("      -H 'ApiKey: $NAP_API_KEY' -o /tmp/metrovalencia.zip")
        logger.error("  unzip /tmp/metrovalencia.zip -d /tmp/metrovalencia_gtfs")
        sys.exit(1)

    if args.dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN - No se harán cambios en la base de datos")
        logger.info("=" * 60)

    logger.info(f"GTFS directory: {gtfs_dir}")

    db = SessionLocal()

    try:
        # Execute all steps
        routes = import_routes(db, gtfs_dir, args.dry_run)
        calendars = create_calendars(db, args.dry_run)
        calendar_dates = create_calendar_dates(db, args.dry_run)
        shapes = import_shapes(db, gtfs_dir, args.dry_run)
        trips = import_trips(db, gtfs_dir, args.dry_run)
        stop_times = import_stop_times(db, gtfs_dir, args.dry_run)

        if not args.dry_run:
            db.commit()
            logger.info("=" * 60)
            logger.info("COMMIT realizado")
            logger.info("=" * 60)

            # Verify
            stats = verify_import(db)

        logger.info("=" * 60)
        logger.info("IMPORTACIÓN COMPLETADA")
        logger.info("=" * 60)
        logger.info(f"  Rutas nuevas: {routes}")
        logger.info(f"  Calendarios: {calendars}")
        logger.info(f"  Festivos: {calendar_dates}")
        logger.info(f"  Shapes: {shapes} puntos")
        logger.info(f"  Trips: {trips}")
        logger.info(f"  Stop_times: {stop_times}")

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
