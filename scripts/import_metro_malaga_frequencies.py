#!/usr/bin/env python3
"""Import Metro Málaga GTFS data based on official frequencies.

This script generates trips from official frequency data from:
https://metromalaga.es/horarios/

Metro Málaga has 2 lines:
- L1: Andalucía Tech (TCH) <-> Atarazanas (ATZ) - 13 stops, ~20 min
- L2: Palacio de Deportes (PDD) <-> Guadalmedina (GD2) - 8 stops, ~12 min

Services:
- LABORABLE: Monday-Thursday, 06:30-23:00
- VIERNES: Friday + eve of holidays, 06:30-01:30 (nocturnal)
- SABADO: Saturday, 07:00-01:30 (nocturnal)
- DOMINGO: Sunday + holidays, 07:00-23:00

Usage:
    python scripts/import_metro_malaga_frequencies.py [--dry-run]
    python scripts/import_metro_malaga_frequencies.py --analyze

GTFS Source: Official frequencies from metromalaga.es
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BATCH_SIZE = 5000

# Metro Málaga configuration
PREFIX = 'METRO_MALAGA_'

# Route IDs
ROUTE_L1 = f'{PREFIX}1'
ROUTE_L2 = f'{PREFIX}2'

# Shape IDs
SHAPE_L1_TCH_ATZ = f'{PREFIX}L1_DIR1'  # TCH -> ATZ
SHAPE_L1_ATZ_TCH = f'{PREFIX}L1_DIR2'  # ATZ -> TCH
SHAPE_L2_PDD_GD2 = f'{PREFIX}L2_DIR1'  # PDD -> GD2
SHAPE_L2_GD2_PDD = f'{PREFIX}L2_DIR2'  # GD2 -> PDD

# Service IDs
SERVICE_LABORABLE = f'{PREFIX}LABORABLE'
SERVICE_VIERNES = f'{PREFIX}VIERNES'
SERVICE_SABADO = f'{PREFIX}SABADO'
SERVICE_DOMINGO = f'{PREFIX}DOMINGO'

# L1: Andalucía Tech -> Atarazanas (13 stops, ~20 min)
# Times extracted from GTFS
STOP_TIMES_L1_DIR0 = [
    (f'{PREFIX}TCH', 'Andalucía Tech', 0),
    (f'{PREFIX}PRF', 'Paraninfo', 90),
    (f'{PREFIX}CNS', 'El Cónsul', 157),
    (f'{PREFIX}CLI', 'Clínico', 235),
    (f'{PREFIX}UNI', 'Universidad', 339),
    (f'{PREFIX}CDJ', 'Ciudad de la Justicia', 445),
    (f'{PREFIX}PTD', 'Portada Alta', 555),
    (f'{PREFIX}CRR', 'Carranque', 631),
    (f'{PREFIX}BBL', 'Barbarela', 723),
    (f'{PREFIX}LUN', 'La Unión', 858),
    (f'{PREFIX}PC1', 'El Perchel', 992),
    (f'{PREFIX}GD1', 'Guadalmedina', 1111),
    (f'{PREFIX}ATZ', 'Atarazanas', 1217),  # ~20 min
]

# L1: Atarazanas -> Andalucía Tech (reverse)
STOP_TIMES_L1_DIR1 = [
    (f'{PREFIX}ATZ', 'Atarazanas', 0),
    (f'{PREFIX}GD1', 'Guadalmedina', 77),
    (f'{PREFIX}PC1', 'El Perchel', 211),
    (f'{PREFIX}LUN', 'La Unión', 332),
    (f'{PREFIX}BBL', 'Barbarela', 469),
    (f'{PREFIX}CRR', 'Carranque', 558),
    (f'{PREFIX}PTD', 'Portada Alta', 635),
    (f'{PREFIX}CDJ', 'Ciudad de la Justicia', 760),
    (f'{PREFIX}UNI', 'Universidad', 869),
    (f'{PREFIX}CLI', 'Clínico', 978),
    (f'{PREFIX}CNS', 'El Cónsul', 1053),
    (f'{PREFIX}PRF', 'Paraninfo', 1127),
    (f'{PREFIX}TCH', 'Andalucía Tech', 1202),  # ~20 min
]

# L2: Palacio de Deportes -> Guadalmedina (8 stops, ~12 min)
STOP_TIMES_L2_DIR0 = [
    (f'{PREFIX}PDD', 'Palacio de Deportes', 0),
    (f'{PREFIX}PBL', 'Puerta Blanca', 123),
    (f'{PREFIX}LZP', 'La Luz - La Paz', 211),
    (f'{PREFIX}TOR', 'El Torcal', 296),
    (f'{PREFIX}PRI', 'Princesa - Huelin', 390),
    (f'{PREFIX}ISL', 'La Isla', 474),
    (f'{PREFIX}PC2', 'El Perchel', 616),
    (f'{PREFIX}GD2', 'Guadalmedina', 743),  # ~12 min
]

# L2: Guadalmedina -> Palacio de Deportes (reverse)
STOP_TIMES_L2_DIR1 = [
    (f'{PREFIX}GD2', 'Guadalmedina', 0),
    (f'{PREFIX}PC2', 'El Perchel', 127),
    (f'{PREFIX}ISL', 'La Isla', 278),
    (f'{PREFIX}PRI', 'Princesa - Huelin', 361),
    (f'{PREFIX}TOR', 'El Torcal', 456),
    (f'{PREFIX}LZP', 'La Luz - La Paz', 541),
    (f'{PREFIX}PBL', 'Puerta Blanca', 627),
    (f'{PREFIX}PDD', 'Palacio de Deportes', 743),  # ~12 min
]

# Official frequencies from https://metromalaga.es/horarios/

# LUNES A JUEVES (06:30 - 23:00)
FREQUENCIES_LABORABLE = [
    (6*3600+30*60, 7*3600+30*60, 570),      # 06:30-07:30: cada 9'30"
    (7*3600+30*60, 9*3600+45*60, 320),      # 07:30-09:45: cada 5'20"
    (9*3600+45*60, 13*3600, 420),           # 09:45-13:00: cada 7'
    (13*3600, 15*3600, 320),                # 13:00-15:00: cada 5'20"
    (15*3600, 20*3600+30*60, 420),          # 15:00-20:30: cada 7'
    (20*3600+30*60, 23*3600, 570),          # 20:30-23:00: cada 9'30"
]

# VIERNES Y VÍSPERAS DE FESTIVO (06:30 - 01:30)
FREQUENCIES_VIERNES = [
    (6*3600+30*60, 7*3600+30*60, 570),      # 06:30-07:30: cada 9'30"
    (7*3600+30*60, 9*3600+45*60, 320),      # 07:30-09:45: cada 5'20"
    (9*3600+45*60, 13*3600, 420),           # 09:45-13:00: cada 7'
    (13*3600, 15*3600, 320),                # 13:00-15:00: cada 5'20"
    (15*3600, 20*3600+30*60, 420),          # 15:00-20:30: cada 7'
    (20*3600+30*60, 22*3600, 570),          # 20:30-22:00: cada 9'30"
    (22*3600, 25*3600+30*60, 720),          # 22:00-01:30: cada 12' (nocturno)
]

# SÁBADO (07:00 - 01:30)
FREQUENCIES_SABADO = [
    (7*3600, 9*3600+30*60, 720),            # 07:00-09:30: cada 12'
    (9*3600+30*60, 11*3600+45*60, 570),     # 09:30-11:45: cada 9'30"
    (11*3600+45*60, 14*3600, 495),          # 11:45-14:00: cada 8'15"
    (14*3600, 17*3600, 570),                # 14:00-17:00: cada 9'30"
    (17*3600, 22*3600, 495),                # 17:00-22:00: cada 8'15"
    (22*3600, 25*3600+30*60, 720),          # 22:00-01:30: cada 12' (nocturno)
]

# DOMINGO Y FESTIVOS (07:00 - 23:00)
FREQUENCIES_DOMINGO = [
    (7*3600, 9*3600+30*60, 720),            # 07:00-09:30: cada 12'
    (9*3600+30*60, 23*3600, 570),           # 09:30-23:00: cada 9'30"
]

# Festivos de Málaga 2026
FESTIVOS_2026 = [
    ('2026-01-01', 'Año Nuevo'),
    ('2026-01-06', 'Reyes'),
    ('2026-02-28', 'Día de Andalucía'),
    ('2026-04-02', 'Jueves Santo'),
    ('2026-04-03', 'Viernes Santo'),
    ('2026-05-01', 'Día del Trabajo'),
    ('2026-08-15', 'Asunción'),
    ('2026-08-19', 'Feria de Málaga'),  # Local
    ('2026-09-08', 'Virgen de la Victoria'),  # Local
    ('2026-10-12', 'Fiesta Nacional'),
    ('2026-11-01', 'Todos los Santos'),
    ('2026-12-06', 'Constitución'),
    ('2026-12-08', 'Inmaculada'),
    ('2026-12-25', 'Navidad'),
]

# Vísperas de festivo 2026 (activan servicio VIERNES con nocturno)
VISPERAS_2026 = [
    ('2025-12-31', 'Víspera Año Nuevo', 'wed'),
    ('2026-01-05', 'Víspera Reyes', 'mon'),
    ('2026-04-01', 'Víspera Jueves Santo', 'wed'),
    ('2026-04-30', 'Víspera 1 Mayo', 'thu'),
    ('2026-08-14', 'Víspera Asunción', 'fri'),       # Ya es viernes - skip
    ('2026-08-18', 'Víspera Feria', 'tue'),
    ('2026-09-07', 'Víspera Virgen Victoria', 'mon'),
    ('2026-10-11', 'Víspera Fiesta Nacional', 'sun'),
    ('2026-10-31', 'Víspera Todos Santos', 'sat'),   # Ya es sábado - skip
    ('2026-12-05', 'Víspera Constitución', 'sat'),   # Ya es sábado - skip
    ('2026-12-07', 'Víspera Inmaculada', 'mon'),
    ('2026-12-24', 'Víspera Navidad', 'thu'),
]


def seconds_to_time(secs: int) -> str:
    """Convert seconds since midnight to HH:MM:SS format."""
    hours = secs // 3600
    minutes = (secs % 3600) // 60
    seconds = secs % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def get_day_of_week(date_str: str) -> str:
    """Get day of week for a date string YYYY-MM-DD."""
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
    else:
        return SERVICE_DOMINGO


def generate_trips_for_line(
    line: int,
    service_id: str,
    frequencies: List[Tuple[int, int, int]],
    direction: int
) -> Tuple[List[Dict], List[Dict]]:
    """Generate trips and stop_times for a line/service/direction."""
    trips = []
    stop_times = []

    if line == 1:
        route_id = ROUTE_L1
        if direction == 0:
            stop_template = STOP_TIMES_L1_DIR0
            headsign = 'Atarazanas'
            shape_id = SHAPE_L1_TCH_ATZ
        else:
            stop_template = STOP_TIMES_L1_DIR1
            headsign = 'Andalucía Tech'
            shape_id = SHAPE_L1_ATZ_TCH
    else:  # L2
        route_id = ROUTE_L2
        if direction == 0:
            stop_template = STOP_TIMES_L2_DIR0
            headsign = 'Guadalmedina'
            shape_id = SHAPE_L2_PDD_GD2
        else:
            stop_template = STOP_TIMES_L2_DIR1
            headsign = 'Palacio de Deportes'
            shape_id = SHAPE_L2_GD2_PDD

    trip_num = 0

    for start_secs, end_secs, headway_secs in frequencies:
        current_time = start_secs

        while current_time < end_secs:
            trip_num += 1
            trip_id = f"{service_id}_L{line}_D{direction}_{trip_num:04d}"

            trips.append({
                'id': trip_id,
                'route_id': route_id,
                'service_id': service_id,
                'headsign': headsign,
                'short_name': None,
                'direction_id': direction,
                'block_id': None,
                'shape_id': shape_id,
                'wheelchair_accessible': 1,
                'bikes_allowed': 1,
            })

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
    """Generate all trips and stop_times for all services and lines."""
    all_trips = []
    all_stop_times = []

    services = [
        (SERVICE_LABORABLE, FREQUENCIES_LABORABLE),
        (SERVICE_VIERNES, FREQUENCIES_VIERNES),
        (SERVICE_SABADO, FREQUENCIES_SABADO),
        (SERVICE_DOMINGO, FREQUENCIES_DOMINGO),
    ]

    for service_id, frequencies in services:
        # L1 both directions
        for direction in [0, 1]:
            trips, stop_times = generate_trips_for_line(1, service_id, frequencies, direction)
            all_trips.extend(trips)
            all_stop_times.extend(stop_times)

        # L2 both directions
        for direction in [0, 1]:
            trips, stop_times = generate_trips_for_line(2, service_id, frequencies, direction)
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

    db.execute(text("DELETE FROM gtfs_calendar WHERE service_id LIKE 'METRO_MALAGA_%'"))

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
        db.execute(text("DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_MALAGA_%'"))

    # Festivos: add DOMINGO service, remove normal day service
    for fecha, nombre in FESTIVOS_2026:
        day = get_day_of_week(fecha)
        normal_service = get_normal_service_for_day(day)

        if dry_run:
            logger.info(f"  [DRY-RUN] Festivo {fecha} ({nombre}): +DOMINGO, -{normal_service}")
        else:
            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :fecha, 1)
            '''), {'service_id': SERVICE_DOMINGO, 'fecha': fecha})

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
        if day in ['fri', 'sat']:
            continue

        normal_service = get_normal_service_for_day(day)

        if dry_run:
            logger.info(f"  [DRY-RUN] Víspera {fecha} ({nombre}): +VIERNES, -{normal_service}")
        else:
            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :fecha, 1)
            '''), {'service_id': SERVICE_VIERNES, 'fecha': fecha})

            db.execute(text('''
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :fecha, 2)
            '''), {'service_id': normal_service, 'fecha': fecha})
            count += 2

    if not dry_run:
        db.commit()

    logger.info(f"  Total calendar_dates: {count}")
    return count


def clear_metro_malaga_data(db):
    """Clear existing Metro Málaga trips and stop_times."""
    logger.info("Clearing existing Metro Málaga schedule data...")

    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id IN (
            SELECT id FROM gtfs_trips WHERE route_id LIKE 'METRO_MALAGA_%'
        )
    """))
    db.commit()
    logger.info(f"  Cleared {result.rowcount} stop_times")

    result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id LIKE 'METRO_MALAGA_%'"
    ))
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


def verify_routes_exist(db) -> bool:
    """Verify Metro Málaga routes exist."""
    routes = db.execute(text(
        "SELECT id FROM gtfs_routes WHERE id LIKE 'METRO_MALAGA_%'"
    )).fetchall()

    logger.info(f"Found {len(routes)} METRO_MALAGA routes")
    return len(routes) >= 2


def verify_stops_exist(db) -> bool:
    """Verify Metro Málaga stops exist."""
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_stops WHERE id LIKE 'METRO_MALAGA_%'"
    )).scalar()

    logger.info(f"Found {result} METRO_MALAGA stops")
    return result >= 17  # At least 17 unique station stops


def analyze():
    """Analyze and show expansion estimates."""
    print("\n" + "=" * 70)
    print("METRO MÁLAGA - FREQUENCY EXPANSION ANALYSIS")
    print("=" * 70)

    all_trips, all_stop_times = generate_all_trips()

    print(f"\nTotal trips to generate: {len(all_trips):,}")
    print(f"Total stop_times to generate: {len(all_stop_times):,}")

    print("\n" + "-" * 70)
    print("TRIPS BY SERVICE")
    print("-" * 70)

    by_service = {}
    for trip in all_trips:
        sid = trip['service_id']
        by_service[sid] = by_service.get(sid, 0) + 1

    for sid in sorted(by_service.keys()):
        print(f"  {sid}: {by_service[sid]:,} trips")

    print("\n" + "-" * 70)
    print("TRIPS BY LINE")
    print("-" * 70)

    l1 = sum(1 for t in all_trips if 'L1' in t['id'])
    l2 = sum(1 for t in all_trips if 'L2' in t['id'])
    print(f"  Línea 1 (TCH-ATZ): {l1:,}")
    print(f"  Línea 2 (PDD-GD2): {l2:,}")

    print("\n" + "-" * 70)
    print("FESTIVOS 2026")
    print("-" * 70)

    for fecha, nombre in FESTIVOS_2026:
        day = get_day_of_week(fecha)
        print(f"  {fecha} ({day}): {nombre}")

    print("\n" + "-" * 70)
    print("VÍSPERAS 2026 (with nocturnal service)")
    print("-" * 70)

    for fecha, nombre, day in VISPERAS_2026:
        skip = " (skip - already nocturnal)" if day in ['fri', 'sat'] else ""
        print(f"  {fecha} ({day}): {nombre}{skip}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Import Metro Málaga GTFS data based on official frequencies'
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

    logger.info("Generating trips from official frequencies...")
    all_trips, all_stop_times = generate_all_trips()
    logger.info(f"Generated {len(all_trips):,} trips and {len(all_stop_times):,} stop_times")

    db = SessionLocal()

    try:
        start_time = datetime.now()

        if not verify_routes_exist(db):
            logger.error("Metro Málaga routes not found!")
            sys.exit(1)

        if not verify_stops_exist(db):
            logger.error("Metro Málaga stops not found!")
            sys.exit(1)

        clear_metro_malaga_data(db)

        calendar_count = create_calendars(db, False)
        logger.info(f"Created {calendar_count} calendars")

        calendar_dates_count = create_calendar_dates(db, False)
        logger.info(f"Created {calendar_dates_count} calendar_dates")

        trips_count = import_trips(db, all_trips)
        logger.info(f"Imported {trips_count:,} trips")

        stop_times_count = import_stop_times(db, all_stop_times)
        logger.info(f"Imported {stop_times_count:,} stop_times")

        elapsed = datetime.now() - start_time

        print("\n" + "=" * 70)
        print("IMPORT SUMMARY - Metro de Málaga")
        print("=" * 70)
        print(f"Calendars: {calendar_count}")
        print(f"Calendar dates: {calendar_dates_count}")
        print(f"Trips: {trips_count:,}")
        print(f"Stop times: {stop_times_count:,}")
        print(f"Elapsed time: {elapsed}")
        print("=" * 70)
        print("\nMetro Málaga import completed successfully!")

    except Exception as e:
        db.rollback()
        logger.error(f"Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
