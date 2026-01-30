#!/usr/bin/env python3
"""Import GTFS data for Tranvía de Sevilla (MetroCentro T1) from TUSSAM/NAP.

This script imports the tranvia trips and stop_times from the TUSSAM GTFS
downloaded from NAP (Punto de Acceso Nacional).

The TUSSAM GTFS contains bus and tram data. This script filters only
route_id=60 (T1 Metrocentro tram).

Usage:
    python scripts/import_tranvia_sevilla_gtfs.py /tmp/gtfs_tussam
    python scripts/import_tranvia_sevilla_gtfs.py /tmp/gtfs_tussam --dry-run
    python scripts/import_tranvia_sevilla_gtfs.py /tmp/gtfs_tussam --analyze

Download GTFS:
    curl -sL "https://nap.transportes.gob.es/api/Fichero/download/1567" \
         -H "apikey: YOUR_API_KEY" -o tussam.zip

GTFS Source: NAP (Punto de Acceso Nacional) File ID 1567
"""

import sys
import os
import csv
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

# Tranvía Sevilla configuration
TRAM_SEV_ROUTE_ID = 'TRAM_SEV_T1'
TRAM_SEV_NETWORK_ID = 'TRAM_SEV'
TUSSAM_TRANVIA_ROUTE_ID = '60'  # TUSSAM internal route_id for tranvia

# Shape IDs for directions (must match shapes in gtfs_shapes table)
SHAPE_ID_AI_LM = 'TRAM_SEV_T1_BROUTER'      # Archivo de Indias -> Luis de Morales
SHAPE_ID_LM_AI = 'TRAM_SEV_T1_BROUTER_REV'  # Luis de Morales -> Archivo de Indias

# Stop ID mapping: TUSSAM stop_id -> Our stop_id
STOP_MAPPING = {
    # Direction 0: Archivo de Indias -> Luis de Morales
    '3005': 'TRAM_SEV_ARCHIVO_DE_INDIAS',
    '3006': 'TRAM_SEV_PUERTA_JEREZ',
    '3007': 'TRAM_SEV_PRADO_SAN_SEBASTIÁN',
    '3008': 'TRAM_SEV_SAN_BERNARDO',
    '3010': 'TRAM_SEV_SAN_FRANCISCO_JAVIER',
    '3011': 'TRAM_SEV_EDUARDO_DATO',
    '3012': 'TRAM_SEV_LUIS_DE_MORALES',
    # Direction 1: Luis de Morales -> Archivo de Indias (same stops, different TUSSAM IDs)
    '3014': 'TRAM_SEV_EDUARDO_DATO',
    '3015': 'TRAM_SEV_SAN_FRANCISCO_JAVIER',
    '3009': 'TRAM_SEV_SAN_BERNARDO',
    '3000': 'TRAM_SEV_PRADO_SAN_SEBASTIÁN',
    '3001': 'TRAM_SEV_PUERTA_JEREZ',
}


def time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS to seconds since midnight."""
    parts = time_str.strip().split(':')
    if len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    elif len(parts) == 2:
        hours, minutes = int(parts[0]), int(parts[1])
        seconds = 0
    else:
        return 0
    return hours * 3600 + minutes * 60 + seconds


def seconds_to_time(secs: int) -> str:
    """Convert seconds since midnight to HH:MM:SS format."""
    hours = secs // 3600
    minutes = (secs % 3600) // 60
    seconds = secs % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def parse_date(date_str: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD."""
    date_str = date_str.strip()
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


def load_csv(directory: str, filename: str) -> List[Dict]:
    """Load a CSV file from the GTFS directory."""
    filepath = os.path.join(directory, filename)
    if not os.path.exists(filepath):
        return []

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def get_tranvia_trips(directory: str) -> List[Dict]:
    """Get only tranvia trips from TUSSAM GTFS."""
    all_trips = load_csv(directory, 'trips.txt')
    return [t for t in all_trips if t['route_id'] == TUSSAM_TRANVIA_ROUTE_ID]


def get_tranvia_stop_times(directory: str, trip_ids: set) -> List[Dict]:
    """Get stop_times for tranvia trips only."""
    all_stop_times = load_csv(directory, 'stop_times.txt')
    return [st for st in all_stop_times if st['trip_id'] in trip_ids]


def map_service_id(tussam_service_id: str) -> str:
    """Map TUSSAM service_id to our service_id format."""
    # TUSSAM uses: INVFES80, INVLAB80, INVSAB80, INVVIE80
    # We use: TRAM_SEV_LABORABLE, TRAM_SEV_VIERNES, TRAM_SEV_SABADO, TRAM_SEV_DOMINGO
    mapping = {
        'INVLAB80': 'TRAM_SEV_LABORABLE',
        'INVVIE80': 'TRAM_SEV_VIERNES',
        'INVSAB80': 'TRAM_SEV_SABADO',
        'INVFES80': 'TRAM_SEV_DOMINGO',
    }
    return mapping.get(tussam_service_id, f'TRAM_SEV_{tussam_service_id}')


def verify_our_stops(db) -> Dict[str, str]:
    """Verify our Tranvía Sevilla stops exist."""
    result = db.execute(text(
        "SELECT id, name FROM gtfs_stops WHERE id LIKE 'TRAM_SEV_%'"
    )).fetchall()

    stops = {row[0]: row[1] for row in result}
    logger.info(f"Found {len(stops)} TRAM_SEV stops in database")

    return stops


def verify_route_exists(db) -> bool:
    """Verify Tranvía Sevilla route exists."""
    result = db.execute(text(
        "SELECT id, short_name FROM gtfs_routes WHERE id = :rid"
    ), {'rid': TRAM_SEV_ROUTE_ID}).fetchone()

    if not result:
        logger.error(f"Route {TRAM_SEV_ROUTE_ID} not found!")
        return False

    logger.info(f"Found route: {result[0]} ({result[1]})")
    return True


def clear_tram_sev_data(db):
    """Clear existing Tranvía Sevilla trips and stop_times."""
    logger.info("Clearing existing Tranvía Sevilla schedule data...")

    # Delete stop_times
    result = db.execute(text("""
        DELETE FROM gtfs_stop_times
        WHERE trip_id IN (
            SELECT id FROM gtfs_trips WHERE route_id = :rid
        )
    """), {'rid': TRAM_SEV_ROUTE_ID})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} stop_times")

    # Delete trips
    result = db.execute(text(
        "DELETE FROM gtfs_trips WHERE route_id = :rid"
    ), {'rid': TRAM_SEV_ROUTE_ID})
    db.commit()
    logger.info(f"  Cleared {result.rowcount} trips")

    # Delete calendar_dates for TRAM_SEV
    result = db.execute(text(
        "DELETE FROM gtfs_calendar_dates WHERE service_id LIKE 'TRAM_SEV_%'"
    ))
    db.commit()
    logger.info(f"  Cleared {result.rowcount} calendar_dates")

    # Delete calendars
    result = db.execute(text(
        "DELETE FROM gtfs_calendar WHERE service_id LIKE 'TRAM_SEV_%'"
    ))
    db.commit()
    logger.info(f"  Cleared {result.rowcount} calendar entries")


def import_calendar(db, directory: str) -> int:
    """Import calendar.txt with TRAM_SEV_ prefix.

    Note: NAP calendar data only covers until April 2026, so we extend
    the end_date to December 2026 for full coverage.
    """
    logger.info("Importing calendar data...")

    rows = load_csv(directory, 'calendar.txt')

    # Extended end date for hybrid import (NAP only has until April 2026)
    EXTENDED_END_DATE = '2026-12-31'

    calendar_rows = []
    for row in rows:
        tussam_service_id = row['service_id'].strip()
        our_service_id = map_service_id(tussam_service_id)

        original_end = parse_date(row['end_date'])
        logger.info(f"  Calendar {our_service_id}: extending end_date from {original_end} to {EXTENDED_END_DATE}")

        calendar_rows.append({
            'service_id': our_service_id,
            'monday': row['monday'].strip() == '1',
            'tuesday': row['tuesday'].strip() == '1',
            'wednesday': row['wednesday'].strip() == '1',
            'thursday': row['thursday'].strip() == '1',
            'friday': row['friday'].strip() == '1',
            'saturday': row['saturday'].strip() == '1',
            'sunday': row['sunday'].strip() == '1',
            'start_date': parse_date(row['start_date']),
            'end_date': EXTENDED_END_DATE,
        })

    if calendar_rows:
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
            calendar_rows
        )
        db.commit()

    return len(calendar_rows)


def import_trips_and_stop_times(db, directory: str, our_stops: Dict[str, str]) -> tuple:
    """Import tranvia trips and stop_times."""
    logger.info("Loading tranvia trips from TUSSAM GTFS...")

    tranvia_trips = get_tranvia_trips(directory)
    logger.info(f"Found {len(tranvia_trips)} tranvia trips")

    trip_ids = {t['trip_id'] for t in tranvia_trips}
    tranvia_stop_times = get_tranvia_stop_times(directory, trip_ids)
    logger.info(f"Found {len(tranvia_stop_times)} tranvia stop_times")

    # Process trips
    trips_to_insert = []
    for trip in tranvia_trips:
        tussam_trip_id = trip['trip_id']
        our_trip_id = f"TRAM_SEV_{tussam_trip_id}"
        our_service_id = map_service_id(trip['service_id'])
        direction_id = int(trip.get('direction_id', '0'))
        headsign = trip.get('trip_headsign', '').strip()

        # Map headsign to our stop names
        if 'MORALES' in headsign.upper():
            headsign = 'Luis de Morales'
            shape_id = SHAPE_ID_AI_LM
        else:
            headsign = 'Archivo de Indias'
            shape_id = SHAPE_ID_LM_AI

        trips_to_insert.append({
            'id': our_trip_id,
            'route_id': TRAM_SEV_ROUTE_ID,
            'service_id': our_service_id,
            'headsign': headsign,
            'short_name': None,
            'direction_id': direction_id,
            'block_id': None,
            'shape_id': shape_id,
            'wheelchair_accessible': 1,
            'bikes_allowed': None,
        })

    # Process stop_times
    stop_times_to_insert = []
    skipped_stops = defaultdict(int)

    for st in tranvia_stop_times:
        tussam_trip_id = st['trip_id']
        our_trip_id = f"TRAM_SEV_{tussam_trip_id}"
        tussam_stop_id = st['stop_id'].strip()

        our_stop_id = STOP_MAPPING.get(tussam_stop_id)
        if not our_stop_id:
            skipped_stops[tussam_stop_id] += 1
            continue

        if our_stop_id not in our_stops:
            skipped_stops[our_stop_id] += 1
            continue

        arrival_time = st['arrival_time'].strip()
        departure_time = st['departure_time'].strip()
        arrival_secs = time_to_seconds(arrival_time)
        departure_secs = time_to_seconds(departure_time)

        stop_times_to_insert.append({
            'trip_id': our_trip_id,
            'stop_sequence': int(st['stop_sequence']),
            'stop_id': our_stop_id,
            'arrival_time': arrival_time,
            'departure_time': departure_time,
            'arrival_seconds': arrival_secs,
            'departure_seconds': departure_secs,
            'stop_headsign': None,
            'pickup_type': 0,
            'drop_off_type': 0,
            'shape_dist_traveled': None,
            'timepoint': 1,
        })

    if skipped_stops:
        logger.warning(f"Skipped stop_times for unmapped stops: {dict(skipped_stops)}")

    # Insert trips
    logger.info(f"Inserting {len(trips_to_insert)} trips...")
    for i in range(0, len(trips_to_insert), BATCH_SIZE):
        batch = trips_to_insert[i:i+BATCH_SIZE]
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
    logger.info(f"Inserting {len(stop_times_to_insert)} stop_times...")
    for i in range(0, len(stop_times_to_insert), BATCH_SIZE):
        batch = stop_times_to_insert[i:i+BATCH_SIZE]
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
        if (i + BATCH_SIZE) % 2000 == 0 or i + BATCH_SIZE >= len(stop_times_to_insert):
            logger.info(f"  Inserted {min(i + BATCH_SIZE, len(stop_times_to_insert))} stop_times...")
    db.commit()

    return len(trips_to_insert), len(stop_times_to_insert)


def analyze_gtfs(directory: str):
    """Analyze TUSSAM GTFS tranvia data."""
    print("\n" + "=" * 70)
    print("TRANVÍA SEVILLA (TUSSAM) GTFS ANALYSIS")
    print("=" * 70)

    # Trips
    tranvia_trips = get_tranvia_trips(directory)
    print(f"\nTranvia trips: {len(tranvia_trips)}")

    # By service
    by_service = defaultdict(int)
    for t in tranvia_trips:
        by_service[t['service_id']] += 1

    print("\nTrips by service:")
    for service_id, count in sorted(by_service.items()):
        our_service = map_service_id(service_id)
        print(f"  {service_id} -> {our_service}: {count}")

    # Stop times
    trip_ids = {t['trip_id'] for t in tranvia_trips}
    tranvia_stop_times = get_tranvia_stop_times(directory, trip_ids)
    print(f"\nTotal stop_times: {len(tranvia_stop_times)}")

    # Unique stops used
    stops_used = set()
    for st in tranvia_stop_times:
        stops_used.add(st['stop_id'])

    print(f"\nUnique stops used: {len(stops_used)}")
    for stop_id in sorted(stops_used):
        our_stop = STOP_MAPPING.get(stop_id, "NOT MAPPED")
        print(f"  {stop_id} -> {our_stop}")

    # Calendar
    calendars = load_csv(directory, 'calendar.txt')
    print(f"\nCalendar entries: {len(calendars)}")
    for cal in calendars:
        days = []
        for d in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            if cal.get(d) == '1':
                days.append(d[:3])
        print(f"  {cal['service_id']}: {', '.join(days)} ({cal['start_date']} - {cal['end_date']})")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Import GTFS data for Tranvía de Sevilla from TUSSAM/NAP'
    )
    parser.add_argument('gtfs_dir', help='Path to GTFS directory (e.g., /tmp/gtfs_tussam)')
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze GTFS files only'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Load data but do not import to database'
    )

    args = parser.parse_args()

    if not os.path.isdir(args.gtfs_dir):
        logger.error(f"Directory not found: {args.gtfs_dir}")
        sys.exit(1)

    # Analyze mode
    if args.analyze:
        analyze_gtfs(args.gtfs_dir)
        sys.exit(0)

    # Dry run mode
    if args.dry_run:
        logger.info("DRY RUN - Analyzing data only")
        analyze_gtfs(args.gtfs_dir)
        sys.exit(0)

    # Real import
    db = SessionLocal()

    try:
        start_time = datetime.now()

        # Verify prerequisites
        if not verify_route_exists(db):
            sys.exit(1)

        our_stops = verify_our_stops(db)
        if not our_stops:
            logger.error("No TRAM_SEV stops found! Import stops first.")
            sys.exit(1)

        # Clear existing data
        clear_tram_sev_data(db)

        # Import calendar
        calendar_count = import_calendar(db, args.gtfs_dir)
        logger.info(f"Imported {calendar_count} calendar entries")

        # Import trips and stop_times
        trips_count, stop_times_count = import_trips_and_stop_times(db, args.gtfs_dir, our_stops)

        elapsed = datetime.now() - start_time

        # Summary
        print("\n" + "=" * 70)
        print("IMPORT SUMMARY - Tranvía de Sevilla")
        print("=" * 70)
        print(f"Calendar entries: {calendar_count}")
        print(f"Trips: {trips_count}")
        print(f"Stop times: {stop_times_count}")
        print(f"Elapsed time: {elapsed}")
        print("=" * 70)
        print("\nTranvía Sevilla GTFS import completed successfully!")
        print("\nNext steps:")
        print("  1. Restart the server to reload GTFSStore")
        print("  2. Verify with: SELECT COUNT(*) FROM gtfs_trips WHERE route_id = 'TRAM_SEV_T1';")
        print("  3. Test departures: curl 'http://localhost:8002/api/v1/gtfs/stops/TRAM_SEV_ARCHIVO_DE_INDIAS/departures?limit=5'")

    except Exception as e:
        db.rollback()
        logger.error(f"Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
