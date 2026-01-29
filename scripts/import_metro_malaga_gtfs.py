#!/usr/bin/env python3
"""Import Metro Málaga GTFS data.

This script imports the complete GTFS data for Metro Málaga:
- 5 calendar services (LABORABLE, VIERNES, SABADO, DOMINGO, FESTIVO)
- 44 calendar_dates (13 festivos + 9 vísperas × 2 operations each)
- 4,682 trips
- 48,945 stop_times
- 4 shapes (L1 and L2, both directions)

Usage:
    python scripts/import_metro_malaga_gtfs.py [--dry-run]
"""

import os
import sys
import csv
import argparse
import logging
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Path to GTFS files
GTFS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'gtfs_metro_malaga')

# ID prefix for Metro Málaga
PREFIX = 'METRO_MALAGA_'

# Service ID mapping from GTFS to our DB
SERVICE_MAPPING = {
    'M01': 'METRO_MALAGA_LABORABLE',
    'M02': 'METRO_MALAGA_VIERNES',
    'M03': 'METRO_MALAGA_SABADO',
    'M04': 'METRO_MALAGA_DOMINGO',
    'M84': 'METRO_MALAGA_FESTIVO',
}

# Shape ID mapping
SHAPE_MAPPING = {
    'L1V1': 'METRO_MALAGA_L1_DIR1',
    'L1V2': 'METRO_MALAGA_L1_DIR2',
    'L2V1': 'METRO_MALAGA_L2_DIR1',
    'L2V2': 'METRO_MALAGA_L2_DIR2',
}

# Festivos de Málaga 2026
FESTIVOS = [
    ('2026-01-01', 'METRO_MALAGA_LABORABLE'),   # Año Nuevo (Miércoles)
    ('2026-01-06', 'METRO_MALAGA_LABORABLE'),   # Reyes (Lunes)
    ('2026-02-28', 'METRO_MALAGA_SABADO'),      # Día Andalucía (Sábado)
    ('2026-04-02', 'METRO_MALAGA_LABORABLE'),   # Jueves Santo (Jueves)
    ('2026-04-03', 'METRO_MALAGA_VIERNES'),     # Viernes Santo (Viernes)
    ('2026-05-01', 'METRO_MALAGA_VIERNES'),     # 1 Mayo (Viernes)
    ('2026-08-15', 'METRO_MALAGA_SABADO'),      # Asunción (Sábado)
    ('2026-09-08', 'METRO_MALAGA_LABORABLE'),   # Virgen Victoria (Martes)
    ('2026-10-12', 'METRO_MALAGA_LABORABLE'),   # Fiesta Nacional (Lunes)
    ('2026-11-01', 'METRO_MALAGA_DOMINGO'),     # Todos Santos (Domingo)
    ('2026-12-06', 'METRO_MALAGA_DOMINGO'),     # Constitución (Domingo)
    ('2026-12-08', 'METRO_MALAGA_LABORABLE'),   # Inmaculada (Martes)
    ('2026-12-25', 'METRO_MALAGA_VIERNES'),     # Navidad (Viernes)
]

# Vísperas de festivo (días que NO son viernes ni sábado)
VISPERAS = [
    ('2025-12-31', 'METRO_MALAGA_LABORABLE'),   # Víspera Año Nuevo (Miércoles)
    ('2026-01-05', 'METRO_MALAGA_LABORABLE'),   # Víspera Reyes (Lunes)
    ('2026-04-01', 'METRO_MALAGA_LABORABLE'),   # Víspera Jueves Santo (Miércoles)
    ('2026-04-02', 'METRO_MALAGA_LABORABLE'),   # Víspera Viernes Santo (Jueves) - OJO: también es festivo
    ('2026-04-30', 'METRO_MALAGA_LABORABLE'),   # Víspera 1 Mayo (Jueves)
    ('2026-09-07', 'METRO_MALAGA_LABORABLE'),   # Víspera Virgen Victoria (Lunes)
    ('2026-10-11', 'METRO_MALAGA_DOMINGO'),     # Víspera Fiesta Nacional (Domingo)
    ('2026-12-07', 'METRO_MALAGA_LABORABLE'),   # Víspera Inmaculada (Lunes)
    ('2026-12-24', 'METRO_MALAGA_LABORABLE'),   # Víspera Navidad (Jueves)
]


def create_calendars(db, dry_run: bool) -> int:
    """Create the 5 calendar services."""
    logger.info("Paso 1: Creando calendarios...")

    calendars = [
        ('METRO_MALAGA_LABORABLE', True, True, True, True, False, False, False),
        ('METRO_MALAGA_VIERNES', False, False, False, False, True, False, False),
        ('METRO_MALAGA_SABADO', False, False, False, False, False, True, False),
        ('METRO_MALAGA_DOMINGO', False, False, False, False, False, False, True),
        ('METRO_MALAGA_FESTIVO', False, False, False, False, False, False, False),
    ]

    if dry_run:
        for cal in calendars:
            logger.info(f"  [DRY-RUN] Crearía calendario: {cal[0]}")
        return len(calendars)

    # Delete existing calendars first
    db.execute(text("DELETE FROM gtfs_calendar WHERE service_id LIKE 'METRO_MALAGA_%'"))

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
    """Create calendar_dates for festivos and vísperas."""
    logger.info("Paso 2: Creando calendar_dates (festivos y vísperas)...")

    count = 0

    if not dry_run:
        # Delete existing
        db.execute(text("DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_MALAGA_%'"))

    # Festivos: añadir FESTIVO, quitar servicio normal
    for fecha, servicio_normal in FESTIVOS:
        if dry_run:
            logger.info(f"  [DRY-RUN] Festivo {fecha}: +FESTIVO, -{servicio_normal}")
        else:
            # Añadir servicio festivo
            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES ('METRO_MALAGA_FESTIVO', :fecha, 1)
            '''), {'fecha': fecha})
            # Quitar servicio normal
            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:servicio, :fecha, 2)
            '''), {'servicio': servicio_normal, 'fecha': fecha})
        count += 2

    # Vísperas: añadir VIERNES (nocturno), quitar servicio normal
    for fecha, servicio_normal in VISPERAS:
        # Skip si es el 2 de abril (ya es festivo, se maneja arriba)
        if fecha == '2026-04-02':
            continue

        if dry_run:
            logger.info(f"  [DRY-RUN] Víspera {fecha}: +VIERNES, -{servicio_normal}")
        else:
            # Añadir servicio viernes (nocturno)
            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES ('METRO_MALAGA_VIERNES', :fecha, 1)
            '''), {'fecha': fecha})
            # Quitar servicio normal
            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:servicio, :fecha, 2)
            '''), {'servicio': servicio_normal, 'fecha': fecha})
        count += 2

    logger.info(f"  Total calendar_dates: {count}")
    return count


def import_trips(db, dry_run: bool) -> int:
    """Import trips from GTFS."""
    logger.info("Paso 3: Importando trips...")

    trips_file = os.path.join(GTFS_DIR, 'trips.txt')

    if not dry_run:
        # Delete existing trips
        db.execute(text("DELETE FROM gtfs_trips WHERE route_id LIKE 'METRO_MALAGA_%'"))

    count = 0
    with open(trips_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Map IDs
            gtfs_service = row['service_id']
            service_prefix = gtfs_service.split('_')[0]  # M01, M02, etc.

            our_service = SERVICE_MAPPING.get(service_prefix)
            if not our_service:
                logger.warning(f"  Service desconocido: {gtfs_service}")
                continue

            our_route = f"METRO_MALAGA_{row['route_id']}"
            our_trip_id = f"METRO_MALAGA_{row['trip_id']}"

            # Map shape
            gtfs_shape = row.get('shape_id', '')
            our_shape = SHAPE_MAPPING.get(gtfs_shape)

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
                    'direction_id': int(row.get('direction_id', 0)),
                    'shape_id': our_shape,
                })

            count += 1
            if count % 1000 == 0:
                logger.info(f"  Procesados {count} trips...")

    logger.info(f"  Total trips: {count}")
    return count


def import_stop_times(db, dry_run: bool) -> int:
    """Import stop_times from GTFS."""
    logger.info("Paso 4: Importando stop_times...")

    stop_times_file = os.path.join(GTFS_DIR, 'stop_times.txt')

    if not dry_run:
        # Delete existing stop_times for Metro Málaga trips
        db.execute(text('''
            DELETE FROM gtfs_stop_times
            WHERE trip_id LIKE 'METRO_MALAGA_%'
        '''))

    count = 0
    batch = []
    batch_size = 5000

    with open(stop_times_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            our_trip_id = f"METRO_MALAGA_{row['trip_id']}"
            our_stop_id = f"METRO_MALAGA_{row['stop_id']}"

            # Parse times (format: HH:MM:SS)
            arrival = row['arrival_time']
            departure = row['departure_time']

            # Convert to seconds
            def time_to_seconds(t):
                parts = t.split(':')
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

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


def import_shapes(db, dry_run: bool) -> int:
    """Import shapes from GTFS."""
    logger.info("Paso 5: Importando shapes...")

    shapes_file = os.path.join(GTFS_DIR, 'shapes.txt')

    if not dry_run:
        # Delete existing shapes
        db.execute(text("DELETE FROM gtfs_shape_points WHERE shape_id LIKE 'METRO_MALAGA_%'"))
        db.execute(text("DELETE FROM gtfs_shapes WHERE id LIKE 'METRO_MALAGA_%'"))

    # Group points by shape
    shapes = {}
    with open(shapes_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            gtfs_shape = row['shape_id']
            our_shape = SHAPE_MAPPING.get(gtfs_shape)

            if not our_shape:
                continue

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

        logger.info(f"  Shape {shape_id}: {len(points)} puntos")

    logger.info(f"  Total shape points: {count}")
    return count


def verify_import(db) -> dict:
    """Verify the import was successful."""
    logger.info("Paso 6: Verificando importación...")

    stats = {}

    # Calendars
    result = db.execute(text("SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'METRO_MALAGA_%'")).scalar()
    stats['calendars'] = result
    logger.info(f"  Calendarios: {result}")

    # Calendar dates
    result = db.execute(text("SELECT COUNT(*) FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_MALAGA_%'")).scalar()
    stats['calendar_dates'] = result
    logger.info(f"  Calendar_dates: {result}")

    # Trips by service
    result = db.execute(text('''
        SELECT service_id, COUNT(*)
        FROM gtfs_trips
        WHERE route_id LIKE 'METRO_MALAGA_%'
        GROUP BY service_id
    ''')).fetchall()
    stats['trips_by_service'] = {r[0]: r[1] for r in result}
    total_trips = sum(stats['trips_by_service'].values())
    stats['trips'] = total_trips
    logger.info(f"  Trips: {total_trips}")
    for service, count in stats['trips_by_service'].items():
        logger.info(f"    {service}: {count}")

    # Stop times
    result = db.execute(text('''
        SELECT COUNT(*) FROM gtfs_stop_times
        WHERE trip_id LIKE 'METRO_MALAGA_%'
    ''')).scalar()
    stats['stop_times'] = result
    logger.info(f"  Stop_times: {result}")

    # Shapes
    result = db.execute(text('''
        SELECT shape_id, COUNT(*)
        FROM gtfs_shape_points
        WHERE shape_id LIKE 'METRO_MALAGA_%'
        GROUP BY shape_id
    ''')).fetchall()
    stats['shapes'] = {r[0]: r[1] for r in result}
    logger.info(f"  Shapes: {len(result)}")
    for shape, count in stats['shapes'].items():
        logger.info(f"    {shape}: {count} puntos")

    return stats


def main():
    parser = argparse.ArgumentParser(description='Import Metro Málaga GTFS data')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN - No se harán cambios en la base de datos")
        logger.info("=" * 60)

    db = SessionLocal()

    try:
        # Execute all steps
        calendars = create_calendars(db, args.dry_run)
        calendar_dates = create_calendar_dates(db, args.dry_run)
        trips = import_trips(db, args.dry_run)
        stop_times = import_stop_times(db, args.dry_run)
        shapes = import_shapes(db, args.dry_run)

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
        logger.info(f"  Calendarios: {calendars}")
        logger.info(f"  Calendar_dates: {calendar_dates}")
        logger.info(f"  Trips: {trips}")
        logger.info(f"  Stop_times: {stop_times}")
        logger.info(f"  Shape points: {shapes}")

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
