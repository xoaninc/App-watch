#!/usr/bin/env python3
"""Import TRAM Alicante GTFS data from NAP.

This script imports the complete GTFS data for TRAM Alicante (Trenes y tranvías
de Alicante y Costa Blanca):
- 48 route variants (lines 1, 2, 3, 4, 5, 9)
- 70 stops
- ~2,214 trips
- ~38,024 stop_times
- 12 shapes

Usage:
    python scripts/import_tram_alicante_gtfs.py [--dry-run] [--analyze]

GTFS Source: NAP (Punto de Acceso Nacional) - Fichero ID 1167
Download: curl -X GET "https://nap.transportes.gob.es/api/Fichero/download/1167" \
          -H "ApiKey: YOUR_API_KEY" -o data/gtfs_tram_alicante.zip
"""

import os
import sys
import csv
import argparse
import logging
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Path to GTFS files
GTFS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'gtfs_tram_alicante')

# ID prefix for TRAM Alicante
PREFIX = 'TRAM_ALICANTE_'

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
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        return [row for row in reader]


def clear_existing_data(db, dry_run: bool = False) -> Dict[str, int]:
    """Clear existing TRAM Alicante data."""
    logger.info("Paso 1: Limpiando datos existentes de TRAM Alicante...")

    counts = {}

    if dry_run:
        counts['stop_times'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'TRAM_ALICANTE_%'"
        )).scalar()
        counts['trips'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_trips WHERE route_id LIKE 'TRAM_ALICANTE_%'"
        )).scalar()
        counts['calendar_dates'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_calendar_dates WHERE service_id LIKE 'TRAM_ALICANTE_%'"
        )).scalar()
        counts['calendars'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'TRAM_ALICANTE_%'"
        )).scalar()

        for key, count in counts.items():
            logger.info(f"  [DRY-RUN] Se borrarían {count} {key}")
        return counts

    # Delete stop_times first (FK constraint)
    result = db.execute(text(
        "DELETE FROM gtfs_stop_times WHERE trip_id LIKE 'TRAM_ALICANTE_%'"
    ))
    counts['stop_times'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id LIKE 'TRAM_ALICANTE_%'"
    ))
    counts['trips'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} trips")

    # Delete calendar_dates
    result = db.execute(text(
        "DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'TRAM_ALICANTE_%'"
    ))
    counts['calendar_dates'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} calendar_dates")

    # Delete calendars
    result = db.execute(text(
        "DELETE FROM gtfs_calendar WHERE service_id LIKE 'TRAM_ALICANTE_%'"
    ))
    counts['calendars'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} calendars")

    db.commit()
    return counts


def import_calendar(db, dry_run: bool = False) -> int:
    """Import calendar.txt."""
    logger.info("Paso 2: Importando calendarios...")

    rows = load_csv('calendar.txt')

    if not rows:
        logger.warning("  No se encontró calendar.txt")
        return 0

    calendars = []
    for row in rows:
        service_id = row['service_id'].strip()
        our_service_id = f"{PREFIX}{service_id}"

        calendars.append({
            'service_id': our_service_id,
            'monday': row['monday'].strip() == '1',
            'tuesday': row['tuesday'].strip() == '1',
            'wednesday': row['wednesday'].strip() == '1',
            'thursday': row['thursday'].strip() == '1',
            'friday': row['friday'].strip() == '1',
            'saturday': row['saturday'].strip() == '1',
            'sunday': row['sunday'].strip() == '1',
            'start_date': parse_date(row['start_date'].strip()),
            'end_date': parse_date(row['end_date'].strip()),
        })

    if dry_run:
        logger.info(f"  [DRY-RUN] Se importarían {len(calendars)} calendarios")
        return len(calendars)

    if calendars:
        db.execute(
            text("""
                INSERT INTO gtfs_calendar
                (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                VALUES (:service_id, :monday, :tuesday, :wednesday, :thursday, :friday, :saturday, :sunday, :start_date, :end_date)
                ON CONFLICT (service_id) DO UPDATE SET
                    monday = EXCLUDED.monday,
                    tuesday = EXCLUDED.tuesday,
                    wednesday = EXCLUDED.wednesday,
                    thursday = EXCLUDED.thursday,
                    friday = EXCLUDED.friday,
                    saturday = EXCLUDED.saturday,
                    sunday = EXCLUDED.sunday,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date
            """),
            calendars
        )
        db.commit()

    logger.info(f"  Importados {len(calendars)} calendarios")
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
        service_id = row['service_id'].strip()
        our_service_id = f"{PREFIX}{service_id}"

        calendar_dates.append({
            'service_id': our_service_id,
            'date': parse_date(row['date'].strip()),
            'exception_type': int(row['exception_type'].strip()),
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
        gtfs_route_id = row['route_id'].strip()
        gtfs_service_id = row['service_id'].strip()
        gtfs_trip_id = row['trip_id'].strip()
        gtfs_shape_id = row.get('shape_id', '').strip()

        our_route_id = f"{PREFIX}{gtfs_route_id}"
        our_service_id = f"{PREFIX}{gtfs_service_id}"
        our_trip_id = f"{PREFIX}{gtfs_trip_id}"
        # Keep shape_id as-is (numeric IDs without prefix)
        our_shape_id = gtfs_shape_id if gtfs_shape_id else None

        trips.append({
            'id': our_trip_id,
            'route_id': our_route_id,
            'service_id': our_service_id,
            'headsign': row.get('trip_headsign', '').strip() or None,
            'short_name': row.get('trip_short_name', '').strip() or None,
            'direction_id': int(row.get('direction_id', '0').strip() or '0'),
            'block_id': row.get('block_id', '').strip() or None,
            'shape_id': our_shape_id,
            'wheelchair_accessible': 1,
            'bikes_allowed': None,
        })

    if dry_run:
        logger.info(f"  [DRY-RUN] Se importarían {len(trips)} trips")
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

        if (i + BATCH_SIZE) % 5000 == 0:
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
        reader.fieldnames = [name.strip() for name in reader.fieldnames]

        for row in reader:
            gtfs_trip_id = row['trip_id'].strip()
            gtfs_stop_id = row['stop_id'].strip()

            our_trip_id = f"{PREFIX}{gtfs_trip_id}"
            our_stop_id = f"{PREFIX}{gtfs_stop_id}"

            arrival_time = row['arrival_time'].strip()
            departure_time = row['departure_time'].strip()

            batch.append({
                'trip_id': our_trip_id,
                'stop_id': our_stop_id,
                'arrival_time': arrival_time,
                'departure_time': departure_time,
                'arrival_seconds': time_to_seconds(arrival_time),
                'departure_seconds': time_to_seconds(departure_time),
                'stop_sequence': int(row['stop_sequence'].strip()),
                'stop_headsign': row.get('stop_headsign', '').strip() or None,
                'pickup_type': int(row.get('pickup_type', '0').strip() or '0'),
                'drop_off_type': int(row.get('drop_off_type', '0').strip() or '0'),
                'shape_dist_traveled': None,
                'timepoint': int(row.get('timepoint', '1').strip() or '1'),
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

                if count % 20000 == 0:
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
    """Import shapes.txt (shapes use numeric IDs without prefix)."""
    logger.info("Paso 6: Importando shapes...")

    rows = load_csv('shapes.txt')

    if not rows:
        logger.warning("  No se encontró shapes.txt")
        return 0

    # Group points by shape_id
    shapes = {}
    for row in rows:
        shape_id = row['shape_id'].strip()

        if shape_id not in shapes:
            shapes[shape_id] = []

        shapes[shape_id].append({
            'lat': float(row['shape_pt_lat'].strip()),
            'lon': float(row['shape_pt_lon'].strip()),
            'sequence': int(row['shape_pt_sequence'].strip()),
        })

    if dry_run:
        logger.info(f"  [DRY-RUN] Se importarían {len(shapes)} shapes:")
        total_pts = 0
        for shape_id, points in sorted(shapes.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
            logger.info(f"    {shape_id}: {len(points)} puntos")
            total_pts += len(points)
        return total_pts

    # Check if shapes already exist
    shape_ids = list(shapes.keys())
    existing = db.execute(text(
        "SELECT shape_id, COUNT(*) FROM gtfs_shape_points WHERE shape_id = ANY(:ids) GROUP BY shape_id"
    ), {'ids': shape_ids}).fetchall()

    if existing:
        logger.info(f"  Shapes ya existen en BD ({len(existing)} shapes)")
        logger.info("  Saltando importación de shapes (ya existen)")
        return 0

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

    db.commit()
    logger.info(f"  Importados {count} shape points en {len(shapes)} shapes")
    return count


def verify_import(db) -> Dict:
    """Verify the import was successful."""
    logger.info("Paso 7: Verificando importación...")

    stats = {}

    # Calendars
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'TRAM_ALICANTE_%'"
    )).scalar()
    stats['calendars'] = result
    logger.info(f"  Calendarios: {result}")

    # Calendar dates
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_calendar_dates WHERE service_id LIKE 'TRAM_ALICANTE_%'"
    )).scalar()
    stats['calendar_dates'] = result
    logger.info(f"  Calendar_dates: {result}")

    # Trips by route (top 10)
    result = db.execute(text("""
        SELECT route_id, COUNT(*)
        FROM gtfs_trips
        WHERE route_id LIKE 'TRAM_ALICANTE_%'
        GROUP BY route_id
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)).fetchall()
    total_trips = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_trips WHERE route_id LIKE 'TRAM_ALICANTE_%'"
    )).scalar()
    stats['trips'] = total_trips
    logger.info(f"  Trips: {total_trips:,}")
    logger.info(f"    Top rutas:")
    for route, count in result[:5]:
        short_route = route.replace('TRAM_ALICANTE_', '')
        logger.info(f"      {short_route}: {count}")

    # Stop times
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'TRAM_ALICANTE_%'"
    )).scalar()
    stats['stop_times'] = result
    logger.info(f"  Stop_times: {result:,}")

    # Shapes (numeric IDs)
    result = db.execute(text("""
        SELECT DISTINCT t.shape_id
        FROM gtfs_trips t
        WHERE t.route_id LIKE 'TRAM_ALICANTE_%' AND t.shape_id IS NOT NULL
    """)).fetchall()
    shape_ids = [r[0] for r in result]
    stats['shape_ids'] = shape_ids
    logger.info(f"  Shapes usados: {len(shape_ids)} ({', '.join(sorted(shape_ids, key=lambda x: int(x) if x.isdigit() else 999))})")

    return stats


def analyze():
    """Analyze GTFS files without importing."""
    print("\n" + "=" * 70)
    print("TRAM ALICANTE - GTFS ANALYSIS")
    print("=" * 70)

    # Agency
    agency = load_csv('agency.txt')
    if agency:
        print(f"\nAgency: {agency[0].get('agency_name', 'N/A')}")

    # Routes
    routes = load_csv('routes.txt')
    print(f"\nRoutes: {len(routes)}")
    # Group by line number
    by_line = {}
    for r in routes:
        short_name = r.get('route_short_name', '').strip()
        by_line[short_name] = by_line.get(short_name, 0) + 1
    for line, count in sorted(by_line.items()):
        color = None
        for r in routes:
            if r.get('route_short_name', '').strip() == line:
                color = r.get('route_color', '')
                break
        print(f"  Línea {line}: {count} variantes (color: #{color})")

    # Stops
    stops = load_csv('stops.txt')
    print(f"\nStops: {len(stops)}")

    # Trips
    trips = load_csv('trips.txt')
    print(f"\nTrips: {len(trips):,}")

    # Service IDs
    service_ids = set()
    for t in trips:
        service_ids.add(t.get('service_id', '').strip())
    print(f"Service IDs: {len(service_ids)} ({', '.join(sorted(service_ids))})")

    # Stop times (count lines)
    filepath = os.path.join(GTFS_DIR, 'stop_times.txt')
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            lines = sum(1 for _ in f) - 1
        print(f"\nStop_times: {lines:,}")

    # Shapes
    shapes = load_csv('shapes.txt')
    if shapes:
        by_shape = {}
        for s in shapes:
            shape_id = s.get('shape_id', '').strip()
            by_shape[shape_id] = by_shape.get(shape_id, 0) + 1
        print(f"\nShapes: {len(by_shape)}")
        for shape, count in sorted(by_shape.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
            print(f"  {shape}: {count} puntos")

    # Calendar
    calendar = load_csv('calendar.txt')
    print(f"\nCalendar: {len(calendar)} entradas")

    # Calendar dates
    cal_dates = load_csv('calendar_dates.txt')
    print(f"Calendar_dates: {len(cal_dates)} entradas")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Import TRAM Alicante GTFS data from NAP')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--analyze', action='store_true', help='Analyze GTFS files only')
    args = parser.parse_args()

    # Check GTFS directory exists
    if not os.path.isdir(GTFS_DIR):
        logger.error(f"GTFS directory not found: {GTFS_DIR}")
        logger.error("Download with: curl -X GET 'https://nap.transportes.gob.es/api/Fichero/download/1167' "
                    "-H 'ApiKey: YOUR_KEY' -o data/gtfs_tram_alicante.zip && "
                    "unzip data/gtfs_tram_alicante.zip -d data/gtfs_tram_alicante")
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
        calendars = import_calendar(db, args.dry_run)
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
        print("IMPORT SUMMARY - TRAM Alicante")
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
            print("\n✅ TRAM Alicante GTFS import completed!")
            print("\nNext steps:")
            print("  1. Restart server: systemctl restart renfeserver")
            print("  2. Test: curl 'https://redcercanias.com/api/v1/gtfs/stops/TRAM_ALICANTE_2/departures?limit=5'")

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
