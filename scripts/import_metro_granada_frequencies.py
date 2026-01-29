#!/usr/bin/env python3
"""Import Metro Granada GTFS data based on official frequencies.

This script generates trips from official frequency data from:
https://metropolitanogranada.es/horarios

Instead of using the NAP GTFS (which has limited validity and some
frequency discrepancies), this script creates trips based on the
official published frequencies.

Services:
- LABORABLE: Monday-Thursday, 06:30-23:00
- VIERNES: Friday + eve of holidays, 06:30-02:00 (nocturnal)
- SABADO: Saturday, 06:30-02:00 (nocturnal)
- DOMINGO: Sunday + holidays, 06:30-23:00

Usage:
    python scripts/import_metro_granada_frequencies.py [--dry-run]
    python scripts/import_metro_granada_frequencies.py --analyze

GTFS Source: Official frequencies from metropolitanogranada.es
"""

import sys
import os
import argparse
import logging
from datetime import date
from typing import List, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BATCH_SIZE = 5000

# Metro Granada configuration
METRO_GRANADA_ROUTE_ID = 'METRO_GRANADA_L1'
PREFIX = 'METRO_GRANADA_'

# Shape IDs
SHAPE_ID_ALB_ARM = 'METRO_GRANADA_L1_ALB_ARM'  # Albolote -> Armilla (direction 0)
SHAPE_ID_ARM_ALB = 'METRO_GRANADA_L1_ARM_ALB'  # Armilla -> Albolote (direction 1)

# Service IDs
SERVICE_LABORABLE = f'{PREFIX}LABORABLE'
SERVICE_VIERNES = f'{PREFIX}VIERNES'
SERVICE_SABADO = f'{PREFIX}SABADO'
SERVICE_DOMINGO = f'{PREFIX}DOMINGO'

# Travel times from each stop (in seconds) - Direction 0: Albolote -> Armilla
# Extracted from GTFS data
STOP_TIMES_DIR0 = [
    ('METRO_GRANADA_1', 'Albolote', 0),
    ('METRO_GRANADA_2', 'Juncaril', 120),
    ('METRO_GRANADA_3', 'Vicuña', 300),
    ('METRO_GRANADA_4', 'Anfiteatro', 360),
    ('METRO_GRANADA_5', 'Maracena', 480),
    ('METRO_GRANADA_6', 'Cerrillo Maracena', 600),
    ('METRO_GRANADA_7', 'Jaén', 780),
    ('METRO_GRANADA_8', 'Estación de autobuses', 900),
    ('METRO_GRANADA_9', 'Argentinita', 1020),
    ('METRO_GRANADA_10', 'Luis Amador', 1080),
    ('METRO_GRANADA_11', 'Villarejo', 1200),
    ('METRO_GRANADA_12', 'Caleta', 1320),
    ('METRO_GRANADA_13', 'Estación de ferrocarriles', 1440),
    ('METRO_GRANADA_14', 'Universidad', 1500),
    ('METRO_GRANADA_15', 'Méndez Núñez', 1620),
    ('METRO_GRANADA_16', 'Recogidas', 1740),
    ('METRO_GRANADA_17', 'Alcázar Genil', 1800),
    ('METRO_GRANADA_18', 'Hípica', 1920),
    ('METRO_GRANADA_19', 'Andrés Segovia', 2040),
    ('METRO_GRANADA_20', 'Palacio deportes', 2160),
    ('METRO_GRANADA_21', 'Nuevo Los Cármenes', 2280),
    ('METRO_GRANADA_22', 'Dílar', 2400),
    ('METRO_GRANADA_23', 'Parque tecnológico', 2520),
    ('METRO_GRANADA_24', 'Sierra Nevada', 2640),
    ('METRO_GRANADA_25', 'Fernando de los Ríos', 2820),
    ('METRO_GRANADA_26', 'Armilla', 3000),  # 50 minutes
]

# Travel times - Direction 1: Armilla -> Albolote
STOP_TIMES_DIR1 = [
    ('METRO_GRANADA_26', 'Armilla', 0),
    ('METRO_GRANADA_25', 'Fernando de los Ríos', 180),
    ('METRO_GRANADA_24', 'Sierra Nevada', 360),
    ('METRO_GRANADA_23', 'Parque tecnológico', 540),
    ('METRO_GRANADA_22', 'Dílar', 660),
    ('METRO_GRANADA_21', 'Nuevo Los Cármenes', 780),
    ('METRO_GRANADA_20', 'Palacio deportes', 900),
    ('METRO_GRANADA_19', 'Andrés Segovia', 1020),
    ('METRO_GRANADA_18', 'Hípica', 1140),
    ('METRO_GRANADA_17', 'Alcázar Genil', 1260),
    ('METRO_GRANADA_16', 'Recogidas', 1320),
    ('METRO_GRANADA_15', 'Méndez Núñez', 1440),
    ('METRO_GRANADA_14', 'Universidad', 1560),
    ('METRO_GRANADA_13', 'Estación de ferrocarriles', 1620),
    ('METRO_GRANADA_12', 'Caleta', 1740),
    ('METRO_GRANADA_11', 'Villarejo', 1860),
    ('METRO_GRANADA_10', 'Luis Amador', 1980),
    ('METRO_GRANADA_9', 'Argentinita', 2040),
    ('METRO_GRANADA_8', 'Estación de autobuses', 2160),
    ('METRO_GRANADA_7', 'Jaén', 2280),
    ('METRO_GRANADA_6', 'Cerrillo Maracena', 2460),
    ('METRO_GRANADA_5', 'Maracena', 2580),
    ('METRO_GRANADA_4', 'Anfiteatro', 2700),
    ('METRO_GRANADA_3', 'Vicuña', 2820),
    ('METRO_GRANADA_2', 'Juncaril', 2940),
    ('METRO_GRANADA_1', 'Albolote', 3060),  # 51 minutes
]

# Official frequencies from https://metropolitanogranada.es/horarios
# Format: (start_seconds, end_seconds, headway_seconds)
FREQUENCIES_LABORABLE = [
    (6*3600+30*60, 7*3600+30*60, 510),    # 06:30-07:30: cada 8'30"
    (7*3600+30*60, 10*3600, 390),          # 07:30-10:00: cada 6'30"
    (10*3600, 13*3600+30*60, 480),         # 10:00-13:30: cada 8'
    (13*3600+30*60, 20*3600+30*60, 390),   # 13:30-20:30: cada 6'30"
    (20*3600+30*60, 23*3600, 510),         # 20:30-23:00: cada 8'30"
]

FREQUENCIES_VIERNES = [
    (6*3600+30*60, 7*3600+30*60, 510),    # 06:30-07:30: cada 8'30"
    (7*3600+30*60, 10*3600, 390),          # 07:30-10:00: cada 6'30"
    (10*3600, 13*3600+30*60, 480),         # 10:00-13:30: cada 8'
    (13*3600+30*60, 20*3600+30*60, 390),   # 13:30-20:30: cada 6'30"
    (20*3600+30*60, 23*3600, 510),         # 20:30-23:00: cada 8'30"
    (23*3600, 26*3600, 900),               # 23:00-02:00: cada 15' (nocturno)
]

FREQUENCIES_SABADO = [
    (6*3600+30*60, 9*3600+30*60, 900),    # 06:30-09:30: cada 15'
    (9*3600+30*60, 23*3600, 600),          # 09:30-23:00: cada 10'
    (23*3600, 26*3600, 900),               # 23:00-02:00: cada 15' (nocturno)
]

FREQUENCIES_DOMINGO = [
    (6*3600+30*60, 9*3600+30*60, 900),    # 06:30-09:30: cada 15'
    (9*3600+30*60, 20*3600+30*60, 660),    # 09:30-20:30: cada 11'
    (20*3600+30*60, 23*3600, 900),         # 20:30-23:00: cada 15'
]

# Festivos de Granada 2026
# Fuente: BOE + Junta de Andalucía + Ayuntamiento de Granada
FESTIVOS_2026 = [
    ('2026-01-01', 'Año Nuevo'),
    ('2026-01-06', 'Reyes'),
    ('2026-02-28', 'Día de Andalucía'),
    ('2026-04-02', 'Jueves Santo'),
    ('2026-04-03', 'Viernes Santo'),
    ('2026-05-01', 'Día del Trabajo'),
    ('2026-06-04', 'Corpus Christi'),  # Local Granada
    ('2026-08-15', 'Asunción'),
    ('2026-10-12', 'Fiesta Nacional'),
    ('2026-11-01', 'Todos los Santos'),
    ('2026-12-06', 'Constitución'),
    ('2026-12-08', 'Inmaculada'),
    ('2026-12-25', 'Navidad'),
]

# Vísperas de festivo 2026 (días que activan servicio VIERNES/nocturno)
# Solo los que no son viernes ni sábado
VISPERAS_2026 = [
    ('2025-12-31', 'Víspera Año Nuevo', 'wed'),      # Miércoles
    ('2026-01-05', 'Víspera Reyes', 'mon'),          # Lunes
    ('2026-04-01', 'Víspera Jueves Santo', 'wed'),   # Miércoles
    ('2026-04-30', 'Víspera 1 Mayo', 'thu'),         # Jueves
    ('2026-06-03', 'Víspera Corpus', 'wed'),         # Miércoles
    ('2026-10-11', 'Víspera Fiesta Nacional', 'sun'), # Domingo
    ('2026-10-31', 'Víspera Todos Santos', 'sat'),   # Ya es sábado - skip
    ('2026-12-05', 'Víspera Constitución', 'sat'),   # Ya es sábado - skip
    ('2026-12-07', 'Víspera Inmaculada', 'mon'),     # Lunes
    ('2026-12-24', 'Víspera Navidad', 'thu'),        # Jueves
]


def seconds_to_time(secs: int) -> str:
    """Convert seconds since midnight to HH:MM:SS format."""
    hours = secs // 3600
    minutes = (secs % 3600) // 60
    seconds = secs % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def get_day_of_week(date_str: str) -> str:
    """Get day of week for a date string YYYY-MM-DD."""
    from datetime import datetime
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    return days[dt.weekday()]


def get_normal_service_for_day(day: str) -> str:
    """Get the normal service_id for a day of the week."""
    if day in ['mon', 'tue', 'wed', 'thu']:
        return SERVICE_LABORABLE
    elif day == 'fri':
        return SERVICE_VIERNES
    elif day == 'sat':
        return SERVICE_SABADO
    else:  # sun
        return SERVICE_DOMINGO


def generate_trips_for_service(
    service_id: str,
    frequencies: List[Tuple[int, int, int]],
    direction: int
) -> Tuple[List[Dict], List[Dict]]:
    """Generate trips and stop_times for a service based on frequencies.

    Args:
        service_id: Service ID (e.g., METRO_GRANADA_LABORABLE)
        frequencies: List of (start_secs, end_secs, headway_secs)
        direction: 0 = Albolote->Armilla, 1 = Armilla->Albolote

    Returns:
        (trips, stop_times) lists
    """
    trips = []
    stop_times = []

    if direction == 0:
        stop_template = STOP_TIMES_DIR0
        headsign = 'Armilla'
        shape_id = SHAPE_ID_ALB_ARM
    else:
        stop_template = STOP_TIMES_DIR1
        headsign = 'Albolote'
        shape_id = SHAPE_ID_ARM_ALB

    trip_num = 0

    for start_secs, end_secs, headway_secs in frequencies:
        current_time = start_secs

        while current_time < end_secs:
            trip_num += 1
            trip_id = f"{service_id}_D{direction}_{trip_num:04d}"

            trips.append({
                'id': trip_id,
                'route_id': METRO_GRANADA_ROUTE_ID,
                'service_id': service_id,
                'headsign': headsign,
                'short_name': None,
                'direction_id': direction,
                'block_id': None,
                'shape_id': shape_id,
                'wheelchair_accessible': 1,
                'bikes_allowed': 1,
            })

            # Generate stop_times
            for seq, (stop_id, stop_name, offset_secs) in enumerate(stop_template, 1):
                arrival_secs = current_time + offset_secs
                time_str = seconds_to_time(arrival_secs)

                stop_times.append({
                    'trip_id': trip_id,
                    'stop_sequence': seq,
                    'stop_id': stop_id,
                    'arrival_time': time_str,
                    'departure_time': time_str,
                    'arrival_seconds': arrival_secs,
                    'departure_seconds': arrival_secs,
                    'stop_headsign': None,
                    'pickup_type': 0,
                    'drop_off_type': 0,
                    'shape_dist_traveled': None,
                    'timepoint': 1,
                })

            current_time += headway_secs

    return trips, stop_times


def generate_all_trips() -> Tuple[List[Dict], List[Dict]]:
    """Generate all trips and stop_times for all services."""
    all_trips = []
    all_stop_times = []

    services = [
        (SERVICE_LABORABLE, FREQUENCIES_LABORABLE),
        (SERVICE_VIERNES, FREQUENCIES_VIERNES),
        (SERVICE_SABADO, FREQUENCIES_SABADO),
        (SERVICE_DOMINGO, FREQUENCIES_DOMINGO),
    ]

    for service_id, frequencies in services:
        # Direction 0: Albolote -> Armilla
        trips, stop_times = generate_trips_for_service(service_id, frequencies, 0)
        all_trips.extend(trips)
        all_stop_times.extend(stop_times)

        # Direction 1: Armilla -> Albolote
        trips, stop_times = generate_trips_for_service(service_id, frequencies, 1)
        all_trips.extend(trips)
        all_stop_times.extend(stop_times)

    return all_trips, all_stop_times


def create_calendars(db, dry_run: bool) -> int:
    """Create the 4 calendar services."""
    logger.info("Creating calendars...")

    calendars = [
        (SERVICE_LABORABLE, True, True, True, True, False, False, False),
        (SERVICE_VIERNES, False, False, False, False, True, False, False),
        (SERVICE_SABADO, False, False, False, False, False, True, False),
        (SERVICE_DOMINGO, False, False, False, False, False, False, True),
    ]

    if dry_run:
        for cal in calendars:
            logger.info(f"  [DRY-RUN] Would create calendar: {cal[0]}")
        return len(calendars)

    # Delete existing calendar_dates first (FK constraint)
    db.execute(text("DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_GRANADA_%'"))
    # Delete existing calendars
    db.execute(text("DELETE FROM gtfs_calendar WHERE service_id LIKE 'METRO_GRANADA_%'"))

    for cal_id, mon, tue, wed, thu, fri, sat, sun in calendars:
        db.execute(text('''
            INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
            VALUES (:service_id, :mon, :tue, :wed, :thu, :fri, :sat, :sun, '2026-01-01', '2026-12-31')
        '''), {
            'service_id': cal_id, 'mon': mon, 'tue': tue, 'wed': wed,
            'thu': thu, 'fri': fri, 'sat': sat, 'sun': sun
        })
        logger.info(f"  Created calendar: {cal_id}")

    db.commit()
    return len(calendars)


def create_calendar_dates(db, dry_run: bool) -> int:
    """Create calendar_dates for festivos and vísperas."""
    logger.info("Creating calendar_dates (festivos y vísperas)...")

    count = 0

    if not dry_run:
        db.execute(text("DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_GRANADA_%'"))

    # Festivos: add DOMINGO service, remove normal day service
    for fecha, nombre in FESTIVOS_2026:
        day = get_day_of_week(fecha)
        normal_service = get_normal_service_for_day(day)

        if dry_run:
            logger.info(f"  [DRY-RUN] Festivo {fecha} ({nombre}): +DOMINGO, -{normal_service}")
        else:
            # Add DOMINGO service
            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :fecha, 1)
            '''), {'service_id': SERVICE_DOMINGO, 'fecha': fecha})

            # Remove normal service (if not already DOMINGO)
            if normal_service != SERVICE_DOMINGO:
                db.execute(text('''
                    INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                    VALUES (:service_id, :fecha, 2)
                '''), {'service_id': normal_service, 'fecha': fecha})
                count += 2
            else:
                count += 1

    # Vísperas: add VIERNES service (nocturnal), remove normal day service
    for fecha, nombre, day in VISPERAS_2026:
        # Skip if already Friday or Saturday (already has nocturnal service)
        if day in ['fri', 'sat']:
            continue

        normal_service = get_normal_service_for_day(day)

        if dry_run:
            logger.info(f"  [DRY-RUN] Víspera {fecha} ({nombre}): +VIERNES, -{normal_service}")
        else:
            # Add VIERNES service (nocturnal)
            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :fecha, 1)
            '''), {'service_id': SERVICE_VIERNES, 'fecha': fecha})

            # Remove normal service
            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :fecha, 2)
            '''), {'service_id': normal_service, 'fecha': fecha})
            count += 2

    if not dry_run:
        db.commit()

    logger.info(f"  Total calendar_dates: {count}")
    return count


def clear_metro_granada_data(db):
    """Clear existing Metro Granada trips and stop_times."""
    logger.info("Clearing existing Metro Granada schedule data...")

    # Delete stop_times
    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id IN (
            SELECT id FROM gtfs_trips WHERE route_id = :rid
        )
    """), {'rid': METRO_GRANADA_ROUTE_ID})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id = :rid"
    ), {'rid': METRO_GRANADA_ROUTE_ID})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} trips")


def import_trips(db, trips: List[Dict]) -> int:
    """Import generated trips."""
    logger.info(f"Importing {len(trips):,} trips...")

    for i in range(0, len(trips), BATCH_SIZE):
        batch = trips[i:i+BATCH_SIZE]
        db.execute(
            text("""
                INSERT INTO gtfs_trips
                (id, route_id, service_id, headsign, short_name, direction_id, block_id, shape_id, wheelchair_accessible, bikes_allowed)
                VALUES (:id, :route_id, :service_id, :headsign, :short_name, :direction_id, :block_id, :shape_id, :wheelchair_accessible, :bikes_allowed)
            """),
            batch
        )

        if (i + BATCH_SIZE) % 5000 == 0 or i + BATCH_SIZE >= len(trips):
            logger.info(f"  Imported {min(i + BATCH_SIZE, len(trips)):,} trips...")
            db.commit()

    db.commit()
    return len(trips)


def import_stop_times(db, stop_times: List[Dict]) -> int:
    """Import generated stop_times."""
    logger.info(f"Importing {len(stop_times):,} stop_times...")

    for i in range(0, len(stop_times), BATCH_SIZE):
        batch = stop_times[i:i+BATCH_SIZE]
        db.execute(
            text("""
                INSERT INTO gtfs_stop_times
                (trip_id, stop_sequence, stop_id, arrival_time, departure_time,
                 arrival_seconds, departure_seconds, stop_headsign, pickup_type,
                 drop_off_type, shape_dist_traveled, timepoint)
                VALUES (:trip_id, :stop_sequence, :stop_id, :arrival_time, :departure_time,
                        :arrival_seconds, :departure_seconds, :stop_headsign, :pickup_type,
                        :drop_off_type, :shape_dist_traveled, :timepoint)
            """),
            batch
        )

        if (i + BATCH_SIZE) % 20000 == 0 or i + BATCH_SIZE >= len(stop_times):
            logger.info(f"  Imported {min(i + BATCH_SIZE, len(stop_times)):,} stop_times...")
            db.commit()

    db.commit()
    return len(stop_times)


def verify_route_exists(db) -> bool:
    """Verify Metro Granada route exists."""
    result = db.execute(text(
        "SELECT id, short_name FROM gtfs_routes WHERE id = :rid"
    ), {'rid': METRO_GRANADA_ROUTE_ID}).fetchone()

    if not result:
        logger.error(f"Route {METRO_GRANADA_ROUTE_ID} not found!")
        return False

    logger.info(f"Found route: {result[0]} ({result[1]})")
    return True


def verify_stops_exist(db) -> bool:
    """Verify Metro Granada stops exist."""
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_stops WHERE id LIKE 'METRO_GRANADA_%'"
    )).scalar()

    logger.info(f"Found {result} METRO_GRANADA stops")
    return result == 26


def analyze():
    """Analyze and show expansion estimates."""
    print("\n" + "=" * 70)
    print("METRO GRANADA - FREQUENCY EXPANSION ANALYSIS")
    print("=" * 70)

    all_trips, all_stop_times = generate_all_trips()

    print(f"\nTotal trips to generate: {len(all_trips):,}")
    print(f"Total stop_times to generate: {len(all_stop_times):,}")

    # By service
    print("\n" + "-" * 70)
    print("TRIPS BY SERVICE")
    print("-" * 70)

    by_service = {}
    for trip in all_trips:
        sid = trip['service_id']
        by_service[sid] = by_service.get(sid, 0) + 1

    for sid in sorted(by_service.keys()):
        print(f"  {sid}: {by_service[sid]:,} trips")

    # By direction
    print("\n" + "-" * 70)
    print("TRIPS BY DIRECTION")
    print("-" * 70)

    dir0 = sum(1 for t in all_trips if t['direction_id'] == 0)
    dir1 = sum(1 for t in all_trips if t['direction_id'] == 1)
    print(f"  Direction 0 (Albolote -> Armilla): {dir0:,}")
    print(f"  Direction 1 (Armilla -> Albolote): {dir1:,}")

    # Sample trips
    print("\n" + "-" * 70)
    print("SAMPLE TRIPS (first 10)")
    print("-" * 70)

    for trip in all_trips[:10]:
        print(f"  {trip['id']}: {trip['headsign']} ({trip['service_id'].split('_')[-1]})")

    # Festivos
    print("\n" + "-" * 70)
    print("FESTIVOS 2026")
    print("-" * 70)

    for fecha, nombre in FESTIVOS_2026:
        day = get_day_of_week(fecha)
        print(f"  {fecha} ({day}): {nombre}")

    # Vísperas
    print("\n" + "-" * 70)
    print("VÍSPERAS 2026 (with nocturnal service)")
    print("-" * 70)

    for fecha, nombre, day in VISPERAS_2026:
        skip = " (skip - already nocturnal)" if day in ['fri', 'sat'] else ""
        print(f"  {fecha} ({day}): {nombre}{skip}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Import Metro Granada GTFS data based on official frequencies'
    )
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze and show expansion estimates'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()

    if args.analyze:
        analyze()
        sys.exit(0)

    if args.dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN - No changes will be made")
        logger.info("=" * 60)
        analyze()
        sys.exit(0)

    # Generate trips
    logger.info("Generating trips from official frequencies...")
    all_trips, all_stop_times = generate_all_trips()
    logger.info(f"Generated {len(all_trips):,} trips and {len(all_stop_times):,} stop_times")

    # Import to database
    db = SessionLocal()

    try:
        from datetime import datetime
        start_time = datetime.now()

        # Verify prerequisites
        if not verify_route_exists(db):
            sys.exit(1)

        if not verify_stops_exist(db):
            logger.error("Metro Granada stops not found! Import stops first.")
            sys.exit(1)

        # Clear existing data
        clear_metro_granada_data(db)

        # Create calendars
        calendar_count = create_calendars(db, False)
        logger.info(f"Created {calendar_count} calendars")

        # Create calendar_dates
        calendar_dates_count = create_calendar_dates(db, False)
        logger.info(f"Created {calendar_dates_count} calendar_dates")

        # Import trips
        trips_count = import_trips(db, all_trips)
        logger.info(f"Imported {trips_count:,} trips")

        # Import stop_times
        stop_times_count = import_stop_times(db, all_stop_times)
        logger.info(f"Imported {stop_times_count:,} stop_times")

        elapsed = datetime.now() - start_time

        # Summary
        print("\n" + "=" * 70)
        print("IMPORT SUMMARY - Metro de Granada")
        print("=" * 70)
        print(f"Calendars: {calendar_count}")
        print(f"Calendar dates: {calendar_dates_count}")
        print(f"Trips: {trips_count:,}")
        print(f"Stop times: {stop_times_count:,}")
        print(f"Elapsed time: {elapsed}")
        print("=" * 70)
        print("\nMetro Granada import completed successfully!")
        print("\nNext steps:")
        print("  1. Restart the server to reload GTFSStore")
        print("  2. Verify with: SELECT service_id, COUNT(*) FROM gtfs_trips WHERE route_id LIKE 'METRO_GRANADA%' GROUP BY service_id;")
        print("  3. Test departures: curl 'http://localhost:8002/api/v1/gtfs/stops/METRO_GRANADA_1/departures?limit=5'")

    except Exception as e:
        db.rollback()
        logger.error(f"Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
