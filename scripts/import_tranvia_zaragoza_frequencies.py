#!/usr/bin/env python3
"""Import Tranvía Zaragoza GTFS data based on official frequencies.

This script generates trips from official frequency data from:
https://www.tranviasdezaragoza.es/el-tranvia-circulara-en-horario-de-invierno-desde-el-9-de-septiembre/

Instead of using the NAP GTFS (which has some frequency discrepancies),
this script creates trips based on the official published frequencies.

Services:
- LABORABLE: Monday-Friday, 05:00-00:00
- SABADO: Saturday, 05:00-00:00
- DOMINGO_FESTIVO: Sunday + holidays, 05:00-00:00

Usage:
    python scripts/import_tranvia_zaragoza_frequencies.py [--dry-run]
    python scripts/import_tranvia_zaragoza_frequencies.py --analyze

GTFS Source: Official frequencies from tranviasdezaragoza.es
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

# Tranvía Zaragoza configuration
TRANVIA_ZARAGOZA_ROUTE_ID = 'TRANVIA_ZARAGOZA_210'
PREFIX = 'TRANVIA_ZARAGOZA_'

# Shape IDs
SHAPE_ID_PG_MO = f'{PREFIX}210_I'  # Parque Goya -> Mago de Oz (direction 0)
SHAPE_ID_MO_PG = f'{PREFIX}210_V'  # Mago de Oz -> Parque Goya (direction 1)

# Service IDs
SERVICE_LABORABLE = f'{PREFIX}LABORABLE'
SERVICE_SABADO = f'{PREFIX}SABADO'
SERVICE_DOMINGO_FESTIVO = f'{PREFIX}DOMINGO_FESTIVO'

# Travel times from each stop (in seconds) - Direction 0: Avenida Academia -> Mago de Oz
# Extracted from existing NAP GTFS data
STOP_TIMES_DIR0 = [
    (f'{PREFIX}0101', 'Avenida de la Academia', 0),
    (f'{PREFIX}0201', 'Parque Goya', 115),
    (f'{PREFIX}0301', 'Juslibol', 182),
    (f'{PREFIX}0401', 'Campus Río Ebro', 296),
    (f'{PREFIX}0501', 'Margarita Xirgu', 424),
    (f'{PREFIX}0601', 'Legaz Lacambra', 486),
    (f'{PREFIX}0701', 'Clara Campoamor', 580),
    (f'{PREFIX}0801', 'Rosalía de Castro', 655),
    (f'{PREFIX}0901', 'Martínez Soria', 735),
    (f'{PREFIX}1001', 'La Chimenea', 815),
    (f'{PREFIX}1101', 'Plaza del Pilar - Murallas', 914),
    (f'{PREFIX}1201', 'César Augusto', 987),
    (f'{PREFIX}1301', 'Plaza España', 1147),
    (f'{PREFIX}1311', 'Plaza Aragón', 1260),
    (f'{PREFIX}1401', 'Gran Vía', 1345),
    (f'{PREFIX}1501', 'Fernando El Católico - Goya', 1435),
    (f'{PREFIX}1601', 'Plaza San Francisco', 1520),
    (f'{PREFIX}1701', 'Emperador Carlos V', 1600),
    (f'{PREFIX}1801', 'Romareda', 1690),
    (f'{PREFIX}1901', 'Casablanca', 1780),
    (f'{PREFIX}2001', 'Argualas', 1880),
    (f'{PREFIX}2101', 'Paseo de Los Olvidados', 2035),
    (f'{PREFIX}2301', 'Los Pájaros', 2155),
    (f'{PREFIX}2401', 'Cantando bajo la lluvia', 2240),
    (f'{PREFIX}2501', 'Mago de Oz', 2320),  # ~39 minutes
]

# Travel times - Direction 1: Mago de Oz -> Avenida Academia
STOP_TIMES_DIR1 = [
    (f'{PREFIX}2502', 'Mago de Oz', 0),
    (f'{PREFIX}2422', 'Un americano en París', 85),
    (f'{PREFIX}2322', 'La ventana indiscreta', 180),
    (f'{PREFIX}2102', 'Paseo de Los Olvidados', 300),
    (f'{PREFIX}2002', 'Argualas', 460),
    (f'{PREFIX}1902', 'Casablanca', 545),
    (f'{PREFIX}1802', 'Romareda', 650),
    (f'{PREFIX}1702', 'Emperador Carlos V', 735),
    (f'{PREFIX}1602', 'Plaza San Francisco', 820),
    (f'{PREFIX}1502', 'Fernando El Católico - Goya', 915),
    (f'{PREFIX}1402', 'Gran Vía', 1010),
    (f'{PREFIX}1312', 'Plaza Aragón', 1110),
    (f'{PREFIX}1302', 'Plaza España', 1229),
    (f'{PREFIX}1202', 'César Augusto', 1368),
    (f'{PREFIX}1102', 'Plaza del Pilar - Murallas', 1441),
    (f'{PREFIX}1002', 'La chimenea', 1541),
    (f'{PREFIX}0902', 'María Montessori', 1621),
    (f'{PREFIX}0802', 'León Felipe', 1708),
    (f'{PREFIX}0702', 'Pablo Neruda', 1774),
    (f'{PREFIX}0602', 'Adolfo Aznar', 1865),
    (f'{PREFIX}0502', 'García Abril', 1924),
    (f'{PREFIX}0402', 'Campus Río Ebro', 2050),
    (f'{PREFIX}0302', 'Juslibol', 2150),
    (f'{PREFIX}0202', 'Parque Goya', 2223),
    (f'{PREFIX}0102', 'Avenida de la Academia', 2318),  # ~39 minutes
]

# Official frequencies from https://www.tranviasdezaragoza.es
# Winter schedule (Horario de Invierno) - from September 9
# Format: (start_seconds, end_seconds, headway_seconds)

FREQUENCIES_LABORABLE = [
    (5*3600,        7*3600+30*60,  20*60),    # 05:00-07:30: cada 20'
    (7*3600+30*60,  9*3600,        5*60),     # 07:30-09:00: cada 5'
    (9*3600,        10*3600,       5*60),     # 09:00-10:00: cada 5'
    (10*3600,       13*3600+30*60, 7*60),     # 10:00-13:30: cada 7'
    (13*3600+30*60, 17*3600,       6*60),     # 13:30-17:00: cada 6'
    (17*3600,       17*3600+30*60, 5*60),     # 17:00-17:30: cada 5'
    (17*3600+30*60, 18*3600+30*60, 5*60),     # 17:30-18:30: cada 5'
    (18*3600+30*60, 20*3600,       5*60),     # 18:30-20:00: cada 5'
    (20*3600,       21*3600,       7*60),     # 20:00-21:00: cada 7'
    (21*3600,       22*3600,       7*60),     # 21:00-22:00: cada 7'
    (22*3600,       22*3600+30*60, 15*60),    # 22:00-22:30: cada 15'
    (22*3600+30*60, 24*3600+45*60, 15*60),    # 22:30-00:45: cada 15'
]

FREQUENCIES_SABADO = [
    (5*3600,        7*3600+30*60,  20*60),    # 05:00-07:30: cada 20'
    (7*3600+30*60,  9*3600,        20*60),    # 07:30-09:00: cada 20'
    (9*3600,        10*3600,       10*60),    # 09:00-10:00: cada 10'
    (10*3600,       13*3600+30*60, 10*60),    # 10:00-13:30: cada 10'
    (13*3600+30*60, 17*3600,       10*60),    # 13:30-17:00: cada 10'
    (17*3600,       17*3600+30*60, 10*60),    # 17:00-17:30: cada 10'
    (17*3600+30*60, 18*3600+30*60, 10*60),    # 17:30-18:30: cada 10'
    (18*3600+30*60, 20*3600,       8*60),     # 18:30-20:00: cada 8'
    (20*3600,       21*3600,       8*60),     # 20:00-21:00: cada 8'
    (21*3600,       22*3600,       8*60),     # 21:00-22:00: cada 8'
    (22*3600,       22*3600+30*60, 8*60),     # 22:00-22:30: cada 8'
    (22*3600+30*60, 24*3600+45*60, 15*60),    # 22:30-00:45: cada 15'
]

FREQUENCIES_DOMINGO_FESTIVO = [
    (5*3600,        7*3600+30*60,  20*60),    # 05:00-07:30: cada 20'
    (7*3600+30*60,  9*3600,        20*60),    # 07:30-09:00: cada 20'
    (9*3600,        10*3600,       15*60),    # 09:00-10:00: cada 15'
    (10*3600,       13*3600+30*60, 15*60),    # 10:00-13:30: cada 15'
    (13*3600+30*60, 17*3600,       15*60),    # 13:30-17:00: cada 15'
    (17*3600,       17*3600+30*60, 12*60),    # 17:00-17:30: cada 12'
    (17*3600+30*60, 18*3600+30*60, 12*60),    # 17:30-18:30: cada 12'
    (18*3600+30*60, 20*3600,       12*60),    # 18:30-20:00: cada 12'
    (20*3600,       21*3600,       12*60),    # 20:00-21:00: cada 12'
    (21*3600,       22*3600,       15*60),    # 21:00-22:00: cada 15'
    (22*3600,       22*3600+30*60, 15*60),    # 22:00-22:30: cada 15'
    (22*3600+30*60, 24*3600+45*60, 15*60),    # 22:30-00:45: cada 15'
]

# Festivos de Zaragoza 2026
# Fuente: BOE + Gobierno de Aragón + Ayuntamiento de Zaragoza
FESTIVOS_2026 = [
    ('2026-01-01', 'Año Nuevo'),
    ('2026-01-06', 'Epifanía del Señor'),
    ('2026-04-02', 'Jueves Santo'),
    ('2026-04-03', 'Viernes Santo'),
    ('2026-04-23', 'San Jorge - Día de Aragón'),
    ('2026-05-01', 'Día del Trabajo'),
    ('2026-06-04', 'Corpus Christi'),  # Fiesta local Zaragoza (movible)
    ('2026-08-15', 'Asunción de la Virgen'),
    ('2026-10-12', 'Fiesta Nacional de España / Pilar'),
    ('2026-11-02', 'Todos los Santos (traslado)'),  # Si cae en domingo
    ('2026-12-08', 'Inmaculada Concepción'),
    ('2026-12-25', 'Navidad'),
    # Fiestas del Pilar - octubre (servicio especial, pero algunos días festivos)
    ('2026-10-13', 'Fiestas del Pilar'),
]

# Calendar start/end dates
CALENDAR_START = '2026-01-01'
CALENDAR_END = '2026-12-31'


def time_to_str(seconds: int) -> str:
    """Convert seconds since midnight to HH:MM:SS format."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def generate_trips_for_service(
    service_id: str,
    frequencies: List[Tuple[int, int, int]],
    direction: int,
    stop_times: List[Tuple[str, str, int]]
) -> Tuple[List[Dict], List[Dict]]:
    """Generate trips and stop_times for a service type."""
    trips = []
    all_stop_times = []

    shape_id = SHAPE_ID_PG_MO if direction == 0 else SHAPE_ID_MO_PG
    headsign = 'Mago de Oz' if direction == 0 else 'Parque Goya'

    trip_num = 0
    for start_secs, end_secs, headway in frequencies:
        current_time = start_secs
        while current_time < end_secs:
            trip_num += 1
            trip_id = f"{service_id}_D{direction}_{trip_num:03d}"

            trips.append({
                'id': trip_id,
                'route_id': TRANVIA_ZARAGOZA_ROUTE_ID,
                'service_id': service_id,
                'headsign': headsign,
                'short_name': None,
                'direction_id': direction,
                'block_id': None,
                'shape_id': shape_id,
                'wheelchair_accessible': 1,
                'bikes_allowed': None,
            })

            # Generate stop_times
            for seq, (stop_id, stop_name, offset_secs) in enumerate(stop_times, 1):
                arr_secs = current_time + offset_secs
                dep_secs = arr_secs

                all_stop_times.append({
                    'trip_id': trip_id,
                    'stop_sequence': seq,
                    'stop_id': stop_id,
                    'arrival_time': time_to_str(arr_secs),
                    'departure_time': time_to_str(dep_secs),
                    'arrival_seconds': arr_secs,
                    'departure_seconds': dep_secs,
                    'stop_headsign': None,
                    'pickup_type': 0,
                    'drop_off_type': 0,
                    'shape_dist_traveled': None,
                    'timepoint': 1,
                })

            current_time += headway

    return trips, all_stop_times


def clear_existing_data(db):
    """Clear existing Tranvía Zaragoza schedule data (trips, stop_times, calendars)."""
    logger.info("Clearing existing Tranvía Zaragoza schedule data...")

    # Delete stop_times
    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id IN (
            SELECT id FROM gtfs_trips WHERE route_id = :rid
        )
    """), {'rid': TRANVIA_ZARAGOZA_ROUTE_ID})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id = :rid"
    ), {'rid': TRANVIA_ZARAGOZA_ROUTE_ID})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} trips")

    # Delete calendar_dates for our service IDs
    result = db.execute(text(
        "DELETE FROM gtfs_calendar_dates WHERE service_id LIKE :pattern"
    ), {'pattern': f'{PREFIX}%'})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} calendar_dates")

    # Delete calendars
    result = db.execute(text(
        "DELETE FROM gtfs_calendar WHERE service_id LIKE :pattern"
    ), {'pattern': f'{PREFIX}%'})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} calendar entries")


def import_calendars(db) -> int:
    """Import calendar entries for each service type."""
    logger.info("Importing calendar entries...")

    calendars = [
        {
            'service_id': SERVICE_LABORABLE,
            'monday': True,
            'tuesday': True,
            'wednesday': True,
            'thursday': True,
            'friday': True,
            'saturday': False,
            'sunday': False,
            'start_date': CALENDAR_START,
            'end_date': CALENDAR_END,
        },
        {
            'service_id': SERVICE_SABADO,
            'monday': False,
            'tuesday': False,
            'wednesday': False,
            'thursday': False,
            'friday': False,
            'saturday': True,
            'sunday': False,
            'start_date': CALENDAR_START,
            'end_date': CALENDAR_END,
        },
        {
            'service_id': SERVICE_DOMINGO_FESTIVO,
            'monday': False,
            'tuesday': False,
            'wednesday': False,
            'thursday': False,
            'friday': False,
            'saturday': False,
            'sunday': True,
            'start_date': CALENDAR_START,
            'end_date': CALENDAR_END,
        },
    ]

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

    return len(calendars)


def import_calendar_dates(db) -> int:
    """Import calendar_dates for holidays (exception_type=1 to add DOMINGO_FESTIVO service)."""
    logger.info("Importing calendar_dates for holidays...")

    calendar_dates = []

    for date_str, desc in FESTIVOS_2026:
        # On holidays, use DOMINGO_FESTIVO schedule
        calendar_dates.append({
            'service_id': SERVICE_DOMINGO_FESTIVO,
            'date': date_str,
            'exception_type': 1,  # Service added
        })
        # Remove LABORABLE and SABADO on holidays
        calendar_dates.append({
            'service_id': SERVICE_LABORABLE,
            'date': date_str,
            'exception_type': 2,  # Service removed
        })
        calendar_dates.append({
            'service_id': SERVICE_SABADO,
            'date': date_str,
            'exception_type': 2,  # Service removed
        })

    if calendar_dates:
        db.execute(
            text("""
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :date, :exception_type)
                ON CONFLICT (service_id, date) DO UPDATE SET
                    exception_type = EXCLUDED.exception_type
            """),
            calendar_dates
        )
        db.commit()

    return len(calendar_dates)


def import_trips_and_stop_times(db) -> Tuple[int, int]:
    """Generate and import all trips and stop_times."""
    all_trips = []
    all_stop_times = []

    # Generate for each service type and direction
    services = [
        (SERVICE_LABORABLE, FREQUENCIES_LABORABLE),
        (SERVICE_SABADO, FREQUENCIES_SABADO),
        (SERVICE_DOMINGO_FESTIVO, FREQUENCIES_DOMINGO_FESTIVO),
    ]

    for service_id, frequencies in services:
        # Direction 0: Parque Goya -> Mago de Oz
        trips, stop_times = generate_trips_for_service(
            service_id, frequencies, 0, STOP_TIMES_DIR0
        )
        all_trips.extend(trips)
        all_stop_times.extend(stop_times)

        # Direction 1: Mago de Oz -> Parque Goya
        trips, stop_times = generate_trips_for_service(
            service_id, frequencies, 1, STOP_TIMES_DIR1
        )
        all_trips.extend(trips)
        all_stop_times.extend(stop_times)

    logger.info(f"Generated {len(all_trips)} trips and {len(all_stop_times)} stop_times")

    # Insert trips
    logger.info("Inserting trips...")
    for i in range(0, len(all_trips), BATCH_SIZE):
        batch = all_trips[i:i+BATCH_SIZE]
        db.execute(
            text("""
                INSERT INTO gtfs_trips
                (id, route_id, service_id, headsign, short_name, direction_id, block_id, shape_id, wheelchair_accessible, bikes_allowed)
                VALUES (:id, :route_id, :service_id, :headsign, :short_name, :direction_id, :block_id, :shape_id, :wheelchair_accessible, :bikes_allowed)
                ON CONFLICT (id) DO UPDATE SET
                    service_id = EXCLUDED.service_id,
                    headsign = EXCLUDED.headsign,
                    direction_id = EXCLUDED.direction_id,
                    shape_id = EXCLUDED.shape_id
            """),
            batch
        )
    db.commit()

    # Insert stop_times
    logger.info("Inserting stop_times...")
    for i in range(0, len(all_stop_times), BATCH_SIZE):
        batch = all_stop_times[i:i+BATCH_SIZE]
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
        if (i + BATCH_SIZE) % 10000 == 0:
            logger.info(f"  Inserted {min(i + BATCH_SIZE, len(all_stop_times))} stop_times...")
    db.commit()

    return len(all_trips), len(all_stop_times)


def analyze():
    """Analyze what would be generated without importing."""
    print("\n" + "=" * 70)
    print("TRANVÍA ZARAGOZA - FREQUENCY ANALYSIS")
    print("=" * 70)

    print("\n📍 Route: L1 Parque Goya ↔ Mago de Oz")
    print(f"   Stops: {len(STOP_TIMES_DIR0)} per direction")
    print(f"   Travel time: ~39 minutes")

    print("\n📅 Services:")
    for name, freqs in [
        ('LABORABLE (L-V)', FREQUENCIES_LABORABLE),
        ('SÁBADO', FREQUENCIES_SABADO),
        ('DOMINGO/FESTIVO', FREQUENCIES_DOMINGO_FESTIVO),
    ]:
        # Count trips
        trip_count = 0
        for start, end, headway in freqs:
            trips_in_slot = (end - start) // headway
            trip_count += trips_in_slot
        trip_count *= 2  # Both directions

        print(f"\n   {name}:")
        for start, end, headway in freqs:
            start_str = time_to_str(start)[:5]
            end_str = time_to_str(end)[:5]
            print(f"     {start_str}-{end_str}: cada {headway//60}' ", end="")
            trips_slot = (end - start) // headway
            print(f"({trips_slot * 2} trips)")
        print(f"   Total: ~{trip_count} trips")

    print(f"\n📆 Festivos 2026: {len(FESTIVOS_2026)}")
    for date_str, desc in FESTIVOS_2026[:5]:
        print(f"     {date_str}: {desc}")
    print(f"     ... y {len(FESTIVOS_2026) - 5} más")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Import Tranvía Zaragoza GTFS based on official frequencies'
    )
    parser.add_argument('--dry-run', action='store_true', help='Analyze only, no import')
    parser.add_argument('--analyze', action='store_true', help='Show frequency analysis')

    args = parser.parse_args()

    if args.analyze or args.dry_run:
        analyze()
        return

    db = SessionLocal()

    try:
        logger.info("=" * 60)
        logger.info("TRANVÍA ZARAGOZA - FREQUENCY-BASED IMPORT")
        logger.info("=" * 60)

        # Clear existing data
        clear_existing_data(db)

        # Import calendars
        calendar_count = import_calendars(db)
        logger.info(f"Imported {calendar_count} calendar entries")

        # Import calendar_dates (holidays)
        calendar_dates_count = import_calendar_dates(db)
        logger.info(f"Imported {calendar_dates_count} calendar_dates entries")

        # Import trips and stop_times
        trips_count, stop_times_count = import_trips_and_stop_times(db)

        # Summary
        print("\n" + "=" * 60)
        print("IMPORT SUMMARY - Tranvía de Zaragoza")
        print("=" * 60)
        print(f"Calendar entries: {calendar_count}")
        print(f"Calendar dates (holidays): {calendar_dates_count}")
        print(f"Trips: {trips_count}")
        print(f"Stop times: {stop_times_count}")
        print("=" * 60)
        print("\n✅ Tranvía Zaragoza frequency-based import completed!")
        print("\nNext steps:")
        print("  1. Deploy to production: make deploy")
        print("  2. Run on production: python scripts/import_tranvia_zaragoza_frequencies.py")
        print("  3. Restart server: systemctl restart renfeserver")
        print("  4. Test: curl 'https://redcercanias.com/api/v1/gtfs/stops/TRANVIA_ZARAGOZA_1301/departures?limit=5'")

    except Exception as e:
        db.rollback()
        logger.error(f"Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
