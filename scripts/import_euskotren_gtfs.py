#!/usr/bin/env python3
"""Import Euskotren GTFS data (trips, stop_times, calendars).

This script updates the Euskotren data to sync with RT feed.
It preserves shapes (already imported) and L3 mapping to Metro Bilbao.

Source: https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfs_euskotren.zip

Usage:
    python scripts/import_euskotren_gtfs.py [--dry-run]
    python scripts/import_euskotren_gtfs.py --gtfs-dir /tmp/euskotren_gtfs
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

DEFAULT_GTFS_DIR = '/tmp/euskotren_gtfs'
PREFIX = 'EUSKOTREN_'


def import_routes(db, gtfs_dir: str, dry_run: bool) -> int:
    """Import routes (upsert to add any missing routes)."""
    logger.info("Paso 0.5: Importando/actualizando routes...")

    # Use existing Euskotren agency for new routes
    DEFAULT_AGENCY = 'EUSKOTREN_ES:Euskotren:Operator:EUS_Funi:'

    # Routes to skip (mapped to other networks)
    SKIP_ROUTES = ['ES:Euskotren:Line:9:']  # L3 -> Metro Bilbao

    routes_file = os.path.join(gtfs_dir, 'routes.txt')
    count = 0
    added = 0
    with open(routes_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            original_route_id = row['route_id'].strip()

            # Skip routes that are mapped to other networks
            if original_route_id in SKIP_ROUTES:
                logger.info(f"  Saltando ruta {original_route_id} (mapeada a Metro Bilbao)")
                count += 1
                continue

            route_id = f"{PREFIX}{original_route_id}"

            if dry_run:
                logger.info(f"  [DRY-RUN] Route: {route_id} ({row['route_short_name']})")
            else:
                # Check if route exists
                exists = db.execute(text(
                    "SELECT 1 FROM gtfs_routes WHERE id = :id"
                ), {'id': route_id}).scalar()

                if not exists:
                    # Only insert new routes, don't update existing
                    db.execute(text('''
                        INSERT INTO gtfs_routes (id, agency_id, short_name, long_name, route_type, color, text_color)
                        VALUES (:id, :agency_id, :short_name, :long_name, :route_type, :color, :text_color)
                    '''), {
                        'id': route_id,
                        'agency_id': DEFAULT_AGENCY,
                        'short_name': row.get('route_short_name', '').strip(),
                        'long_name': row.get('route_long_name', '').strip(),
                        'route_type': int(row.get('route_type', 2)),
                        'color': row.get('route_color', '').strip() or None,
                        'text_color': row.get('route_text_color', '').strip() or None,
                    })
                    added += 1
                    logger.info(f"  Nueva ruta: {route_id} ({row['route_short_name']})")
            count += 1

    logger.info(f"  Routes procesadas: {count}, añadidas: {added}")
    return added


def import_calendars(db, gtfs_dir: str, dry_run: bool) -> int:
    """Import calendar services."""
    logger.info("Paso 1: Importando calendars...")

    calendar_file = os.path.join(gtfs_dir, 'calendar.txt')
    count = 0
    with open(calendar_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            service_id = f"{PREFIX}{row['service_id'].strip()}"

            if dry_run:
                if count < 5:
                    logger.info(f"  [DRY-RUN] Calendar: {service_id}")
            else:
                db.execute(text('''
                    INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                    VALUES (:service_id, :mon, :tue, :wed, :thu, :fri, :sat, :sun, :start_date, :end_date)
                    ON CONFLICT (service_id) DO UPDATE SET
                        monday = EXCLUDED.monday, tuesday = EXCLUDED.tuesday, wednesday = EXCLUDED.wednesday,
                        thursday = EXCLUDED.thursday, friday = EXCLUDED.friday, saturday = EXCLUDED.saturday,
                        sunday = EXCLUDED.sunday, start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date
                '''), {
                    'service_id': service_id,
                    'mon': row['monday'] == '1',
                    'tue': row['tuesday'] == '1',
                    'wed': row['wednesday'] == '1',
                    'thu': row['thursday'] == '1',
                    'fri': row['friday'] == '1',
                    'sat': row['saturday'] == '1',
                    'sun': row['sunday'] == '1',
                    'start_date': row['start_date'],
                    'end_date': row['end_date'],
                })
            count += 1

    logger.info(f"  Calendars importados: {count}")
    return count


def get_mapped_route_id(original_route_id: str) -> str:
    """Map Euskotren route IDs to correct network routes.

    L3 (Line:9) is operated by Metro Bilbao, so map it there.
    """
    # L3 Matiko-Kukullaga -> Metro Bilbao
    if 'Line:9:' in original_route_id:
        return 'METRO_BILBAO_L3'
    return f"{PREFIX}{original_route_id}"


def import_trips(db, gtfs_dir: str, dry_run: bool) -> int:
    """Import trips."""
    logger.info("Paso 2: Importando trips...")

    trips_file = os.path.join(gtfs_dir, 'trips.txt')
    count = 0
    with open(trips_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = f"{PREFIX}{row['trip_id'].strip()}"
            route_id = get_mapped_route_id(row['route_id'].strip())
            service_id = f"{PREFIX}{row['service_id'].strip()}"
            shape_id = f"{PREFIX}{row['shape_id'].strip()}" if row.get('shape_id') else None

            if dry_run:
                if count < 5:
                    logger.info(f"  [DRY-RUN] Trip: {trip_id}")
            else:
                db.execute(text('''
                    INSERT INTO gtfs_trips (id, route_id, service_id, headsign, direction_id, shape_id)
                    VALUES (:id, :route_id, :service_id, :headsign, :direction_id, :shape_id)
                    ON CONFLICT (id) DO UPDATE SET
                        route_id = EXCLUDED.route_id, service_id = EXCLUDED.service_id,
                        headsign = EXCLUDED.headsign, direction_id = EXCLUDED.direction_id,
                        shape_id = EXCLUDED.shape_id
                '''), {
                    'id': trip_id,
                    'route_id': route_id,
                    'service_id': service_id,
                    'headsign': row.get('trip_headsign', '').strip(),
                    'direction_id': int(row['direction_id']) if row.get('direction_id') else 0,
                    'shape_id': shape_id,
                })
            count += 1

            if count % 2000 == 0:
                logger.info(f"  Procesados {count} trips...")

    logger.info(f"  Trips importados: {count}")
    return count


def import_stop_times(db, gtfs_dir: str, dry_run: bool) -> int:
    """Import stop_times."""
    logger.info("Paso 3: Importando stop_times...")

    stop_times_file = os.path.join(gtfs_dir, 'stop_times.txt')

    def time_to_seconds(t):
        if not t:
            return 0
        parts = t.split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    count = 0
    with open(stop_times_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = f"{PREFIX}{row['trip_id'].strip()}"
            stop_id = f"{PREFIX}{row['stop_id'].strip()}"
            arrival = row.get('arrival_time', '').strip()
            departure = row.get('departure_time', '').strip()

            if dry_run:
                if count < 5:
                    logger.info(f"  [DRY-RUN] StopTime: {trip_id} @ {stop_id}")
            else:
                db.execute(text('''
                    INSERT INTO gtfs_stop_times (trip_id, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds, stop_sequence)
                    VALUES (:trip_id, :stop_id, :arrival_time, :departure_time, :arrival_seconds, :departure_seconds, :stop_sequence)
                '''), {
                    'trip_id': trip_id,
                    'stop_id': stop_id,
                    'arrival_time': arrival,
                    'departure_time': departure,
                    'arrival_seconds': time_to_seconds(arrival),
                    'departure_seconds': time_to_seconds(departure),
                    'stop_sequence': int(row['stop_sequence']),
                })
            count += 1

            if count % 20000 == 0:
                logger.info(f"  Procesados {count} stop_times...")

    logger.info(f"  Stop_times importados: {count}")
    return count


def verify_import(db) -> dict:
    """Verify the import."""
    logger.info("Paso 4: Verificando importación...")

    stats = {}

    result = db.execute(text("SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'EUSKOTREN_%'")).scalar()
    stats['calendars'] = result
    logger.info(f"  Calendars: {result}")

    result = db.execute(text("SELECT COUNT(*) FROM gtfs_trips WHERE route_id LIKE 'EUSKOTREN_%'")).scalar()
    stats['trips'] = result
    logger.info(f"  Trips: {result}")

    result = db.execute(text("SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'EUSKOTREN_%'")).scalar()
    stats['stop_times'] = result
    logger.info(f"  Stop_times: {result}")

    # Check RT match
    result = db.execute(text('''
        SELECT COUNT(*) FROM gtfs_rt_trip_updates rt
        JOIN gtfs_trips t ON rt.trip_id = t.id
        WHERE rt.trip_id LIKE 'EUSKOTREN_%'
    ''')).scalar()
    stats['rt_matches'] = result
    logger.info(f"  RT matches: {result}")

    return stats


def delete_existing_data(db, dry_run: bool):
    """Delete existing data in correct order (FK constraints)."""
    logger.info("Paso 0: Eliminando datos existentes...")

    if dry_run:
        logger.info("  [DRY-RUN] Se eliminarían stop_times, trips, calendars")
        return

    # Order matters due to foreign keys: stop_times -> trips -> calendars
    deleted = db.execute(text(
        "DELETE FROM gtfs_stop_times WHERE trip_id LIKE 'EUSKOTREN_%'"
    )).rowcount
    logger.info(f"  Eliminados {deleted} stop_times")

    deleted = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id LIKE 'EUSKOTREN_%'"
    )).rowcount
    logger.info(f"  Eliminados {deleted} trips")

    deleted = db.execute(text(
        "DELETE FROM gtfs_calendar WHERE service_id LIKE 'EUSKOTREN_%' OR service_id LIKE 'ES:Euskotren%'"
    )).rowcount
    logger.info(f"  Eliminados {deleted} calendars")


def main():
    parser = argparse.ArgumentParser(description='Import Euskotren GTFS data')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--gtfs-dir', default=DEFAULT_GTFS_DIR, help='Path to GTFS directory')
    args = parser.parse_args()

    if not os.path.exists(args.gtfs_dir):
        logger.error(f"GTFS directory not found: {args.gtfs_dir}")
        logger.error("Download first:")
        logger.error("  curl -sL 'https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfs_euskotren.zip' -o /tmp/euskotren.zip")
        logger.error("  unzip /tmp/euskotren.zip -d /tmp/euskotren_gtfs")
        sys.exit(1)

    if args.dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN - No se harán cambios")
        logger.info("=" * 60)

    db = SessionLocal()

    try:
        # Delete existing data first (in correct order for FK constraints)
        delete_existing_data(db, args.dry_run)

        # Import routes first (upsert to add any missing)
        routes = import_routes(db, args.gtfs_dir, args.dry_run)

        calendars = import_calendars(db, args.gtfs_dir, args.dry_run)
        trips = import_trips(db, args.gtfs_dir, args.dry_run)
        stop_times = import_stop_times(db, args.gtfs_dir, args.dry_run)

        if not args.dry_run:
            db.commit()
            logger.info("=" * 60)
            logger.info("COMMIT realizado")
            logger.info("=" * 60)
            verify_import(db)

        logger.info("=" * 60)
        logger.info("IMPORTACIÓN COMPLETADA")
        logger.info("=" * 60)
        logger.info(f"  Routes: {routes}")
        logger.info(f"  Calendars: {calendars}")
        logger.info(f"  Trips: {trips}")
        logger.info(f"  Stop_times: {stop_times}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
