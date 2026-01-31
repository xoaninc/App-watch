#!/usr/bin/env python3
"""Import Tranvía de Murcia GTFS data from NAP.

This script imports the complete GTFS data for Tranvía de Murcia:
- 2 routes: L1A (Nueva Condomina-Universidad), L1B (La Ñora-Terra Natura)
- 28 stops
- ~15,360 trips
- ~800,000+ stop_times
- 2 shapes (L1: 278 pts, L1B: 355 pts)

The NAP GTFS uses calendar_dates.txt only (no calendar.txt).
Each day has its own service_id (e.g., 20260130_2378).

Usage:
    python scripts/import_tranvia_murcia_gtfs.py [--dry-run] [--analyze]

GTFS Source: NAP (Punto de Acceso Nacional) - Fichero ID 1569
Download: curl -X GET "https://nap.transportes.gob.es/api/Fichero/download/1569" \
          -H "ApiKey: YOUR_API_KEY" -o data/gtfs_tranvia_murcia.zip
"""

import os
import sys
import csv
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Path to GTFS files
GTFS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'gtfs_tranvia_murcia')

# ID prefix for Tranvía Murcia
PREFIX = 'TRANVIA_MURCIA_'

# Route mapping
ROUTE_MAPPING = {
    'L1A': f'{PREFIX}L1A',
    'L1B': f'{PREFIX}L1B',
}

# Shape IDs (keep original, they're already in DB as L1, L1B)
SHAPE_MAPPING = {
    'L1': 'L1',
    'L1B': 'L1B',
}

BATCH_SIZE = 5000


def time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS to seconds since midnight."""
    parts = time_str.strip().split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 3600 + int(parts[1]) * 60
    return 0


def parse_date(date_str: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD."""
    date_str = date_str.strip()
    if len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str


def load_csv(filename: str) -> List[Dict]:
    """Load a CSV file from the GTFS directory."""
    filepath = os.path.join(GTFS_DIR, filename)
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # Clean field names (remove quotes and whitespace)
        reader.fieldnames = [name.strip().strip('"') for name in reader.fieldnames]
        return [row for row in reader]


def clear_existing_data(db, dry_run: bool = False) -> Dict[str, int]:
    """Clear existing Tranvía Murcia data."""
    logger.info("Paso 1: Limpiando datos existentes de Tranvía Murcia...")

    counts = {}

    if dry_run:
        # Count what would be deleted
        counts['stop_times'] = db.execute(text("""
            SELECT COUNT(*) FROM gtfs_stop_times
            WHERE trip_id LIKE 'TRANVIA_MURCIA_%'
        """)).scalar()
        counts['trips'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_trips WHERE route_id LIKE 'TRANVIA_MURCIA_%'"
        )).scalar()
        counts['calendar_dates'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_calendar_dates WHERE service_id LIKE 'TRANVIA_MURCIA_%'"
        )).scalar()
        counts['calendars'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'TRANVIA_MURCIA_%'"
        )).scalar()

        for key, count in counts.items():
            logger.info(f"  [DRY-RUN] Se borrarían {count} {key}")
        return counts

    # Delete stop_times first (FK constraint)
    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id LIKE 'TRANVIA_MURCIA_%'
    """))
    counts['stop_times'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id LIKE 'TRANVIA_MURCIA_%'"
    ))
    counts['trips'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} trips")

    # Delete calendar_dates
    result = db.execute(text(
        "DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'TRANVIA_MURCIA_%'"
    ))
    counts['calendar_dates'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} calendar_dates")

    # Delete calendars
    result = db.execute(text(
        "DELETE FROM gtfs_calendar WHERE service_id LIKE 'TRANVIA_MURCIA_%'"
    ))
    counts['calendars'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} calendars")

    db.commit()
    return counts


def create_calendars(db, dry_run: bool = False) -> int:
    """Create calendar entries from unique service_ids in calendar_dates.

    The Murcia GTFS uses only calendar_dates.txt (no calendar.txt).
    We create a dummy calendar entry for each service_id with all days = true,
    and let calendar_dates handle the actual service days.
    """
    logger.info("Paso 2: Creando calendarios...")

    # Load calendar_dates to get unique service_ids
    calendar_dates = load_csv('calendar_dates.txt')
    service_ids = set()

    for row in calendar_dates:
        gtfs_service_id = row['service_id'].strip().strip('"')
        our_service_id = f"{PREFIX}{gtfs_service_id}"
        service_ids.add(our_service_id)

    logger.info(f"  Encontrados {len(service_ids)} service_ids únicos")

    if dry_run:
        logger.info(f"  [DRY-RUN] Se crearían {len(service_ids)} calendarios")
        return len(service_ids)

    # Create calendar entry for each service_id
    # All days = true, dates cover 2026
    calendars = []
    for service_id in service_ids:
        calendars.append({
            'service_id': service_id,
            'monday': True,
            'tuesday': True,
            'wednesday': True,
            'thursday': True,
            'friday': True,
            'saturday': True,
            'sunday': True,
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
        })

    # Insert in batches
    for i in range(0, len(calendars), BATCH_SIZE):
        batch = calendars[i:i+BATCH_SIZE]
        db.execute(
            text("""
                INSERT INTO gtfs_calendar
                (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                VALUES (:service_id, :monday, :tuesday, :wednesday, :thursday, :friday, :saturday, :sunday, :start_date, :end_date)
                ON CONFLICT (service_id) DO UPDATE SET
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date
            """),
            batch
        )

    db.commit()
    logger.info(f"  Creados {len(calendars)} calendarios")
    return len(calendars)


def import_calendar_dates(db, dry_run: bool = False) -> int:
    """Import calendar_dates.txt."""
    logger.info("Paso 3: Importando calendar_dates...")

    rows = load_csv('calendar_dates.txt')

    if not rows:
        logger.warning("  No se encontró calendar_dates.txt")
        return 0

    calendar_dates = []
    for row in rows:
        gtfs_service_id = row['service_id'].strip().strip('"')
        our_service_id = f"{PREFIX}{gtfs_service_id}"

        calendar_dates.append({
            'service_id': our_service_id,
            'date': parse_date(row['date'].strip().strip('"')),
            'exception_type': int(row['exception_type'].strip().strip('"')),
        })

    if dry_run:
        logger.info(f"  [DRY-RUN] Se importarían {len(calendar_dates)} calendar_dates")
        return len(calendar_dates)

    # Insert in batches
    for i in range(0, len(calendar_dates), BATCH_SIZE):
        batch = calendar_dates[i:i+BATCH_SIZE]
        db.execute(
            text("""
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :date, :exception_type)
                ON CONFLICT (service_id, date) DO UPDATE SET
                    exception_type = EXCLUDED.exception_type
            """),
            batch
        )

    db.commit()
    logger.info(f"  Importados {len(calendar_dates)} calendar_dates")
    return len(calendar_dates)


def import_trips(db, dry_run: bool = False) -> int:
    """Import trips.txt."""
    logger.info("Paso 4: Importando trips...")

    rows = load_csv('trips.txt')

    if not rows:
        logger.warning("  No se encontró trips.txt")
        return 0

    trips = []
    for row in rows:
        gtfs_route_id = row['route_id'].strip().strip('"')
        gtfs_service_id = row['service_id'].strip().strip('"')
        gtfs_trip_id = row['trip_id'].strip().strip('"')
        gtfs_shape_id = row.get('shape_id', '').strip().strip('"')

        our_route_id = ROUTE_MAPPING.get(gtfs_route_id, f"{PREFIX}{gtfs_route_id}")
        our_service_id = f"{PREFIX}{gtfs_service_id}"
        our_trip_id = f"{PREFIX}{gtfs_trip_id}"
        our_shape_id = SHAPE_MAPPING.get(gtfs_shape_id, gtfs_shape_id) if gtfs_shape_id else None

        trips.append({
            'id': our_trip_id,
            'route_id': our_route_id,
            'service_id': our_service_id,
            'headsign': row.get('trip_headsign', '').strip().strip('"') or None,
            'short_name': row.get('trip_short_name', '').strip().strip('"') or None,
            'direction_id': int(row.get('direction_id', '0').strip().strip('"') or '0'),
            'block_id': row.get('block_id', '').strip().strip('"') or None,
            'shape_id': our_shape_id,
            'wheelchair_accessible': 1,
            'bikes_allowed': None,
        })

    if dry_run:
        logger.info(f"  [DRY-RUN] Se importarían {len(trips)} trips")
        # Show sample
        for trip in trips[:3]:
            logger.info(f"    {trip['id']} -> {trip['route_id']} (shape: {trip['shape_id']})")
        return len(trips)

    # Insert in batches
    for i in range(0, len(trips), BATCH_SIZE):
        batch = trips[i:i+BATCH_SIZE]
        db.execute(
            text("""
                INSERT INTO gtfs_trips
                (id, route_id, service_id, headsign, short_name, direction_id, block_id, shape_id, wheelchair_accessible, bikes_allowed)
                VALUES (:id, :route_id, :service_id, :headsign, :short_name, :direction_id, :block_id, :shape_id, :wheelchair_accessible, :bikes_allowed)
                ON CONFLICT (id) DO UPDATE SET
                    route_id = EXCLUDED.route_id,
                    service_id = EXCLUDED.service_id,
                    headsign = EXCLUDED.headsign,
                    direction_id = EXCLUDED.direction_id,
                    shape_id = EXCLUDED.shape_id
            """),
            batch
        )

        if (i + BATCH_SIZE) % 10000 == 0:
            logger.info(f"    Procesados {i + BATCH_SIZE} trips...")
            db.commit()

    db.commit()
    logger.info(f"  Importados {len(trips)} trips")
    return len(trips)


def import_stop_times(db, dry_run: bool = False) -> int:
    """Import stop_times.txt."""
    logger.info("Paso 5: Importando stop_times...")

    filepath = os.path.join(GTFS_DIR, 'stop_times.txt')
    if not os.path.exists(filepath):
        logger.warning("  No se encontró stop_times.txt")
        return 0

    count = 0
    batch = []

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [name.strip().strip('"') for name in reader.fieldnames]

        for row in reader:
            gtfs_trip_id = row['trip_id'].strip().strip('"')
            gtfs_stop_id = row['stop_id'].strip().strip('"')

            our_trip_id = f"{PREFIX}{gtfs_trip_id}"
            our_stop_id = f"{PREFIX}{gtfs_stop_id}"

            arrival_time = row['arrival_time'].strip().strip('"')
            departure_time = row['departure_time'].strip().strip('"')

            batch.append({
                'trip_id': our_trip_id,
                'stop_id': our_stop_id,
                'arrival_time': arrival_time,
                'departure_time': departure_time,
                'arrival_seconds': time_to_seconds(arrival_time),
                'departure_seconds': time_to_seconds(departure_time),
                'stop_sequence': int(row['stop_sequence'].strip().strip('"')),
                'stop_headsign': row.get('stop_headsign', '').strip().strip('"') or None,
                'pickup_type': int(row.get('pickup_type', '0').strip().strip('"') or '0'),
                'drop_off_type': int(row.get('drop_off_type', '0').strip().strip('"') or '0'),
                'shape_dist_traveled': None,
                'timepoint': int(row.get('timepoint', '1').strip().strip('"') or '1'),
            })

            count += 1

            if len(batch) >= BATCH_SIZE:
                if not dry_run:
                    db.execute(
                        text("""
                            INSERT INTO gtfs_stop_times
                            (trip_id, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds,
                             stop_sequence, stop_headsign, pickup_type, drop_off_type, shape_dist_traveled, timepoint)
                            VALUES (:trip_id, :stop_id, :arrival_time, :departure_time, :arrival_seconds, :departure_seconds,
                                    :stop_sequence, :stop_headsign, :pickup_type, :drop_off_type, :shape_dist_traveled, :timepoint)
                        """),
                        batch
                    )
                    db.commit()

                if count % 100000 == 0:
                    logger.info(f"    Procesados {count:,} stop_times...")

                batch = []

    # Insert remaining batch
    if batch and not dry_run:
        db.execute(
            text("""
                INSERT INTO gtfs_stop_times
                (trip_id, stop_id, arrival_time, departure_time, arrival_seconds, departure_seconds,
                 stop_sequence, stop_headsign, pickup_type, drop_off_type, shape_dist_traveled, timepoint)
                VALUES (:trip_id, :stop_id, :arrival_time, :departure_time, :arrival_seconds, :departure_seconds,
                        :stop_sequence, :stop_headsign, :pickup_type, :drop_off_type, :shape_dist_traveled, :timepoint)
            """),
            batch
        )
        db.commit()

    if dry_run:
        logger.info(f"  [DRY-RUN] Se importarían {count:,} stop_times")
    else:
        logger.info(f"  Importados {count:,} stop_times")

    return count


def import_shapes(db, dry_run: bool = False) -> int:
    """Import shapes.txt (optional - shapes may already exist)."""
    logger.info("Paso 6: Importando shapes...")

    rows = load_csv('shapes.txt')

    if not rows:
        logger.warning("  No se encontró shapes.txt")
        return 0

    # Group points by shape_id
    shapes = {}
    for row in rows:
        shape_id = row['shape_id'].strip().strip('"')

        if shape_id not in shapes:
            shapes[shape_id] = []

        shapes[shape_id].append({
            'lat': float(row['shape_pt_lat'].strip().strip('"')),
            'lon': float(row['shape_pt_lon'].strip().strip('"')),
            'sequence': int(row['shape_pt_sequence'].strip().strip('"')),
        })

    if dry_run:
        logger.info(f"  [DRY-RUN] Se importarían {len(shapes)} shapes:")
        for shape_id, points in shapes.items():
            logger.info(f"    {shape_id}: {len(points)} puntos")
        return sum(len(pts) for pts in shapes.values())

    # Check if shapes already exist
    existing = db.execute(text(
        "SELECT shape_id, COUNT(*) FROM gtfs_shape_points WHERE shape_id IN ('L1', 'L1B') GROUP BY shape_id"
    )).fetchall()

    if existing:
        logger.info(f"  Shapes ya existen en BD:")
        for shape_id, count in existing:
            logger.info(f"    {shape_id}: {count} puntos")
        logger.info("  Saltando importación de shapes (ya existen)")
        return 0

    # Delete existing shapes for Murcia and insert new ones
    for shape_id in shapes:
        db.execute(text("DELETE FROM gtfs_shape_points WHERE shape_id = :sid"), {'sid': shape_id})

    count = 0
    for shape_id, points in shapes.items():
        # Create shape record
        db.execute(text("""
            INSERT INTO gtfs_shapes (id) VALUES (:id)
            ON CONFLICT (id) DO NOTHING
        """), {'id': shape_id})

        # Insert points
        for pt in sorted(points, key=lambda x: x['sequence']):
            db.execute(text("""
                INSERT INTO gtfs_shape_points (shape_id, lat, lon, sequence)
                VALUES (:shape_id, :lat, :lon, :seq)
            """), {
                'shape_id': shape_id,
                'lat': pt['lat'],
                'lon': pt['lon'],
                'seq': pt['sequence'],
            })
            count += 1

        logger.info(f"    Shape {shape_id}: {len(points)} puntos")

    db.commit()
    logger.info(f"  Importados {count} shape points")
    return count


def verify_import(db) -> Dict:
    """Verify the import was successful."""
    logger.info("Paso 7: Verificando importación...")

    stats = {}

    # Calendars
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'TRANVIA_MURCIA_%'"
    )).scalar()
    stats['calendars'] = result
    logger.info(f"  Calendarios: {result}")

    # Calendar dates
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_calendar_dates WHERE service_id LIKE 'TRANVIA_MURCIA_%'"
    )).scalar()
    stats['calendar_dates'] = result
    logger.info(f"  Calendar_dates: {result}")

    # Trips by route
    result = db.execute(text("""
        SELECT route_id, COUNT(*)
        FROM gtfs_trips
        WHERE route_id LIKE 'TRANVIA_MURCIA_%'
        GROUP BY route_id
        ORDER BY route_id
    """)).fetchall()
    stats['trips_by_route'] = {r[0]: r[1] for r in result}
    total_trips = sum(stats['trips_by_route'].values())
    stats['trips'] = total_trips
    logger.info(f"  Trips: {total_trips:,}")
    for route, count in stats['trips_by_route'].items():
        logger.info(f"    {route}: {count:,}")

    # Stop times
    result = db.execute(text("""
        SELECT COUNT(*) FROM gtfs_stop_times
        WHERE trip_id LIKE 'TRANVIA_MURCIA_%'
    """)).scalar()
    stats['stop_times'] = result
    logger.info(f"  Stop_times: {result:,}")

    # Shapes
    result = db.execute(text("""
        SELECT shape_id, COUNT(*)
        FROM gtfs_shape_points
        WHERE shape_id IN ('L1', 'L1B')
        GROUP BY shape_id
    """)).fetchall()
    stats['shapes'] = {r[0]: r[1] for r in result}
    logger.info(f"  Shapes: {len(result)}")
    for shape, count in stats['shapes'].items():
        logger.info(f"    {shape}: {count} puntos")

    return stats


def analyze():
    """Analyze GTFS files without importing."""
    print("\n" + "=" * 70)
    print("TRANVÍA MURCIA - GTFS ANALYSIS")
    print("=" * 70)

    # Agency
    agency = load_csv('agency.txt')
    if agency:
        print(f"\nAgency: {agency[0].get('agency_name', 'N/A')}")

    # Routes
    routes = load_csv('routes.txt')
    print(f"\nRoutes: {len(routes)}")
    for r in routes:
        route_id = r.get('route_id', '').strip().strip('"')
        name = r.get('route_long_name', '').strip().strip('"')
        print(f"  {route_id}: {name}")

    # Stops
    stops = load_csv('stops.txt')
    print(f"\nStops: {len(stops)}")

    # Trips
    trips = load_csv('trips.txt')
    print(f"\nTrips: {len(trips):,}")

    # Count by route
    by_route = {}
    for t in trips:
        route_id = t.get('route_id', '').strip().strip('"')
        by_route[route_id] = by_route.get(route_id, 0) + 1
    for route, count in sorted(by_route.items()):
        print(f"  {route}: {count:,}")

    # Service IDs
    service_ids = set()
    for t in trips:
        service_ids.add(t.get('service_id', '').strip().strip('"'))
    print(f"\nService IDs únicos: {len(service_ids)}")

    # Stop times (count lines without loading all)
    filepath = os.path.join(GTFS_DIR, 'stop_times.txt')
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            lines = sum(1 for _ in f) - 1  # Subtract header
        print(f"\nStop_times: ~{lines:,}")

    # Shapes
    shapes = load_csv('shapes.txt')
    if shapes:
        by_shape = {}
        for s in shapes:
            shape_id = s.get('shape_id', '').strip().strip('"')
            by_shape[shape_id] = by_shape.get(shape_id, 0) + 1
        print(f"\nShapes: {len(by_shape)}")
        for shape, count in sorted(by_shape.items()):
            print(f"  {shape}: {count} puntos")

    # Calendar dates
    cal_dates = load_csv('calendar_dates.txt')
    print(f"\nCalendar_dates: {len(cal_dates)}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Import Tranvía de Murcia GTFS data from NAP')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--analyze', action='store_true', help='Analyze GTFS files only')
    args = parser.parse_args()

    # Check GTFS directory exists
    if not os.path.isdir(GTFS_DIR):
        logger.error(f"GTFS directory not found: {GTFS_DIR}")
        logger.error("Download with: curl -X GET 'https://nap.transportes.gob.es/api/Fichero/download/1569' "
                    "-H 'ApiKey: YOUR_KEY' -o data/gtfs_tranvia_murcia.zip && "
                    "unzip data/gtfs_tranvia_murcia.zip -d data/gtfs_tranvia_murcia")
        sys.exit(1)

    if args.analyze:
        analyze()
        return

    if args.dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN - No se harán cambios en la base de datos")
        logger.info("=" * 60)

    db = SessionLocal()

    try:
        start_time = datetime.now()

        # Execute all steps
        clear_existing_data(db, args.dry_run)
        calendars = create_calendars(db, args.dry_run)
        calendar_dates = import_calendar_dates(db, args.dry_run)
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

        elapsed = datetime.now() - start_time

        # Summary
        print("\n" + "=" * 70)
        print("IMPORT SUMMARY - Tranvía de Murcia")
        print("=" * 70)
        print(f"Calendarios: {calendars}")
        print(f"Calendar_dates: {calendar_dates}")
        print(f"Trips: {trips:,}")
        print(f"Stop_times: {stop_times:,}")
        print(f"Shape points: {shapes}")
        print(f"Tiempo: {elapsed}")
        print("=" * 70)

        if args.dry_run:
            print("\n[DRY RUN - No se guardaron cambios]")
        else:
            print("\n✅ Tranvía Murcia GTFS import completed!")
            print("\nNext steps:")
            print("  1. Deploy to production: rsync to server")
            print("  2. Run on server: python scripts/import_tranvia_murcia_gtfs.py")
            print("  3. Restart server: systemctl restart renfeserver")
            print("  4. Test: curl 'https://redcercanias.com/api/v1/gtfs/stops/TRANVIA_MURCIA_1/departures?limit=5'")

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
