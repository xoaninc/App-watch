#!/usr/bin/env python3
"""Import SFM Mallorca GTFS data from NAP (trains only).

This script imports GTFS data for Serveis Ferroviaris de Mallorca (SFM) trains:
- M1: Metro Palma ↔ UIB/ParcBit (route 216)
- T1: Tren Palma ↔ Inca (route 218)
- T2: Tren Palma ↔ Sa Pobla (route 219)
- T3: Tren Palma ↔ Manacor (route 220)

The NAP GTFS contains mixed bus+train data. This script:
1. Filters only train routes (216, 218, 219, 220)
2. Imports trips, stop_times, calendar, calendar_dates from NAP
3. Keeps existing shapes in BD (better quality than NAP)
4. Adds manual festivos for Baleares/Palma 2026

Service patterns:
- M1: L-V + Sábado (NO opera domingos/festivos)
- T1: Solo L-V (NO opera sábados/domingos/festivos)
- T2: L-V + S-D (opera todos los días)
- T3: L-V + S-D (opera todos los días)

Usage:
    python scripts/import_sfm_mallorca_gtfs.py [--dry-run] [--analyze]

GTFS Source: NAP (Punto de Acceso Nacional) - Fichero ID 1272
Download: curl -X GET "https://nap.transportes.gob.es/api/Fichero/download/1272" \
          -H "ApiKey: YOUR_API_KEY" -o data/gtfs_sfm_mallorca.zip
"""

import os
import sys
import csv
import argparse
import logging
from datetime import datetime, date
from typing import Dict, List, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Path to GTFS files
GTFS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'gtfs_sfm_mallorca')

# ID prefix for SFM Mallorca
PREFIX = 'SFM_MALLORCA_'

# Train routes to import (filter from mixed bus+train GTFS)
TRAIN_ROUTES = {
    '216': 'M1',  # Metro Palma-UIB
    '218': 'T1',  # Tren Palma-Inca
    '219': 'T2',  # Tren Palma-Sa Pobla
    '220': 'T3',  # Tren Palma-Manacor
}

# Shape ID mapping: NAP shape_id -> BD shape_id
# NAP uses generic IDs, BD has descriptive IDs
SHAPE_MAPPING = {
    # M1 shapes
    'M1-1_SHP': 'M1-1_SHP',  # M1 direction 0 (Palma->ParcBit)
    'M1-2_SHP': 'M1-2_SHP',  # M1 direction 1 (ParcBit->Palma)
    # T1 shapes
    'T1-1_SHP': 'T1-1_SHP',  # T1 direction 0 (Palma->Inca)
    'T1-2_SHP': 'T1-2_SHP',  # T1 direction 1 (Inca->Palma)
    # T2 shapes
    'T2-1_SHP': 'T2-1_SHP',  # T2 direction 0 (Palma->Sa Pobla)
    'T2-2_SHP': 'T2-2_SHP',  # T2 direction 1 (Sa Pobla->Palma)
    # T3 shapes
    'T3-1_SHP': 'T3-1_SHP',  # T3 direction 0 (Palma->Manacor)
    'T3-2_SHP': 'T3-2_SHP',  # T3 direction 1 (Manacor->Palma)
}

# Service IDs by line and type (from NAP calendar.txt)
# Format: line -> (L-V service_ids, Sáb service_ids, S-D service_ids)
SERVICE_IDS = {
    'M1': {
        'LV': ['M1-1_260705', 'M1-2_260708'],           # L-V
        'SAB': ['M1-1_260706', 'M1-2_260748'],          # Sábado
        'SD': [],                                        # No opera dom/festivos
    },
    'T1': {
        'LV': ['T1-1_261507', 'T1-2_261508'],           # L-V
        'SAB': [],                                       # No opera sábados
        'SD': [],                                        # No opera dom/festivos
    },
    'T2': {
        'LV': ['T2-1_261509', 'T2-2_261511'],           # L-V
        'SAB': [],                                       # Included in SD
        'SD': ['T2-1_261510', 'T2-2_261512'],           # S-D (includes sábado)
    },
    'T3': {
        'LV': ['T3-1_261513', 'T3-2_261515'],           # L-V
        'SAB': [],                                       # Included in SD
        'SD': ['T3-1_261514', 'T3-2_261516'],           # S-D (includes sábado)
    },
}

# Festivos Baleares/Palma 2026 (only those falling on L-V)
# Source: BOE, BOIB, official calendars
FESTIVOS_2026 = [
    ('2026-01-01', 'Año Nuevo'),
    ('2026-01-06', 'Reyes'),
    ('2026-01-20', 'Sant Sebastià (Palma)'),
    ('2026-03-02', 'Día de Baleares'),  # Already in NAP for T2/T3
    ('2026-04-02', 'Jueves Santo'),
    ('2026-04-03', 'Viernes Santo'),
    ('2026-05-01', 'Día del Trabajo'),
    ('2026-06-29', 'San Pere (Palma)'),
    ('2026-10-12', 'Fiesta Nacional'),
    ('2026-12-08', 'Inmaculada'),
    ('2026-12-25', 'Navidad'),
]

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


def get_train_service_ids() -> Set[str]:
    """Get all service_ids used by train routes."""
    trips = load_csv('trips.txt')
    service_ids = set()

    for trip in trips:
        route_id = trip['route_id'].strip()
        if route_id in TRAIN_ROUTES:
            service_ids.add(trip['service_id'].strip())

    return service_ids


def clear_existing_data(db, dry_run: bool = False) -> Dict[str, int]:
    """Clear existing SFM Mallorca train data (preserve shapes)."""
    logger.info("Paso 1: Limpiando datos existentes de SFM Mallorca (trenes)...")

    counts = {}

    if dry_run:
        counts['stop_times'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'SFM_MALLORCA_%'"
        )).scalar()
        counts['trips'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_trips WHERE route_id LIKE 'SFM_MALLORCA_%'"
        )).scalar()
        counts['calendar_dates'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_calendar_dates WHERE service_id LIKE 'SFM_MALLORCA_%'"
        )).scalar()
        counts['calendars'] = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'SFM_MALLORCA_%'"
        )).scalar()

        for key, count in counts.items():
            logger.info(f"  [DRY-RUN] Se borrarían {count} {key}")
        logger.info("  [DRY-RUN] Shapes se mantienen (no se borran)")
        return counts

    # Delete stop_times first (FK constraint)
    result = db.execute(text(
        "DELETE FROM gtfs_stop_times WHERE trip_id LIKE 'SFM_MALLORCA_%'"
    ))
    counts['stop_times'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id LIKE 'SFM_MALLORCA_%'"
    ))
    counts['trips'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} trips")

    # Delete calendar_dates
    result = db.execute(text(
        "DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'SFM_MALLORCA_%'"
    ))
    counts['calendar_dates'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} calendar_dates")

    # Delete calendars
    result = db.execute(text(
        "DELETE FROM gtfs_calendar WHERE service_id LIKE 'SFM_MALLORCA_%'"
    ))
    counts['calendars'] = result.rowcount
    logger.info(f"  Borrados {result.rowcount} calendars")

    # NOTE: Shapes are NOT deleted - we keep existing BD shapes
    logger.info("  Shapes se mantienen (mejor calidad que NAP)")

    db.commit()
    return counts


def import_calendar(db, dry_run: bool = False) -> int:
    """Import calendar.txt (only train service_ids)."""
    logger.info("Paso 2: Importando calendarios (solo trenes)...")

    rows = load_csv('calendar.txt')
    train_service_ids = get_train_service_ids()

    if not rows:
        logger.warning("  No se encontró calendar.txt")
        return 0

    calendars = []
    for row in rows:
        service_id = row['service_id'].strip()

        # Only import train service_ids
        if service_id not in train_service_ids:
            continue

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
        for cal in calendars:
            days = []
            if cal['monday']: days.append('L')
            if cal['tuesday']: days.append('M')
            if cal['wednesday']: days.append('X')
            if cal['thursday']: days.append('J')
            if cal['friday']: days.append('V')
            if cal['saturday']: days.append('S')
            if cal['sunday']: days.append('D')
            logger.info(f"    {cal['service_id'].replace(PREFIX, '')}: {'-'.join(days)} ({cal['start_date']} → {cal['end_date']})")
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
    """Import calendar_dates.txt + manual festivos."""
    logger.info("Paso 3: Importando calendar_dates + festivos manuales...")

    rows = load_csv('calendar_dates.txt')
    train_service_ids = get_train_service_ids()

    calendar_dates = []

    # Import existing calendar_dates from NAP (only for trains)
    nap_count = 0
    for row in rows:
        service_id = row['service_id'].strip()

        # Only import train service_ids
        if service_id not in train_service_ids:
            continue

        our_service_id = f"{PREFIX}{service_id}"

        calendar_dates.append({
            'service_id': our_service_id,
            'date': parse_date(row['date'].strip()),
            'exception_type': int(row['exception_type'].strip()),
        })
        nap_count += 1

    logger.info(f"  Calendar_dates del NAP: {nap_count}")

    # Add manual festivos
    festivos_added = add_festivos(calendar_dates, train_service_ids)
    logger.info(f"  Festivos añadidos manualmente: {festivos_added}")

    if dry_run:
        logger.info(f"  [DRY-RUN] Se importarían {len(calendar_dates)} calendar_dates en total")
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


def add_festivos(calendar_dates: List[Dict], train_service_ids: Set[str]) -> int:
    """Add manual festivos for Baleares/Palma 2026.

    For each festivo:
    - M1: exception_type=2 for L-V and Sáb service_ids (no service)
    - T1: exception_type=2 for L-V service_ids (no service)
    - T2/T3: exception_type=2 for L-V, exception_type=1 for S-D

    Returns number of festivos added.
    """
    added = 0
    existing_dates = {(cd['service_id'], cd['date']) for cd in calendar_dates}

    for festivo_date, festivo_name in FESTIVOS_2026:
        logger.info(f"    Procesando festivo: {festivo_date} ({festivo_name})")

        for line, services in SERVICE_IDS.items():
            # M1: No opera dom/festivos - quitar L-V y Sáb
            if line == 'M1':
                for sid in services['LV'] + services['SAB']:
                    if sid in train_service_ids:
                        key = (f"{PREFIX}{sid}", festivo_date)
                        if key not in existing_dates:
                            calendar_dates.append({
                                'service_id': f"{PREFIX}{sid}",
                                'date': festivo_date,
                                'exception_type': 2,  # No opera
                            })
                            existing_dates.add(key)
                            added += 1

            # T1: No opera sáb/dom/festivos - quitar L-V
            elif line == 'T1':
                for sid in services['LV']:
                    if sid in train_service_ids:
                        key = (f"{PREFIX}{sid}", festivo_date)
                        if key not in existing_dates:
                            calendar_dates.append({
                                'service_id': f"{PREFIX}{sid}",
                                'date': festivo_date,
                                'exception_type': 2,  # No opera
                            })
                            existing_dates.add(key)
                            added += 1

            # T2, T3: Usa horario S-D en festivos
            elif line in ('T2', 'T3'):
                # Quitar servicio L-V
                for sid in services['LV']:
                    if sid in train_service_ids:
                        key = (f"{PREFIX}{sid}", festivo_date)
                        if key not in existing_dates:
                            calendar_dates.append({
                                'service_id': f"{PREFIX}{sid}",
                                'date': festivo_date,
                                'exception_type': 2,  # No opera L-V
                            })
                            existing_dates.add(key)
                            added += 1

                # Añadir servicio S-D
                for sid in services['SD']:
                    if sid in train_service_ids:
                        key = (f"{PREFIX}{sid}", festivo_date)
                        if key not in existing_dates:
                            calendar_dates.append({
                                'service_id': f"{PREFIX}{sid}",
                                'date': festivo_date,
                                'exception_type': 1,  # Añadir S-D
                            })
                            existing_dates.add(key)
                            added += 1

    return added


def get_shape_id_for_trip(nap_shape_id: str, route_id: str, direction_id: int) -> str:
    """Map NAP shape_id to BD shape_id based on route and direction.

    NAP uses generic shape_ids like 'M1-1_SHP'.
    We map them to our BD shape_ids which are the same format.
    """
    line = TRAIN_ROUTES.get(route_id, '')
    if not line:
        return None

    # Construct shape_id: {line}-{direction+1}_SHP
    # direction_id 0 -> 1, direction_id 1 -> 2
    bd_shape_id = f"{line}-{direction_id + 1}_SHP"

    return bd_shape_id


def import_trips(db, dry_run: bool = False) -> int:
    """Import trips.txt (only train routes)."""
    logger.info("Paso 4: Importando trips (solo trenes)...")

    rows = load_csv('trips.txt')

    if not rows:
        logger.warning("  No se encontró trips.txt")
        return 0

    trips = []
    trips_by_line = {line: 0 for line in TRAIN_ROUTES.values()}

    for row in rows:
        gtfs_route_id = row['route_id'].strip()

        # Only import train routes
        if gtfs_route_id not in TRAIN_ROUTES:
            continue

        line = TRAIN_ROUTES[gtfs_route_id]
        gtfs_service_id = row['service_id'].strip()
        gtfs_trip_id = row['trip_id'].strip()
        direction_id = int(row.get('direction_id', '0').strip() or '0')

        our_route_id = f"{PREFIX}{gtfs_route_id}"
        our_service_id = f"{PREFIX}{gtfs_service_id}"
        our_trip_id = f"{PREFIX}{gtfs_trip_id}"

        # Map shape_id to BD format
        our_shape_id = get_shape_id_for_trip(
            row.get('shape_id', '').strip(),
            gtfs_route_id,
            direction_id
        )

        trips.append({
            'id': our_trip_id,
            'route_id': our_route_id,
            'service_id': our_service_id,
            'headsign': row.get('trip_headsign', '').strip() or None,
            'short_name': row.get('trip_short_name', '').strip() or None,
            'direction_id': direction_id,
            'block_id': row.get('block_id', '').strip() or None,
            'shape_id': our_shape_id,
            'wheelchair_accessible': 1,
            'bikes_allowed': None,
        })
        trips_by_line[line] += 1

    if dry_run:
        logger.info(f"  [DRY-RUN] Se importarían {len(trips)} trips:")
        for line, count in trips_by_line.items():
            logger.info(f"    {line}: {count} trips")
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

    db.commit()
    logger.info(f"  Importados {len(trips)} trips:")
    for line, count in trips_by_line.items():
        logger.info(f"    {line}: {count} trips")
    return len(trips)


def import_stop_times(db, dry_run: bool = False) -> int:
    """Import stop_times.txt (only for train trips)."""
    logger.info("Paso 5: Importando stop_times (solo trenes)...")

    # First, get all train trip_ids
    trips = load_csv('trips.txt')
    train_trip_ids = set()
    for trip in trips:
        if trip['route_id'].strip() in TRAIN_ROUTES:
            train_trip_ids.add(trip['trip_id'].strip())

    logger.info(f"  Trip IDs de trenes: {len(train_trip_ids)}")

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

            # Only import stop_times for train trips
            if gtfs_trip_id not in train_trip_ids:
                continue

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


def verify_import(db) -> Dict:
    """Verify the import was successful."""
    logger.info("Paso 6: Verificando importación...")

    stats = {}

    # Calendars
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'SFM_MALLORCA_%'"
    )).scalar()
    stats['calendars'] = result
    logger.info(f"  Calendarios: {result}")

    # Calendar dates
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_calendar_dates WHERE service_id LIKE 'SFM_MALLORCA_%'"
    )).scalar()
    stats['calendar_dates'] = result
    logger.info(f"  Calendar_dates: {result}")

    # Trips by route
    result = db.execute(text("""
        SELECT route_id, COUNT(*)
        FROM gtfs_trips
        WHERE route_id LIKE 'SFM_MALLORCA_%'
        GROUP BY route_id
        ORDER BY route_id
    """)).fetchall()
    total_trips = sum(r[1] for r in result)
    stats['trips'] = total_trips
    logger.info(f"  Trips: {total_trips}")
    for route, count in result:
        route_num = route.replace('SFM_MALLORCA_', '')
        line = TRAIN_ROUTES.get(route_num, route_num)
        logger.info(f"    {line} (route {route_num}): {count}")

    # Stop times
    result = db.execute(text(
        "SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'SFM_MALLORCA_%'"
    )).scalar()
    stats['stop_times'] = result
    logger.info(f"  Stop_times: {result:,}")

    # Shapes (check existing)
    result = db.execute(text("""
        SELECT DISTINCT t.shape_id
        FROM gtfs_trips t
        WHERE t.route_id LIKE 'SFM_MALLORCA_%' AND t.shape_id IS NOT NULL
    """)).fetchall()
    shape_ids = [r[0] for r in result]
    stats['shape_ids'] = shape_ids
    logger.info(f"  Shapes usados: {len(shape_ids)} ({', '.join(sorted(shape_ids))})")

    # Verify shapes exist
    for shape_id in shape_ids:
        pts = db.execute(text(
            "SELECT COUNT(*) FROM gtfs_shape_points WHERE shape_id = :sid"
        ), {'sid': shape_id}).scalar()
        if pts == 0:
            logger.warning(f"    ⚠️ Shape {shape_id} no tiene puntos!")
        else:
            logger.info(f"    {shape_id}: {pts} puntos")

    return stats


def analyze():
    """Analyze GTFS files without importing."""
    print("\n" + "=" * 70)
    print("SFM MALLORCA - GTFS ANALYSIS (TRAINS ONLY)")
    print("=" * 70)

    # Agency
    agency = load_csv('agency.txt')
    if agency:
        print(f"\nAgency: {agency[0].get('agency_name', 'N/A')}")

    # All routes
    routes = load_csv('routes.txt')
    print(f"\nAll routes in GTFS: {len(routes)}")

    # Filter train routes
    train_routes = [r for r in routes if r.get('route_id', '').strip() in TRAIN_ROUTES]
    print(f"Train routes (to import): {len(train_routes)}")
    for r in train_routes:
        rid = r.get('route_id', '').strip()
        name = r.get('route_long_name', '').strip()
        line = TRAIN_ROUTES.get(rid, rid)
        print(f"  {line} (route {rid}): {name}")

    # Trips
    trips = load_csv('trips.txt')
    train_trips = [t for t in trips if t.get('route_id', '').strip() in TRAIN_ROUTES]
    print(f"\nAll trips in GTFS: {len(trips):,}")
    print(f"Train trips (to import): {len(train_trips)}")

    # Trips by route
    by_route = {}
    for t in train_trips:
        rid = t.get('route_id', '').strip()
        line = TRAIN_ROUTES.get(rid, rid)
        by_route[line] = by_route.get(line, 0) + 1
    for line, count in sorted(by_route.items()):
        print(f"  {line}: {count} trips")

    # Service IDs for trains
    train_service_ids = set()
    for t in train_trips:
        train_service_ids.add(t.get('service_id', '').strip())
    print(f"\nTrain service IDs: {len(train_service_ids)}")
    for sid in sorted(train_service_ids):
        print(f"  {sid}")

    # Stop times (estimate)
    filepath = os.path.join(GTFS_DIR, 'stop_times.txt')
    if os.path.exists(filepath):
        # Count only train stop_times
        train_trip_ids = {t.get('trip_id', '').strip() for t in train_trips}
        train_st_count = 0
        total_count = 0
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_count += 1
                if row.get('trip_id', '').strip() in train_trip_ids:
                    train_st_count += 1
        print(f"\nAll stop_times in GTFS: {total_count:,}")
        print(f"Train stop_times (to import): {train_st_count:,}")

    # Calendar
    calendar = load_csv('calendar.txt')
    train_calendars = [c for c in calendar if c.get('service_id', '').strip() in train_service_ids]
    print(f"\nAll calendars: {len(calendar)}")
    print(f"Train calendars (to import): {len(train_calendars)}")
    for cal in train_calendars:
        sid = cal.get('service_id', '').strip()
        days = []
        if cal.get('monday') == '1': days.append('L')
        if cal.get('tuesday') == '1': days.append('M')
        if cal.get('wednesday') == '1': days.append('X')
        if cal.get('thursday') == '1': days.append('J')
        if cal.get('friday') == '1': days.append('V')
        if cal.get('saturday') == '1': days.append('S')
        if cal.get('sunday') == '1': days.append('D')
        print(f"  {sid}: {'-'.join(days)} ({cal.get('start_date')} → {cal.get('end_date')})")

    # Calendar dates
    cal_dates = load_csv('calendar_dates.txt')
    train_cal_dates = [c for c in cal_dates if c.get('service_id', '').strip() in train_service_ids]
    print(f"\nAll calendar_dates: {len(cal_dates)}")
    print(f"Train calendar_dates (from NAP): {len(train_cal_dates)}")

    # Festivos to add
    print(f"\nFestivos Baleares/Palma 2026 (to add manually): {len(FESTIVOS_2026)}")
    for date, name in FESTIVOS_2026:
        print(f"  {date}: {name}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Import SFM Mallorca GTFS data from NAP (trains only)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--analyze', action='store_true', help='Analyze GTFS files only')
    args = parser.parse_args()

    # Check GTFS directory exists
    if not os.path.isdir(GTFS_DIR):
        logger.error(f"GTFS directory not found: {GTFS_DIR}")
        logger.error("Download with: curl -X GET 'https://nap.transportes.gob.es/api/Fichero/download/1272' "
                    "-H 'ApiKey: YOUR_KEY' -o data/gtfs_sfm_mallorca.zip && "
                    "unzip -o data/gtfs_sfm_mallorca.zip -d data/gtfs_sfm_mallorca")
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
        print("IMPORT SUMMARY - SFM Mallorca (Trains)")
        print("=" * 70)
        print(f"Calendarios: {calendars}")
        print(f"Calendar_dates: {calendar_dates}")
        print(f"Trips: {trips}")
        print(f"Stop_times: {stop_times:,}")
        print(f"Shapes: Mantenidos de BD (no importados)")
        print(f"Tiempo: {elapsed}")
        print("=" * 70)

        if args.dry_run:
            print("\n[DRY RUN - No se guardaron cambios]")
        else:
            print("\n✅ SFM Mallorca GTFS import completed!")
            print("\nNext steps:")
            print("  1. Restart server: systemctl restart renfeserver")
            print("  2. Test: curl 'https://redcercanias.com/api/v1/gtfs/stops/SFM_MALLORCA_71801/departures?limit=5'")

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
